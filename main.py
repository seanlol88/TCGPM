from datetime import date as date_type, timedelta, datetime
from fastapi import FastAPI, Request
from fastapi.responses import Response
from starlette.middleware.sessions import SessionMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from jinja2 import FileSystemLoader
from pathlib import Path
from sqlalchemy import func, case, distinct
from sqlalchemy.orm import joinedload
import sys
import threading
import time

import config
from models.base import init_db, SessionLocal
from models.product import Product
from models.customer import Customer
from models.order import Order, OrderItem
from models.category import Category
from models.subcategory import Subcategory
from models.payment import Payment
from models.order_log import OrderLog
from models.store_settings import StoreSettings
from models.distributor import Distributor, ProductDistributor
from api import inventory as inventory_api
from api import customers as customers_api
from api import orders as orders_api
from api import categories as categories_api
from api import subcategories as subcategories_api
from api import payments as payments_api
from api import audit as audit_api
from api import settings as settings_api
from api import backups as backups_api
from api import gmail as gmail_api
from api import system as system_api
from api import distributors as distributors_api
from api import auth as auth_api
from api import setup as setup_api
from api import recovery as recovery_api

app = FastAPI(title=config.APP_TITLE)

# Session middleware for Google Drive OAuth2 flow and staff login
# NOTE: add_middleware is LIFO - last added wraps outermost
# LoginRedirectMiddleware must be added FIRST so it runs AFTER SessionMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import RedirectResponse as StarletteRedirect

LOGIN_WHITELIST = {"/login", "/logout", "/auth/check", "/static", "/openapi.json", "/docs", "/docs/oauth2-redirect",
                   "/setup", "/setup/complete", "/setup/gmail-connect", "/setup/skip-gmail",
                   "/recovery", "/recovery/reset", "/recovery/complete"}
SETUP_PREFIXES = ["/setup", "/gmail/callback", "/recovery"]


def _check_session_timeout(request: Request):
    """Check if the session has expired due to inactivity timeout. If so, clear the session."""
    from api.auth import is_session_expired, update_last_activity
    if is_session_expired(request):
        request.session.clear()
        return True
    # Update last activity on each successful request
    update_last_activity(request)
    return False


def _is_first_run():
    """Check if this is the first run (setup not complete)."""
    db = SessionLocal()
    try:
        settings = StoreSettings.get(db)
        return not settings.setup_complete
    except Exception:
        return False
    finally:
        db.close()


def _is_setup_path(path: str) -> bool:
    """Check if the path is a setup-related route."""
    if path in LOGIN_WHITELIST:
        return True
    for prefix in SETUP_PREFIXES:
        if path.startswith(prefix):
            return True
    return False


class LoginRedirectMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        path = request.url.path
        # Allow login, logout, auth check, static files, and setup routes without auth
        if path in LOGIN_WHITELIST or path.startswith("/static/") or _is_setup_path(path):
            return await call_next(request)
        # Check if user is logged in (session is available after SessionMiddleware)
        staff_id = request.session.get("staff_id")
        if not staff_id:
            # If first run, redirect to setup wizard instead of login
            if _is_first_run():
                return StarletteRedirect(url="/setup", status_code=302)
            return StarletteRedirect(url="/login", status_code=302)
        # Check session timeout
        if _check_session_timeout(request):
            return StarletteRedirect(url="/login?timeout=1", status_code=302)
        return await call_next(request)

app.add_middleware(LoginRedirectMiddleware)
app.add_middleware(SessionMiddleware, secret_key=config.SESSION_SECRET, max_age=86400)

# Cache control middleware - prevent browser caching of all responses
# Added last so it is outermost (LIFO), but does not access session
class CacheControlMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        return response

app.add_middleware(CacheControlMiddleware)

# Ensure database directory exists
Path(config.DATABASE_URL.replace("sqlite:///", "")).parent.mkdir(parents=True, exist_ok=True)

# Initialize database tables
init_db()

# Templates - disable cache to always load latest version
template_loader = FileSystemLoader(str(Path(__file__).parent / "templates"))
template_loader.cache = False  # type: ignore
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
templates.env.loader = template_loader

# Make templates available to API routes
inventory_api.templates = templates
customers_api.templates = templates
orders_api.templates = templates
categories_api.templates = templates
subcategories_api.templates = templates
payments_api.templates = templates
audit_api.templates = templates
settings_api.templates = templates
backups_api.templates = templates
gmail_api.templates = templates
auth_api.templates = templates
setup_api.templates = templates

# Include routers (setup first so its routes take priority)
app.include_router(setup_api.router)
app.include_router(auth_api.router)
app.include_router(inventory_api.router)
app.include_router(customers_api.router)
app.include_router(orders_api.router)
app.include_router(categories_api.router)
app.include_router(subcategories_api.router)
app.include_router(payments_api.router)
app.include_router(audit_api.router)
app.include_router(settings_api.router)
app.include_router(backups_api.router)
app.include_router(gmail_api.router)
app.include_router(system_api.router)
app.include_router(distributors_api.router)
app.include_router(recovery_api.router)
system_api.templates = templates
distributors_api.templates = templates
recovery_api.templates = templates

# Static files for uploaded logos
static_dir = Path(__file__).parent / "static"
static_dir.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


# Inject store settings and current staff into all templates via Jinja2 globals
def _get_store_settings():
    db = SessionLocal()
    try:
        return StoreSettings.get(db)
    finally:
        db.close()

def _get_current_staff_name(request):
    """Get the current staff name from the session."""
    from api.auth import get_current_staff
    staff = get_current_staff(request)
    if staff:
        return staff.name
    # Fallback to session value if DB lookup fails
    return getattr(request, 'session', {}).get('staff_name', None)

# Use a simple approach: override TemplateResponse to inject settings and staff
original_template_response = templates.TemplateResponse

def patched_template_response(name, context, status_code=200, headers=None, media_type=None, background=None):
    context["store_settings"] = _get_store_settings()
    # Inject current staff info and permissions into all templates
    request = context.get("request")
    if request:
        staff_name = _get_current_staff_name(request)
        context["current_staff_name"] = staff_name
        from api.auth import get_staff_permissions
        context["current_permissions"] = get_staff_permissions(request)
    else:
        context["current_staff_name"] = None
        context["current_permissions"] = {}
    return original_template_response(name, context, status_code=status_code, headers=headers, media_type=media_type, background=background)

templates.TemplateResponse = patched_template_response


@app.get("/")
def dashboard(request: Request):
    db = SessionLocal()
    try:
        product_count = db.query(Product).count()
        stock_count = db.query(func.sum(Product.quantity)).scalar() or 0
        customer_count = db.query(Customer).count()
        order_count = db.query(Order).filter(Order.deleted == False).count()
        category_count = db.query(Category).count()
        subcategory_count = db.query(Subcategory).count()
        payment_count = db.query(Payment).count()
        today = date_type.today()
        upcoming_releases = (
            db.query(Product)
            .options(
                joinedload(Product.category),
                joinedload(Product.subcategory).joinedload(Subcategory.category),
            )
            .filter(
                Product.release_date != None,
            )
            .order_by(Product.release_date.asc())
            .limit(5)
            .all()
        )
        # Calculate available stock for upcoming releases (total minus reserved in unpicked orders)
        upcoming_product_ids = [p.id for p in upcoming_releases]
        reserved_stock = {}
        if upcoming_product_ids:
            reserved_orders = (
                db.query(Order)
                .options(
                    joinedload(Order.items).joinedload(OrderItem.product),
                )
                .filter(Order.deleted == False)
                .all()
            )
            for order in reserved_orders:
                # Skip fully picked up orders - their stock is no longer reserved
                if order.picked_up:
                    continue
                for item in order.items:
                    if item.product and item.product.id in upcoming_product_ids:
                        unpicked = (item.quantity or 0) - (item.picked_up_quantity or 0)
                        if unpicked > 0:
                            prod_id = item.product.id
                            reserved_stock[prod_id] = reserved_stock.get(prod_id, 0) + unpicked
        upcoming_release_count = len(upcoming_releases)
        recent_orders = (
            db.query(Order)
            .options(
                joinedload(Order.customer),
                joinedload(Order.items).joinedload(OrderItem.product),
            )
            .filter(Order.deleted == False)
            .order_by(Order.id.desc())
            .limit(5)
            .all()
        )
        # Actual profit from picked-up items per category
        # Query all non-deleted orders with items that have been picked up
        category_profit_data = []
        categories = db.query(Category).order_by(Category.name.asc()).all()
        
        # Get all orders (including deleted) with their items and products
        all_orders = (
            db.query(Order)
            .options(
                joinedload(Order.items).joinedload(OrderItem.product).joinedload(Product.category),
            )
            .all()
        )
        
        # Calculate actual profit from picked-up quantities and find hottest item per category
        for cat in categories:
            total_cost = 0.0
            total_revenue = 0.0
            total_profit = 0.0
            items_sold = 0
            # Track picked-up quantities per product to find the hottest item
            product_picked = {}
            for order in all_orders:
                for item in order.items:
                    if item.product and item.product.category_id == cat.id:
                        picked = item.picked_up_quantity or 0
                        if picked > 0:
                            cost = item.product.cost_price or 0.0
                            price = item.unit_price or 0.0
                            total_cost += cost * picked
                            total_revenue += price * picked
                            total_profit += (price - cost) * picked
                            items_sold += picked
                            # Accumulate picked quantity per product
                            prod_id = item.product.id
                            if prod_id not in product_picked:
                                product_picked[prod_id] = {"name": item.product.name, "picked": 0}
                            product_picked[prod_id]["picked"] += picked
            # Find the hottest item (most picked up)
            hottest_item = None
            hottest_count = 0
            for prod_data in product_picked.values():
                if prod_data["picked"] > hottest_count:
                    hottest_count = prod_data["picked"]
                    hottest_item = prod_data["name"]
            margin = (total_profit / total_revenue * 100) if total_revenue > 0 else 0.0
            category_profit_data.append({
                "name": cat.name,
                "items_sold": items_sold,
                "total_cost": total_cost,
                "total_revenue": total_revenue,
                "total_profit": total_profit,
                "margin": margin,
                "hottest_item": hottest_item,
                "hottest_count": hottest_count,
            })
        
        # Calculate totals for the summary
        grand_revenue = sum(cat["total_revenue"] for cat in category_profit_data)
        grand_cost = sum(cat["total_cost"] for cat in category_profit_data)
        grand_profit = sum(cat["total_profit"] for cat in category_profit_data)
        grand_items_sold = sum(cat["items_sold"] for cat in category_profit_data)
        grand_margin = (grand_profit / grand_revenue * 100) if grand_revenue > 0 else 0.0
        
        # Calculate total cost of unpicked items (ordered but not yet collected)
        total_unpicked_cost = 0.0
        total_unpicked_revenue = 0.0
        unpicked_items_count = 0
        for order in all_orders:
            if order.deleted:
                continue
            # Skip fully picked up orders - no unpicked items remain
            if order.picked_up:
                continue
            for item in order.items:
                if item.product:
                    unpicked = (item.quantity or 0) - (item.picked_up_quantity or 0)
                    if unpicked > 0:
                        cost = item.product.cost_price or 0.0
                        price = item.unit_price or 0.0
                        total_unpicked_cost += cost * unpicked
                        total_unpicked_revenue += price * unpicked
                        unpicked_items_count += unpicked
        
        # Calculate last 3 months of sales data (from picked-up items)
        today = date_type.today()
        # Build the last 3 calendar months
        month_data = []
        for month_offset in range(2, -1, -1):
            target_month = today.month - month_offset
            target_year = today.year
            while target_month <= 0:
                target_month += 12
                target_year -= 1
            month_data.append({
                "year": target_year,
                "month": target_month,
                "label": target_year.strftime("%B") if isinstance(target_year, datetime) else date_type(target_year, target_month, 1).strftime("%b %Y"),
                "revenue": 0.0,
                "cost": 0.0,
                "profit": 0.0,
                "orders": 0,
                "items_sold": 0,
            })
        
        # Count unique orders per month (by order_date)
        order_months = {}  # (year, month) -> set of order ids
        
        # Calculate monthly profit from picked-up items
        for order in all_orders:
            for item in order.items:
                if item.product:
                    picked = item.picked_up_quantity or 0
                    if picked > 0:
                        # Use order_date to determine the month
                        order_date = order.order_date
                        if isinstance(order_date, datetime):
                            y, m = order_date.year, order_date.month
                        elif isinstance(order_date, date_type):
                            y, m = order_date.year, order_date.month
                        else:
                            continue
                        cost = item.product.cost_price or 0.0
                        price = item.unit_price or 0.0
                        for md in month_data:
                            if md["year"] == y and md["month"] == m:
                                md["revenue"] += price * picked
                                md["cost"] += cost * picked
                                md["profit"] += (price - cost) * picked
                                md["items_sold"] += picked
                                # Track unique orders per month
                                key = (y, m)
                                if key not in order_months:
                                    order_months[key] = set()
                                order_months[key].add(order.id)
        
        # Apply order counts
        for md in month_data:
            key = (md["year"], md["month"])
            md["orders"] = len(order_months.get(key, set()))
        
        # Find the best month (by revenue) and add index
        best_month_idx = 0
        best_revenue = 0
        for i, md in enumerate(month_data):
            md["index"] = i
            if md["revenue"] > best_revenue:
                best_revenue = md["revenue"]
                best_month_idx = i
        
        # Financial year category ranking (July 1 - June 30, Australian financial year)
        # Determine the current financial year
        fy_today = date_type.today()
        if fy_today.month >= 7:
            fy_start_year = fy_today.year
        else:
            fy_start_year = fy_today.year - 1
        fy_start = date_type(fy_start_year, 7, 1)
        fy_end = date_type(fy_start_year + 1, 6, 30)
        
        # Calculate pickups per category during the financial year
        fy_category_ranking = []
        for cat in categories:
            fy_items_sold = 0
            fy_revenue = 0.0
            fy_profit = 0.0
            fy_orders = set()
            for order in all_orders:
                if order.deleted:
                    continue
                # Check if order date is within the financial year
                order_date = order.order_date
                if isinstance(order_date, datetime):
                    order_date_only = order_date.date()
                elif isinstance(order_date, date_type):
                    order_date_only = order_date
                else:
                    continue
                if order_date_only < fy_start or order_date_only > fy_end:
                    continue
                for item in order.items:
                    if item.product and item.product.category_id == cat.id:
                        picked = item.picked_up_quantity or 0
                        if picked > 0:
                            fy_items_sold += picked
                            fy_revenue += (item.unit_price or 0.0) * picked
                            fy_profit += ((item.unit_price or 0.0) - (item.product.cost_price or 0.0)) * picked
                            fy_orders.add(order.id)
            fy_category_ranking.append({
                "name": cat.name,
                "items_sold": fy_items_sold,
                "revenue": fy_revenue,
                "profit": fy_profit,
                "orders": len(fy_orders),
            })
        
        # Sort by items_sold descending for ranking
        fy_category_ranking.sort(key=lambda x: x["items_sold"], reverse=True)
        for rank, item in enumerate(fy_category_ranking, 1):
            item["rank"] = rank
    finally:
        db.close()

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "product_count": product_count,
        "stock_count": stock_count,
        "customer_count": customer_count,
        "order_count": order_count,
        "category_count": category_count,
        "subcategory_count": subcategory_count,
        "payment_count": payment_count,
        "upcoming_release_count": upcoming_release_count,
        "upcoming_releases": upcoming_releases,
        "reserved_stock": reserved_stock,
        "recent_orders": recent_orders,
        "category_profit_data": category_profit_data,
        "grand_revenue": grand_revenue,
        "grand_cost": grand_cost,
        "grand_profit": grand_profit,
        "grand_items_sold": grand_items_sold,
        "grand_margin": grand_margin,
        "total_unpicked_cost": total_unpicked_cost,
        "total_unpicked_revenue": total_unpicked_revenue,
        "unpicked_items_count": unpicked_items_count,
        "month_data": month_data,
        "best_month_idx": best_month_idx,
        "fy_category_ranking": fy_category_ranking,
        "fy_start_year": fy_start_year,
        "date_type": date_type,
    })


def backup_scheduler():
    """Background thread that runs scheduled backups."""
    # Day names mapped to weekday numbers (Monday=0, Sunday=6)
    weekday_map = {
        "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
        "friday": 4, "saturday": 5, "sunday": 6
    }
    
    while True:
        time.sleep(60)  # Check every minute
        db = SessionLocal()
        try:
            settings = StoreSettings.get(db)
            if not settings.backup_enabled:
                continue
            
            # Determine if we should run a backup based on schedule
            should_run = False
            now = time.localtime()
            today = date_type.today()
            
            if settings.backup_schedule == "hourly":
                # Run at the top of each hour
                if now.tm_min == 0 and not settings.backup_last_run:
                    should_run = True
                elif settings.backup_last_run:
                    last = settings.backup_last_run
                    if last.hour != now.tm_hour or last.date() != today:
                        should_run = True
            elif settings.backup_schedule == "daily":
                # Run once per day at the configured time
                backup_time = settings.backup_time or "02:00"
                try:
                    backup_hour, backup_minute = map(int, backup_time.split(":"))
                except (ValueError, AttributeError):
                    backup_hour, backup_minute = 2, 0
                
                # Check if the current time matches the scheduled time
                time_match = (now.tm_hour == backup_hour and now.tm_min == backup_minute)
                
                if not settings.backup_last_run:
                    if time_match:
                        should_run = True
                elif settings.backup_last_run.date() < today:
                    # Last backup was on a different day, check if it's time
                    if time_match:
                        should_run = True
            elif settings.backup_schedule == "weekly":
                # Run once per week on the configured day and time
                backup_time = settings.backup_time or "02:00"
                backup_weekday = settings.backup_weekday or "monday"
                try:
                    backup_hour, backup_minute = map(int, backup_time.split(":"))
                except (ValueError, AttributeError):
                    backup_hour, backup_minute = 2, 0
                
                target_weekday = weekday_map.get(backup_weekday, 0)
                time_match = (now.tm_hour == backup_hour and now.tm_min == backup_minute)
                
                if not settings.backup_last_run:
                    if today.weekday() == target_weekday and time_match:
                        should_run = True
                elif settings.backup_last_run.date() < today - timedelta(days=7):
                    # Last backup was more than a week ago, check if it's the right day and time
                    if today.weekday() == target_weekday and time_match:
                        should_run = True
            
            if should_run:
                from services.backup import create_backup
                try:
                    create_backup()
                except Exception as e:
                    print(f"Backup scheduler error: {e}")
        except Exception as e:
            print(f"Backup scheduler error: {e}")
        finally:
            db.close()


@app.on_event("startup")
def startup_event():
    """Start the backup scheduler thread and system tray icon on app startup."""
    scheduler_thread = threading.Thread(target=backup_scheduler, daemon=True)
    scheduler_thread.start()
    
    # Start system tray icon (only on Windows)
    if sys.platform == "win32":
        from services.tray import start_tray
        start_tray()


if __name__ == "__main__":
    import sys
    import io
    import uvicorn
    
    # Fix for PyInstaller GUI apps (console=False): sys.stdout/stderr are None,
    # which crashes uvicorn's logging formatter when it calls sys.stdout.isatty().
    # Provide fallback streams so uvicorn's logging works correctly.
    if sys.stdout is None:
        sys.stdout = io.TextIOWrapper(io.BytesIO(), encoding="utf-8")
    if sys.stderr is None:
        sys.stderr = io.TextIOWrapper(io.BytesIO(), encoding="utf-8")
    
    # Read port from store_settings or .app_port file or default to 8001
    port = 8001
    env_file = Path(__file__).parent / ".app_port"
    if env_file.exists():
        try:
            port = int(env_file.read_text().strip())
        except (ValueError, IOError):
            pass
    # Also check database for port setting
    try:
        db = SessionLocal()
        settings = StoreSettings.get(db)
        if settings and settings.app_port:
            port = settings.app_port
        db.close()
    except Exception:
        pass
    uvicorn.run(app, host="0.0.0.0", port=port, log_config=None)
