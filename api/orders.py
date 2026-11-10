from fastapi import APIRouter, Request, Form
from fastapi.responses import RedirectResponse, JSONResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, joinedload
from datetime import datetime, timezone, timedelta
from models.base import SessionLocal
from models.product import Product
from models.customer import Customer
from models.order import Order, OrderItem
from models.category import Category
from models.subcategory import Subcategory
from models.payment import Payment
from models.order_log import OrderLog
from models.order_note import OrderNote
from api.auth import get_staff_name

router = APIRouter()
templates: Jinja2Templates = None  # type: ignore[assignment]


def get_melbourne_time():
    """Get current time in Melbourne, Australia timezone."""
    import calendar
    now_utc = datetime.now(timezone.utc)
    year = now_utc.year
    oct_cal = calendar.monthcalendar(year, 10)
    first_sun_oct = datetime(year, 10, oct_cal[0][6] if oct_cal[0][6] else oct_cal[1][6], tzinfo=timezone.utc)
    apr_cal = calendar.monthcalendar(year, 4)
    first_sun_apr = datetime(year, 4, apr_cal[0][6] if apr_cal[0][6] else apr_cal[1][6], tzinfo=timezone.utc)
    
    if first_sun_oct <= now_utc < first_sun_apr:
        return now_utc.astimezone(timezone(timedelta(hours=11)))
    else:
        return now_utc.astimezone(timezone(timedelta(hours=10)))


def get_available_stock(db: Session, products, exclude_order_id=None):
    """Calculate available stock (total minus reserved in unpicked items of other orders)."""
    reserved_stock = {}
    filter_conditions = [Order.deleted != True]
    if exclude_order_id is not None:
        filter_conditions.append(Order.id != exclude_order_id)
    other_orders = db.query(Order).filter(*filter_conditions).all()
    for other_order in other_orders:
        # Skip fully picked up orders - their stock is no longer reserved
        if other_order.picked_up:
            continue
        for item in other_order.items:
            unpicked = item.quantity - (item.picked_up_quantity or 0)
            if unpicked > 0:
                reserved_stock[item.product_id] = reserved_stock.get(item.product_id, 0) + unpicked
    available_stock = {}
    for product in products:
        available_stock[product.id] = product.quantity - reserved_stock.get(product.id, 0)
    return available_stock


@router.get("/orders/new")
def new_order_page(request: Request):
    db = SessionLocal()
    try:
        customers = db.query(Customer).order_by(Customer.last_name.asc(), Customer.first_name.asc()).all()
        products = (
            db.query(Product)
            .options(joinedload(Product.category), joinedload(Product.subcategory).joinedload(Subcategory.category))
            .filter(Product.quantity > 0)
            .order_by(Product.name.asc())
            .all()
        )
        categories = db.query(Category).order_by(Category.name.asc()).all()
        subcategories = db.query(Subcategory).options(
            joinedload(Subcategory.category)
        ).order_by(Subcategory.category_id.asc(), Subcategory.name.asc()).all()
    finally:
        db.close()
    return templates.TemplateResponse("new_order.html", {
        "request": request,
        "customers": customers,
        "products": products,
        "categories": categories,
        "subcategories": subcategories,
        "error": None,
        "success": None,
    })


@router.post("/orders/new")
def create_order(
    request: Request,
    customer_id: int = Form(...),
    product_ids: list = Form(...),
    quantities: list = Form(...),
    prices: list = Form(...),
    deposit: float = Form(0.0),
    payment_method: str = Form("cash"),
):
    db = SessionLocal()
    try:
        staff_name = get_staff_name(request)
        customer = db.query(Customer).filter(Customer.id == customer_id).first()
        if not customer:
            products = db.query(Product).options(joinedload(Product.category), joinedload(Product.subcategory).joinedload(Subcategory.category)).filter(Product.quantity > 0).order_by(Product.name.asc()).all()
            categories = db.query(Category).order_by(Category.name.asc()).all()
            subcategories = db.query(Subcategory).options(joinedload(Subcategory.category)).order_by(Subcategory.category_id.asc(), Subcategory.name.asc()).all()
            return templates.TemplateResponse("new_order.html", {
                "request": request,
                "customers": db.query(Customer).order_by(Customer.last_name.asc(), Customer.first_name.asc()).all(),
                "products": products,
                "categories": categories,
                "subcategories": subcategories,
                "error": "Customer not found.",
                "success": None,
            })

        # Validate stock availability and aggregate quantities per product
        errors = []
        items_data = []
        product_qty_map = {}  # Aggregate quantities per product across all rows
        for i in range(len(product_ids)):
            # Skip rows where no product was selected (empty product_ids)
            if not product_ids[i] or not str(product_ids[i]).strip():
                continue
            
            try:
                pid = int(product_ids[i])
                qty = int(quantities[i])
                price = float(prices[i])
            except (ValueError, IndexError):
                continue

            if qty <= 0:
                errors.append(f"Quantity must be positive.")
                continue

            product = db.query(Product).filter(Product.id == pid).first()
            if not product:
                errors.append(f"Product not found.")
                continue

            # Aggregate quantity per product across all rows
            product_qty_map[pid] = product_qty_map.get(pid, 0) + qty

            items_data.append({
                "product_id": pid,
                "quantity": qty,
                "unit_price": price,
                "product_name": product.name,
                "max_per_order": product.max_per_order,
            })

        # Check max per order limits against aggregated totals (deduplicate by product)
        checked_products = set()
        for item in items_data:
            pid = item["product_id"]
            if pid in checked_products:
                continue
            checked_products.add(pid)
            total_qty = product_qty_map[pid]
            max_per = item["max_per_order"]
            if max_per and total_qty > max_per:
                errors.append(f"{item['product_name']} has a maximum of {max_per} per order. Total requested: {total_qty}.")

            product = db.query(Product).filter(Product.id == pid).first()
            if product and product.quantity < total_qty:
                errors.append(f"Not enough stock for {item['product_name']}. Available: {product.quantity}, Total requested: {total_qty}.")

        if errors:
            products = db.query(Product).options(joinedload(Product.category), joinedload(Product.subcategory).joinedload(Subcategory.category)).filter(Product.quantity > 0).order_by(Product.name.asc()).all()
            categories = db.query(Category).order_by(Category.name.asc()).all()
            subcategories = db.query(Subcategory).options(joinedload(Subcategory.category)).order_by(Subcategory.category_id.asc(), Subcategory.name.asc()).all()
            return templates.TemplateResponse("new_order.html", {
                "request": request,
                "customers": db.query(Customer).order_by(Customer.last_name.asc(), Customer.first_name.asc()).all(),
                "products": products,
                "categories": categories,
                "subcategories": subcategories,
                "error": "; ".join(errors),
                "success": None,
            })

        if not items_data:
            products = db.query(Product).options(joinedload(Product.category), joinedload(Product.subcategory).joinedload(Subcategory.category)).filter(Product.quantity > 0).order_by(Product.name.asc()).all()
            categories = db.query(Category).order_by(Category.name.asc()).all()
            subcategories = db.query(Subcategory).options(joinedload(Subcategory.category)).order_by(Subcategory.category_id.asc(), Subcategory.name.asc()).all()
            return templates.TemplateResponse("new_order.html", {
                "request": request,
                "customers": db.query(Customer).order_by(Customer.last_name.asc(), Customer.first_name.asc()).all(),
                "products": products,
                "categories": categories,
                "subcategories": subcategories,
                "error": "No valid items to order.",
                "success": None,
            })

        # Create order
        total = sum(item["quantity"] * item["unit_price"] for item in items_data)
        order = Order(customer_id=customer_id, total=total, deposit=deposit, staff_name=staff_name or None)
        db.add(order)
        db.flush()

        # Create order items and deduct stock
        for item in items_data:
            order_item = OrderItem(
                order_id=order.id,
                product_id=item["product_id"],
                quantity=item["quantity"],
                unit_price=item["unit_price"],
            )
            db.add(order_item)

            # Deduct stock
            product = db.query(Product).filter(Product.id == item["product_id"]).first()
            if product:
                product.quantity -= item["quantity"]

        # Log order creation
        log = OrderLog(
            order_id=order.id,
            action=f"Order created. Total: ${total:.2f}, Deposit: ${deposit:.2f}",
            staff_name=staff_name or None,
            timestamp=get_melbourne_time(),
        )
        db.add(log)

        # If deposit > 0, create payment record
        if deposit > 0:
            payment = Payment(
                order_id=order.id,
                amount=deposit,
                payment_type=payment_method or "cash",
                staff_name=staff_name or None,
                timestamp=get_melbourne_time(),
            )
            db.add(payment)

        db.commit()

        # Send email receipt
        try:
            from services.email import send_order_receipt
            if customer.email:
                send_order_receipt(order, db)
        except Exception as e:
            print(f"Failed to send email: {e}")

        return RedirectResponse(url="/orders", status_code=303)

    except Exception as e:
        db.rollback()
        products = db.query(Product).options(joinedload(Product.category), joinedload(Product.subcategory).joinedload(Subcategory.category)).filter(Product.quantity > 0).order_by(Product.name.asc()).all()
        categories = db.query(Category).order_by(Category.name.asc()).all()
        subcategories = db.query(Subcategory).options(joinedload(Subcategory.category)).order_by(Subcategory.category_id.asc(), Subcategory.name.asc()).all()
        return templates.TemplateResponse("new_order.html", {
            "request": request,
            "customers": db.query(Customer).order_by(Customer.last_name.asc(), Customer.first_name.asc()).all(),
            "products": products,
            "categories": categories,
            "subcategories": subcategories,
            "error": str(e),
            "success": None,
        })
    finally:
        db.close()


@router.get("/orders/{order_id}/summary-json")
def get_order_summary_json(order_id: int):
    """AJAX endpoint to get order summary (items, deposit, balance) for the payment modal."""
    db = SessionLocal()
    try:
        order = db.query(Order).options(
            joinedload(Order.customer),
            joinedload(Order.items).joinedload(OrderItem.product)
        ).filter(Order.id == order_id).first()
        if not order:
            return JSONResponse(status_code=404, content={"status": "error", "message": "Order not found."})
        return {
            "status": "success",
            "order_id": order.id,
            "customer_name": order.customer.full_name if order.customer else "Unknown",
            "total": order.total,
            "deposit": order.deposit,
            "balance": order.balance,
            "items": [
                {
                    "item_id": item.id,
                    "product_name": item.product.name if item.product else "Unknown",
                    "quantity": item.quantity,
                    "unit_price": item.unit_price,
                    "subtotal": item.quantity * item.unit_price,
                    "picked_up_quantity": item.picked_up_quantity or 0
                }
                for item in order.items
            ]
        }
    finally:
        db.close()


@router.post("/orders/new-json")
def create_order_json(
    request: Request,
    customer_id: int = Form(...),
    product_ids: list = Form(...),
    quantities: list = Form(...),
    prices: list = Form(...),
    deposit: float = Form(0.0),
    payment_method: str = Form("cash"),
):
    """Create order via AJAX and return JSON with order summary."""
    db = SessionLocal()
    try:
        staff_name = get_staff_name(request)
        customer = db.query(Customer).filter(Customer.id == customer_id).first()
        if not customer:
            return JSONResponse(content={"error": "Customer not found."}, status_code=404)

        # Validate stock availability and aggregate quantities per product
        errors = []
        items_data = []
        product_qty_map = {}  # Aggregate quantities per product across all rows
        for i in range(len(product_ids)):
            # Skip rows where no product was selected (empty product_ids)
            if not product_ids[i] or not str(product_ids[i]).strip():
                continue
            
            try:
                pid = int(product_ids[i])
                qty = int(quantities[i])
                price = float(prices[i])
            except (ValueError, IndexError):
                continue

            if qty <= 0:
                errors.append(f"Quantity must be positive.")
                continue

            product = db.query(Product).filter(Product.id == pid).first()
            if not product:
                errors.append(f"Product not found.")
                continue

            # Aggregate quantity per product across all rows
            product_qty_map[pid] = product_qty_map.get(pid, 0) + qty

            items_data.append({
                "product_id": pid,
                "quantity": qty,
                "unit_price": price,
                "product_name": product.name,
                "max_per_order": product.max_per_order,
            })

        # Check max per order limits against aggregated totals (deduplicate by product)
        checked_products = set()
        for item in items_data:
            pid = item["product_id"]
            if pid in checked_products:
                continue
            checked_products.add(pid)
            total_qty = product_qty_map[pid]
            max_per = item["max_per_order"]
            if max_per and total_qty > max_per:
                errors.append(f"{item['product_name']} has a maximum of {max_per} per order. Total requested: {total_qty}.")

            product = db.query(Product).filter(Product.id == pid).first()
            if product and product.quantity < total_qty:
                errors.append(f"Not enough stock for {item['product_name']}. Available: {product.quantity}, Total requested: {total_qty}.")

        if errors:
            return JSONResponse(content={"error": "; ".join(errors)}, status_code=400)

        if not items_data:
            return JSONResponse(content={"error": "No valid items to order."}, status_code=400)

        # Create order
        total = sum(item["quantity"] * item["unit_price"] for item in items_data)
        order = Order(customer_id=customer_id, total=total, deposit=deposit, staff_name=staff_name or None)
        db.add(order)
        db.flush()

        # Create order items and deduct stock
        for item in items_data:
            order_item = OrderItem(
                order_id=order.id,
                product_id=item["product_id"],
                quantity=item["quantity"],
                unit_price=item["unit_price"],
            )
            db.add(order_item)

            # Deduct stock
            product = db.query(Product).filter(Product.id == item["product_id"]).first()
            if product:
                product.quantity -= item["quantity"]

        # Log order creation
        log = OrderLog(
            order_id=order.id,
            action=f"Order created. Total: ${total:.2f}, Deposit: ${deposit:.2f}",
            staff_name=staff_name or None,
            timestamp=get_melbourne_time(),
        )
        db.add(log)

        # If deposit > 0, create payment record
        if deposit > 0:
            payment = Payment(
                order_id=order.id,
                amount=deposit,
                payment_type=payment_method or "cash",
                staff_name=staff_name or None,
                timestamp=get_melbourne_time(),
            )
            db.add(payment)

        db.commit()

        # Send email receipt
        try:
            from services.email import send_order_receipt
            if customer.email:
                send_order_receipt(order, db)
        except Exception as e:
            print(f"Failed to send email: {e}")

        # Build order summary for the modal
        order_items_summary = []
        for item in items_data:
            order_items_summary.append({
                "name": item["product_name"],
                "quantity": item["quantity"],
                "unit_price": item["unit_price"],
                "subtotal": item["quantity"] * item["unit_price"],
            })

        return JSONResponse(content={
            "order_id": order.id,
            "customer_name": customer.full_name,
            "customer_phone": customer.phone,
            "customer_email": customer.email or "",
            "items": order_items_summary,
            "total": total,
            "deposit": deposit,
            "balance": total - deposit,
            "staff_name": staff_name or "",
        })

    except Exception as e:
        db.rollback()
        return JSONResponse(content={"error": str(e)}, status_code=500)
    finally:
        db.close()



@router.get("/orders/export-pdf")
def export_orders_pdf(
    request: Request,
    order_ids: str = "",
    category_ids: str = "",
    subcategory_ids: str = "",
    customer_search: str = "",
    customer_id: str = "",
    show_deleted: str = "",
    product_id: str = "",
    format: str = "a4",  # "a4" or "labels"
):
    """Export filtered orders as a condensed PDF. If order_ids is provided, export only those specific orders.
    Format: 'a4' for A4 print (10 orders/page with cutting lines), 'labels' for PPS 21UP address labels (63.5x38.1mm)."""
    from models.store_settings import StoreSettings

    db = SessionLocal()
    try:
        # Get store settings
        settings = StoreSettings.get(db)
        store_name = settings.store_name or "TCG Preorder Manager"
        store_address = settings.address or ""
        store_contact = settings.contact_number or ""
        store_email = settings.email or ""
        store_website = settings.website or ""
        store_abn = settings.abn or ""

        # If specific order IDs are provided, fetch only those
        if order_ids.strip():
            ids = [int(c.strip()) for c in order_ids.split(",") if c.strip()]
            if ids:
                orders = db.query(Order).options(
                    joinedload(Order.customer),
                    joinedload(Order.items).joinedload(OrderItem.product).joinedload(Product.category),
                ).filter(Order.id.in_(ids)).order_by(Order.id.desc()).all()
            else:
                orders = []
        else:
            # Build the same query as order_history
            query = db.query(Order).options(
                joinedload(Order.customer),
                joinedload(Order.items).joinedload(OrderItem.product).joinedload(Product.category),
            )

            if not show_deleted:
                query = query.filter(Order.deleted == False)

            if category_ids.strip():
                cat_ids = [int(c.strip()) for c in category_ids.split(",") if c.strip()]
                if cat_ids:
                    query = query.filter(
                        Order.items.any(OrderItem.product.has(Product.category_id.in_(cat_ids)))
                    )

            if subcategory_ids.strip():
                subcat_ids = [int(c.strip()) for c in subcategory_ids.split(",") if c.strip()]
                if subcat_ids:
                    query = query.filter(
                        Order.items.any(OrderItem.product.has(Product.subcategory_id.in_(subcat_ids)))
                    )

            if customer_id.strip():
                query = query.filter(Order.customer_id == int(customer_id.strip()))
            elif customer_search.strip():
                search_term = f"%{customer_search.strip()}%"
                query = query.filter(
                    Order.customer.has(
                        (Customer.first_name.ilike(search_term))
                        | (Customer.last_name.ilike(search_term))
                        | (Customer.phone.ilike(search_term))
                    )
                )

            if product_id.strip():
                query = query.filter(Order.items.any(OrderItem.product_id == int(product_id.strip())))

            orders = query.order_by(Order.deleted.asc(), Order.picked_up.asc(), Order.id.desc()).all()
    finally:
        db.close()

    if format == "labels":
        # PPS 21UP label format: 63.5 x 38.1 mm per label, 3 columns x 7 rows per A4 sheet
        pdf_data = _export_labels_pdf(orders, settings)
    else:
        # A4 Print format: 10 orders per page (2 columns x 5 rows) with cutting lines
        pdf_data = _export_a4_print_pdf(orders, settings)

    return Response(
        content=pdf_data,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename=orders_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
        },
    )


def _export_labels_pdf(orders, settings):
    """Export orders as PPS 21UP address labels (63.5 x 38.1 mm, 3 columns x 7 rows per A4 sheet). Returns bytes."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib.colors import HexColor
    from reportlab.pdfgen import canvas
    from io import BytesIO

    page_width, page_height = A4  # 595.27 x 841.89 points

    # PPS 21UP label dimensions
    label_w = 63.5 * mm  # 177.165 points
    label_h = 38.1 * mm  # 107.724 points

    # Margins for 21UP labels (3 columns, 7 rows)
    left_margin = 7.97 * mm
    top_margin = 14.75 * mm
    col_gap = 1.42 * mm
    row_gap = 0 * mm  # no gap between rows for 21UP

    labels_per_row = 3
    labels_per_col = 7

    store_name = settings.store_name or "TCG Preorder Manager"
    store_contact = settings.contact_number or ""

    # Build PDF using canvas for precise label positioning
    canvas_buf = BytesIO()
    c = canvas.Canvas(canvas_buf, pagesize=A4)

    label_index = 0
    for order in orders:
        # Calculate page and position
        page_num = label_index // (labels_per_row * labels_per_col)
        if page_num > 0:
            c.showPage()

        row = (label_index % (labels_per_row * labels_per_col)) // labels_per_row
        col = label_index % labels_per_row

        x = left_margin + col * (label_w + col_gap)
        y = page_height - top_margin - (row + 1) * (label_h + row_gap)

        customer_name = order.customer.full_name if order.customer else "Unknown"
        customer_phone = order.customer.phone if order.customer else ""
        order_date = order.order_date.strftime("%Y-%m-%d") if order.order_date else ""
        balance = order.total - order.deposit

        if order.is_fully_picked_up:
            status = "PICKED UP"
        elif order.pickup_progress:
            status = f"PARTIAL: {order.pickup_progress}"
        else:
            status = "PENDING"

        # Order number and customer name
        c.setFont("Helvetica-Bold", 7)
        c.drawString(x + 1*mm, y + label_h - 9*mm, f"Order #{order.id} — {customer_name}")

        # Date and phone
        c.setFont("Helvetica", 6)
        date_line = order_date
        if customer_phone:
            date_line += f"  |  {customer_phone}"
        c.drawString(x + 1*mm, y + label_h - 16*mm, date_line)

        # Items
        c.setFont("Helvetica", 5)
        item_names = []
        for item in order.items:
            product_name = item.product.name if item.product else "Unknown"
            picked = item.picked_up_quantity or 0
            item_names.append(f"{product_name} x{item.quantity}({picked})")
        items_text = ", ".join(item_names)
        wrap_y = y + label_h - 22*mm
        max_w = label_w - 2*mm
        line = ""
        for word in items_text.split(", "):
            test = (line + ", " + word) if line else word
            if c.stringWidth(test, "Helvetica", 5) < max_w:
                line = test
            else:
                if line:
                    c.drawString(x + 1*mm, wrap_y, line)
                    wrap_y -= 6*mm
                while c.stringWidth(word, "Helvetica", 5) > max_w and len(word) > 1:
                    word = word[:-1]
                line = word + ".."
        if line:
            c.drawString(x + 1*mm, wrap_y, line)

        # Total, deposit, balance
        c.setFont("Helvetica", 6)
        c.drawString(x + 1*mm, y + label_h - 32*mm, f"Total: ${order.total:.2f}")
        c.drawString(x + label_w/2 - 1*mm, y + label_h - 32*mm, f"Balance: ${balance:.2f}")

        # Status
        if order.is_fully_picked_up:
            c.setFillColor(HexColor("#27ae60"))
        elif order.pickup_progress:
            c.setFillColor(HexColor("#3498db"))
        else:
            c.setFillColor(HexColor("#e67e22"))
        c.setFont("Helvetica-Bold", 6)
        c.drawString(x + 1*mm, y + 2*mm, status)
        c.setFillColor(HexColor("#000000"))

        # Store info
        c.setFont("Helvetica", 5)
        store_line = store_name
        if store_contact:
            store_line += f" | {store_contact}"
        c.drawString(x + 1*mm, y + 8*mm, store_line)

        label_index += 1

    c.save()
    canvas_buf.seek(0)
    return canvas_buf.read()


def _export_a4_print_pdf(orders, settings):
    """Export orders as A4 print format: 10 orders per page (2 columns x 5 rows) with cutting lines. Returns bytes."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib.colors import HexColor
    from reportlab.pdfgen import canvas
    from io import BytesIO

    page_width, page_height = A4  # 595.27 x 841.89 points

    # Layout: 2 columns x 5 rows = 10 orders per page
    cols = 2
    rows_per_page = 5
    orders_per_page = cols * rows_per_page  # 10

    # Page margins
    page_margin_left = 8 * mm
    page_margin_right = 8 * mm
    page_margin_top = 8 * mm
    page_margin_bottom = 8 * mm

    # Order box dimensions with gap between boxes
    box_gap = 1.5 * mm
    box_width = (page_width - page_margin_left - page_margin_right - box_gap) / cols
    box_height = (page_height - page_margin_top - page_margin_bottom - box_gap) / rows_per_page

    canvas_buf = BytesIO()
    c = canvas.Canvas(canvas_buf, pagesize=A4)

    def fit_text(text, font_name, font_size, max_width):
        """Truncate text to fit within max_width without ellipsis."""
        while c.stringWidth(text, font_name, font_size) > max_width and len(text) > 1:
            text = text[:-1]
        return text

    def wrap_text(text, font_name, font_size, max_width):
        """Wrap long text into multiple centered lines that fit within max_width."""
        words = text.split()
        lines = []
        current_line = ""
        for word in words:
            test_line = (current_line + " " + word).strip() if current_line else word
            if c.stringWidth(test_line, font_name, font_size) <= max_width:
                current_line = test_line
            else:
                if current_line:
                    lines.append(current_line)
                if c.stringWidth(word, font_name, font_size) > max_width:
                    while c.stringWidth(word, font_name, font_size) > max_width and len(word) > 1:
                        word = word[:-1]
                    lines.append(word)
                    current_line = ""
                    continue
                current_line = word
        if current_line:
            lines.append(current_line)
        return lines if lines else [text]

    for idx, order in enumerate(orders):
        # New page every 10 orders
        if idx > 0 and idx % orders_per_page == 0:
            c.showPage()

        # Position within page
        pos_in_page = idx % orders_per_page
        col = pos_in_page % cols
        row = pos_in_page // cols

        # Box position (bottom-left origin in reportlab)
        x = page_margin_left + col * (box_width + box_gap)
        y = page_margin_bottom + row * (box_height + box_gap)

        # Draw order box with border
        c.setStrokeColor(HexColor("#cccccc"))
        c.setLineWidth(0.5)
        c.rect(x, y, box_width, box_height, stroke=1, fill=0)

        # Order content
        customer_name = order.customer.full_name if order.customer else "Unknown"

        # Inner padding (5px ≈ 1.76mm)
        pad = 1.76 * mm
        content_width = box_width - (pad * 2)
        center_x = x + box_width / 2  # Center of the box

        # Content boundaries (bottom to top within the box)
        top_edge = y + box_height - pad
        bottom_edge = y + pad

        # --- COUNT TOTAL LINES NEEDED ---
        item_count = len(order.items)
        total_lines = 0
        for item in order.items:
            product_name = item.product.name if item.product else "Unknown"
            item_line = f"({item.quantity}) x {product_name}"
            # Estimate lines at a reasonable font size
            temp_lines = wrap_text(item_line, "Helvetica", 8, content_width)
            total_lines += len(temp_lines)

        # --- DYNAMIC FONT SIZING to fit ALL items ---
        available_height = top_edge - bottom_edge - (16 * 1.5) * mm  # Subtract customer name space
        if total_lines > 0:
            item_line_h = available_height / total_lines
            item_font = max(3, min(14, item_line_h / (1.3 * mm)))
        else:
            item_font = 14
            item_line_h = item_font * 1.3 * mm

        # Recalculate name font based on item count
        if item_count <= 1:
            name_font = 16
        elif item_count <= 3:
            name_font = 14
        else:
            name_font = 12

        # --- DRAW CUSTOMER NAME at top ---
        c.setFillColor(HexColor("#000000"))
        c.setFont("Helvetica-Bold", name_font)
        name_y = top_edge - 3*mm
        c.drawCentredString(center_x, name_y, fit_text(customer_name, "Helvetica-Bold", name_font, content_width))

        # --- DRAW ITEMS below the name ---
        c.setFont("Helvetica", item_font)
        current_y = name_y - (name_font * 1.5) * mm

        for item in order.items:
            product_name = item.product.name if item.product else "Unknown"
            item_line = f"({item.quantity}) x {product_name}"
            # Wrap long item names into multiple lines
            wrapped_lines = wrap_text(item_line, "Helvetica", item_font, content_width)
            for line in reversed(wrapped_lines):
                c.drawCentredString(center_x, current_y, line)
                current_y -= item_line_h

        # Cutting lines (dashed) between boxes
        c.setStrokeColor(HexColor("#999999"))
        c.setLineWidth(0.3)
        c.setDash(2, 2)
        if row < rows_per_page - 1:
            c.line(x, y + box_height, x + box_width, y + box_height)
        if col < cols - 1:
            c.line(x + box_width, y, x + box_width, y + box_height)
        c.setDash([])
        c.setStrokeColor(HexColor("#000000"))

    c.save()
    canvas_buf.seek(0)
    return canvas_buf.read()


@router.get("/orders/{order_id}")
def order_detail_page(request: Request, order_id: int):
    db = SessionLocal()
    try:
        order = (
            db.query(Order)
            .options(
                joinedload(Order.customer),
                joinedload(Order.items).joinedload(OrderItem.product).joinedload(Product.subcategory).joinedload(Subcategory.category),
                joinedload(Order.payments),
            )
            .filter(Order.id == order_id)
            .first()
        )
        if not order:
            return templates.TemplateResponse("orders.html", {
                "request": request,
                "orders": [],
            })

        customers = db.query(Customer).order_by(Customer.last_name.asc(), Customer.first_name.asc()).all()
        products = (
            db.query(Product)
            .options(joinedload(Product.category), joinedload(Product.subcategory).joinedload(Subcategory.category))
            .order_by(Product.name.asc())
            .all()
        )
        categories = db.query(Category).order_by(Category.name.asc()).all()
        subcategories = db.query(Subcategory).options(
            joinedload(Subcategory.category)
        ).order_by(Subcategory.category_id.asc(), Subcategory.name.asc()).all()
        payments = db.query(Payment).filter(Payment.order_id == order_id).order_by(Payment.timestamp.desc()).all()
        logs = db.query(OrderLog).filter(OrderLog.order_id == order_id).order_by(OrderLog.timestamp.desc()).all()
        notes = db.query(OrderNote).filter(OrderNote.order_id == order_id).order_by(OrderNote.created_at.desc()).all()
        
        # Calculate available stock (total minus reserved in other orders)
        available_stock = get_available_stock(db, products, exclude_order_id=order_id)
    finally:
        db.close()
    return templates.TemplateResponse("order_detail.html", {
        "request": request,
        "order": order,
        "customers": customers,
        "products": products,
        "categories": categories,
        "subcategories": subcategories,
        "payments": payments,
        "logs": logs,
        "notes": notes,
        "error": None,
        "success": None,
        "stock_warnings": [],
        "available_stock": available_stock,
    })


@router.post("/orders/{order_id}")
async def update_order(
    request: Request,
    order_id: int,
):
    db = SessionLocal()
    try:
        # Read all form data at once (including picked_up_{item_id} fields)
        form_data = await request.form()
        
        # Extract required fields from form data
        customer_id = int(form_data.get("customer_id", 0))
        staff_name = form_data.get("staff_name", "").strip()
        deposit_str = form_data.get("deposit", "0")
        try:
            deposit = float(deposit_str) if deposit_str else 0.0
        except (ValueError, TypeError):
            deposit = 0.0
        
        # Get product_ids, quantities, prices as lists (FormData doesn't have getlist)
        product_ids = [v for k, v in form_data.multi_items() if k == "product_ids"]
        quantities = [v for k, v in form_data.multi_items() if k == "quantities"]
        prices = [v for k, v in form_data.multi_items() if k == "prices"]
        
        if not staff_name:
            order = db.query(Order).filter(Order.id == order_id).first()
            customers = db.query(Customer).order_by(Customer.last_name.asc(), Customer.first_name.asc()).all()
            products = db.query(Product).options(joinedload(Product.category), joinedload(Product.subcategory).joinedload(Subcategory.category)).order_by(Product.name.asc()).all()
            categories = db.query(Category).order_by(Category.name.asc()).all()
            subcategories = db.query(Subcategory).options(joinedload(Subcategory.category)).order_by(Subcategory.category_id.asc(), Subcategory.name.asc()).all()
            payments = db.query(Payment).filter(Payment.order_id == order_id).order_by(Payment.timestamp.desc()).all()
            available_stock = get_available_stock(db, products, exclude_order_id=order_id)
            return templates.TemplateResponse("order_detail.html", {
                "request": request,
                "order": order,
                "customers": customers,
                "products": products,
                "categories": categories,
                "subcategories": subcategories,
                "payments": payments,
                "error": "Staff name is required.",
                "success": None,
                "stock_warnings": [],
                "available_stock": available_stock,
            })
        order = (
            db.query(Order)
            .options(
                joinedload(Order.customer),
                joinedload(Order.items).joinedload(OrderItem.product),
            )
            .filter(Order.id == order_id)
            .first()
        )
        if not order:
            return templates.TemplateResponse("orders.html", {
                "request": request,
                "orders": [],
            })

        customers = db.query(Customer).order_by(Customer.last_name.asc(), Customer.first_name.asc()).all()
        products = (
            db.query(Product)
            .options(joinedload(Product.category), joinedload(Product.subcategory).joinedload(Subcategory.category))
            .order_by(Product.name.asc())
            .all()
        )
        categories = db.query(Category).order_by(Category.name.asc()).all()
        subcategories = db.query(Subcategory).options(
            joinedload(Subcategory.category)
        ).order_by(Subcategory.category_id.asc(), Subcategory.name.asc()).all()
        available_stock = get_available_stock(db, products, exclude_order_id=order_id)

        # Validate inputs and aggregate quantities per product
        errors = []
        stock_warnings = []
        items_data = []
        product_qty_map = {}  # Aggregate quantities per product across all rows
        for i in range(len(product_ids)):
            pid = int(product_ids[i])
            qty = int(quantities[i])
            price = float(prices[i])

            if qty < 0:
                errors.append(f"Quantity cannot be negative.")
                continue

            if qty == 0:
                # Skip zero-quantity items (effectively removing them)
                continue

            product = db.query(Product).filter(Product.id == pid).first()
            if not product:
                errors.append(f"Product not found.")
                continue

            # Aggregate quantity per product across all rows
            product_qty_map[pid] = product_qty_map.get(pid, 0) + qty

            items_data.append({
                "product_id": pid,
                "quantity": qty,
                "unit_price": price,
                "product_name": product.name,
                "max_per_order": product.max_per_order,
            })

        # Check max per order limits against aggregated totals (deduplicate by product)
        checked_products = set()
        for item in items_data:
            pid = item["product_id"]
            if pid in checked_products:
                continue
            checked_products.add(pid)
            total_qty = product_qty_map[pid]
            max_per = item["max_per_order"]
            if max_per and total_qty > max_per:
                errors.append(f"{item['product_name']} has a maximum of {max_per} per order. Total requested: {total_qty}.")

            product = db.query(Product).filter(Product.id == pid).first()
            if product and product.quantity < total_qty:
                stock_warnings.append(f"Not enough stock for {item['product_name']}. Available: {product.quantity}, Total requested: {total_qty}.")

        if errors:
            payments = db.query(Payment).filter(Payment.order_id == order_id).order_by(Payment.timestamp.desc()).all()
            return templates.TemplateResponse("order_detail.html", {
                "request": request,
                "order": order,
                "customers": customers,
                "products": products,
                "categories": categories,
                "subcategories": subcategories,
                "payments": payments,
                "error": "; ".join(errors),
                "success": None,
                "stock_warnings": stock_warnings,
                "available_stock": available_stock,
            })

        if not items_data:
            payments = db.query(Payment).filter(Payment.order_id == order_id).order_by(Payment.timestamp.desc()).all()
            return templates.TemplateResponse("order_detail.html", {
                "request": request,
                "order": order,
                "customers": customers,
                "products": products,
                "categories": categories,
                "subcategories": subcategories,
                "payments": payments,
                "error": "No valid items to order.",
                "success": None,
                "stock_warnings": stock_warnings,
                "available_stock": available_stock,
            })

        if stock_warnings:
            payments = db.query(Payment).filter(Payment.order_id == order_id).order_by(Payment.timestamp.desc()).all()
            return templates.TemplateResponse("order_detail.html", {
                "request": request,
                "order": order,
                "customers": customers,
                "products": products,
                "categories": categories,
                "subcategories": subcategories,
                "payments": payments,
                "error": None,
                "success": None,
                "stock_warnings": stock_warnings,
                "available_stock": available_stock,
            })

        # Build mapping of old item product_ids to their pickup quantities
        # Also track which items had pickup changes for the note
        old_pickup_by_product = {}
        pickup_changes = []
        for item in order.items:
            key = f"picked_up_{item.id}"
            if key in form_data:
                try:
                    picked_qty = int(form_data[key])
                except (ValueError, TypeError):
                    picked_qty = 0
            else:
                picked_qty = item.picked_up_quantity or 0
            old_pickup_by_product[item.product_id] = picked_qty
            old_picked = item.picked_up_quantity or 0
            if picked_qty != old_picked:
                pickup_changes.append({
                    "product_id": item.product_id,
                    "product_name": item.product.name if item.product else f"Item #{item.id}",
                    "old_picked": old_picked,
                    "new_picked": picked_qty,
                    "unit_price": item.unit_price,
                })

        # Check deposit covers the value of items being newly picked up
        total_value_being_picked = sum(
            (ch["new_picked"] - ch["old_picked"]) * ch["unit_price"]
            for ch in pickup_changes
            if ch["new_picked"] > ch["old_picked"]
        )
        if total_value_being_picked > 0:
            previously_picked_value = sum(
                (item.picked_up_quantity or 0) * item.unit_price
                for item in order.items
            )
            available_deposit = order.deposit - previously_picked_value
            if total_value_being_picked > available_deposit + 0.01:
                payments = db.query(Payment).filter(Payment.order_id == order_id).order_by(Payment.timestamp.desc()).all()
                return templates.TemplateResponse("order_detail.html", {
                    "request": request,
                    "order": order,
                    "customers": customers,
                    "products": products,
                    "categories": categories,
                    "subcategories": subcategories,
                    "payments": payments,
                    "error": f"Insufficient deposit! Items being picked up total ${total_value_being_picked:.2f}, but only ${max(0, available_deposit):.2f} of deposit remains available. Please add a payment before picking up these items.",
                    "success": None,
                    "stock_warnings": stock_warnings,
                    "available_stock": available_stock,
                })
        
        # Calculate the stock difference: restore old stock and deduct new stock
        old_items = order.items
        for old_item in old_items:
            # Restore stock from old items
            product = db.query(Product).filter(Product.id == old_item.product_id).first()
            if product:
                product.quantity += old_item.quantity

        # Clear old items
        for old_item in old_items:
            db.delete(old_item)
        db.flush()

        # Create new items and deduct stock
        total = 0
        for item in items_data:
            # Restore pickup quantity from old item with same product_id
            picked_qty = old_pickup_by_product.get(item["product_id"], 0)
            picked_qty = min(picked_qty, item["quantity"])  # clamp to new quantity
            
            order_item = OrderItem(
                order_id=order.id,
                product_id=item["product_id"],
                quantity=item["quantity"],
                unit_price=item["unit_price"],
                picked_up_quantity=picked_qty,
            )
            db.add(order_item)
            total += item["quantity"] * item["unit_price"]

            # Deduct stock
            product = db.query(Product).filter(Product.id == item["product_id"]).first()
            if product:
                product.quantity -= item["quantity"]

        # Update order
        order.customer_id = customer_id
        order.total = total
        order.deposit = deposit
        order.staff_name = staff_name or order.staff_name
        
        # Update picked_up based on item-level pickup status
        old_picked_up = order.picked_up
        order.picked_up = order.is_fully_picked_up

        # Log the update
        update_actions = [f"Order updated. Total: ${total:.2f}, Deposit: ${deposit:.2f}"]
        if old_picked_up != order.picked_up:
            if order.picked_up:
                update_actions.append("Order fully picked up!")
            else:
                update_actions.append("Order marked as not fully picked up")
        
        log = OrderLog(
            order_id=order.id,
            action="; ".join(update_actions),
            staff_name=staff_name or None,
            timestamp=get_melbourne_time(),
        )
        db.add(log)

        # If pickup quantities changed, add a note in the Notes section
        if pickup_changes:
            note_lines = []
            for ch in pickup_changes:
                product_name = ch['product_name']
                new_picked = ch['new_picked']
                # Find the new order item to get the current quantity
                for item in order.items:
                    if item.product_id == ch['product_id']:
                        total_qty = item.quantity
                        if new_picked == total_qty:
                            note_lines.append(f"✓ {product_name} ({new_picked}/{total_qty} picked up)")
                        elif new_picked > 0:
                            note_lines.append(f"⏳ {product_name} ({new_picked}/{total_qty} picked up)")
                        else:
                            note_lines.append(f"✗ {product_name} ({new_picked}/{total_qty} picked up)")
                        break
            note_text = "Pickup updated:\n" + "\n".join(note_lines)
            note = OrderNote(
                order_id=order.id,
                text=note_text,
                staff_name=staff_name or None,
                created_at=get_melbourne_time(),
            )
            db.add(note)

        db.commit()

        updated_products = (
            db.query(Product)
            .options(joinedload(Product.category), joinedload(Product.subcategory).joinedload(Subcategory.category))
            .order_by(Product.name.asc())
            .all()
        )
        updated_available_stock = get_available_stock(db, updated_products, exclude_order_id=order_id)
        payments = db.query(Payment).filter(Payment.order_id == order_id).order_by(Payment.timestamp.desc()).all()
        return templates.TemplateResponse("order_detail.html", {
            "request": request,
            "order": order,
            "customers": customers,
            "products": updated_products,
            "categories": categories,
            "subcategories": subcategories,
            "payments": payments,
            "error": None,
            "success": "Order updated successfully!",
            "stock_warnings": [],
            "available_stock": updated_available_stock,
        })

    except Exception as e:
        db.rollback()
        customers = db.query(Customer).order_by(Customer.last_name.asc(), Customer.first_name.asc()).all()
        products = (
            db.query(Product)
            .options(joinedload(Product.category), joinedload(Product.subcategory).joinedload(Subcategory.category))
            .order_by(Product.name.asc())
            .all()
        )
        categories = db.query(Category).order_by(Category.name.asc()).all()
        subcategories = db.query(Subcategory).options(
            joinedload(Subcategory.category)
        ).order_by(Subcategory.category_id.asc(), Subcategory.name.asc()).all()
        payments = db.query(Payment).filter(Payment.order_id == order_id).order_by(Payment.timestamp.desc()).all()
        available_stock = get_available_stock(db, products, exclude_order_id=order_id)
        return templates.TemplateResponse("order_detail.html", {
            "request": request,
            "order": order,
            "customers": customers,
            "products": products,
            "categories": categories,
            "subcategories": subcategories,
            "payments": payments,
            "error": str(e),
            "success": None,
            "stock_warnings": [],
            "available_stock": available_stock,
        })
    finally:
        db.close()


@router.post("/orders/{order_id}/update-item-pickup")
async def update_item_pickup(request: Request, order_id: int):
    """Update per-item pickup status for an order via AJAX."""
    db = SessionLocal()
    try:
        # Read all form data at once
        form_data = await request.form()
        staff_name = form_data.get("staff_name", "").strip()
        
        if not staff_name:
            return JSONResponse(content={"error": "Staff name is required."}, status_code=400)
        order = (
            db.query(Order)
            .options(
                joinedload(Order.items).joinedload(OrderItem.product),
                joinedload(Order.customer),
            )
            .filter(Order.id == order_id)
            .first()
        )
        if not order:
            return JSONResponse(content={"error": "Order not found."}, status_code=404)

        # Parse item pickup quantities from form data to calculate the value of newly picked up items
        # Form data contains: item_1=2, item_2=0, ... where the value is the count of checked units
        pickup_changes = []  # List of (item, old_qty, new_qty, value_of_newly_picked)
        for item in order.items:
            key = f"item_{item.id}"
            old_picked_up_quantity = item.picked_up_quantity or 0
            # Get the pickup count from form data; default to 0 if not present
            pickup_count = 0
            if key in form_data:
                try:
                    pickup_count = int(form_data[key])
                except (ValueError, TypeError):
                    pickup_count = 0
            # Clamp to valid range
            pickup_count = max(0, min(pickup_count, item.quantity))
            newly_picked = pickup_count - old_picked_up_quantity
            value_of_newly_picked = newly_picked * item.unit_price if newly_picked > 0 else 0
            pickup_changes.append({
                "item": item,
                "old_qty": old_picked_up_quantity,
                "new_qty": pickup_count,
                "value": value_of_newly_picked,
            })

        # Check deposit covers the value of items being newly picked up
        total_value_being_picked = sum(pc["value"] for pc in pickup_changes)
        if total_value_being_picked > 0:
            balance = order.total - order.deposit
            deposit_remaining = order.deposit - (order.total - balance)  # deposit paid minus already picked up value
            # Calculate how much deposit is already consumed by previously picked up items
            previously_picked_value = sum(
                (item.picked_up_quantity or 0) * item.unit_price
                for item in order.items
            )
            available_deposit = order.deposit - previously_picked_value
            if total_value_being_picked > available_deposit + 0.01:
                return JSONResponse(content={
                    "error": f"Insufficient deposit! Items being picked up total ${total_value_being_picked:.2f}, but only ${max(0, available_deposit):.2f} of deposit remains available. Please add a payment before picking up these items.",
                    "deposit": order.deposit,
                    "total": order.total,
                    "balance": order.total - order.deposit,
                    "previously_picked_value": previously_picked_value,
                    "available_deposit": max(0, available_deposit),
                    "value_being_picked": total_value_being_picked,
                }, status_code=400)

        # Apply pickup changes
        changed_items = []
        for pc in pickup_changes:
            item = pc["item"]
            item.picked_up_quantity = pc["new_qty"]
            if pc["new_qty"] != pc["old_qty"]:
                changed_items.append({
                    "product_name": item.product.name if item.product else f"Item #{item.id}",
                    "picked_up": item.is_fully_picked_up,
                })

        # Update the order-level picked_up flag based on whether all items are fully picked up
        old_picked_up = order.picked_up
        order.picked_up = order.is_fully_picked_up

        # Log the change
        if changed_items:
            item_changes = ", ".join(
                f"{ch['product_name']}: {'✓ picked up' if ch['picked_up'] else '✗ not picked up'}"
                for ch in changed_items
            )
            action_parts = [f"Item pickup updated: {item_changes}"]
            if old_picked_up != order.picked_up:
                if order.picked_up:
                    action_parts.append("Order fully picked up!")
                else:
                    action_parts.append("Order marked as not fully picked up")
            log = OrderLog(
                order_id=order.id,
                action="; ".join(action_parts),
                staff_name=staff_name or None,
                timestamp=get_melbourne_time(),
            )
            db.add(log)
            
            # Also add a note in the Notes section summarizing what was picked up
            note_lines = []
            for ch in changed_items:
                product_name = ch['product_name']
                # Find the matching order item to get quantities
                for item in order.items:
                    if (item.product.name if item.product else f"Item #{item.id}") == product_name:
                        picked = item.picked_up_quantity or 0
                        total = item.quantity
                        if picked == total:
                            note_lines.append(f"✓ {product_name} ({picked}/{total} picked up)")
                        elif picked > 0:
                            note_lines.append(f"⏳ {product_name} ({picked}/{total} picked up)")
                        else:
                            note_lines.append(f"✗ {product_name} ({picked}/{total} picked up)")
                        break
            note_text = "Pickup updated:\n" + "\n".join(note_lines)
            note = OrderNote(
                order_id=order.id,
                text=note_text,
                staff_name=staff_name or None,
                created_at=get_melbourne_time(),
            )
            db.add(note)
        db.commit()

        # Build response with all items' pickup status
        items_status = []
        for item in order.items:
            items_status.append({
                "item_id": item.id,
                "product_name": item.product.name if item.product else f"Item #{item.id}",
                "quantity": item.quantity,
                "picked_up_quantity": item.picked_up_quantity or 0,
                "is_fully_picked_up": item.is_fully_picked_up,
            })

        picked, total = order.pickup_progress
        return JSONResponse(content={
            "picked_up": order.picked_up,
            "is_fully_picked_up": order.is_fully_picked_up,
            "pickup_progress": f"{picked}/{total}",
            "items": items_status,
        })
    except Exception as e:
        db.rollback()
        return JSONResponse(content={"error": str(e)}, status_code=500)
    finally:
        db.close()


@router.post("/orders/{order_id}/add-payment")
def add_payment_to_order(
    request: Request,
    order_id: int,
    amount: float = Form(...),
    payment_type: str = Form("cash"),
    staff_name: str = Form(""),
):
    """Add a payment to an order via AJAX from the order history page."""
    db = SessionLocal()
    try:
        if not staff_name.strip():
            staff_name = get_staff_name(request)
        order = db.query(Order).filter(Order.id == order_id).first()
        if not order:
            return JSONResponse(content={"error": "Order not found."}, status_code=404)

        if amount <= 0:
            return JSONResponse(content={"error": "Payment amount must be positive."}, status_code=400)

        # Prevent overpayment: don't allow more money than the outstanding balance
        balance = order.total - order.deposit
        if amount > balance + 0.01:
            return JSONResponse(content={"error": f"Payment exceeds the outstanding balance of ${balance:.2f}."}, status_code=400)

        # Create payment record
        payment = Payment(
            order_id=order_id,
            amount=amount,
            payment_type=payment_type,
            staff_name=staff_name or None,
            timestamp=get_melbourne_time(),
        )
        db.add(payment)

        # Update deposit and balance
        order.deposit += amount
        db.commit()

        # Log the payment
        log = OrderLog(
            order_id=order_id,
            action=f"Payment of ${amount:.2f} ({payment_type}) added. New deposit: ${order.deposit:.2f}",
            staff_name=staff_name or None,
            timestamp=get_melbourne_time(),
        )
        db.add(log)
        db.commit()

        # Send payment receipt email
        try:
            from services.email import send_payment_receipt
            customer = db.query(Customer).filter(Customer.id == order.customer_id).first()
            if customer and customer.email:
                send_payment_receipt(payment, order, db)
        except Exception as e:
            print(f"Failed to send payment receipt: {e}")

        return JSONResponse(content={
            "success": True,
            "new_deposit": order.deposit,
            "new_balance": order.total - order.deposit,
        })
    except Exception as e:
        db.rollback()
        return JSONResponse(content={"error": str(e)}, status_code=500)
    finally:
        db.close()


@router.post("/orders/{order_id}/delete")
def delete_order(request: Request, order_id: int, staff_name: str = Form("")):
    db = SessionLocal()
    try:
        if not staff_name.strip():
            staff_name = get_staff_name(request)

        order = (
            db.query(Order)
            .options(joinedload(Order.items))
            .filter(Order.id == order_id)
            .first()
        )
        if not order:
            return RedirectResponse(url="/orders", status_code=303)

        # Restore stock
        for item in order.items:
            product = db.query(Product).filter(Product.id == item.product_id).first()
            if product:
                product.quantity += item.quantity

        # Soft delete — mark as deleted instead of removing
        order.deleted = True

        # Log the deletion
        log = OrderLog(
            order_id=order_id,
            action=f"Order soft-deleted. Total: ${order.total:.2f}",
            staff_name=staff_name.strip(),
            timestamp=get_melbourne_time(),
        )
        db.add(log)
        db.commit()

    except Exception as e:
        db.rollback()
    finally:
        db.close()

    return RedirectResponse(url="/orders", status_code=303)


@router.post("/orders/{order_id}/delete-json")
def delete_order_json(request: Request, order_id: int, staff_name: str = Form("")):
    """AJAX endpoint for soft-deleting an order with confirmation modal."""
    db = SessionLocal()
    try:
        if not staff_name.strip():
            staff_name = get_staff_name(request)

        order = (
            db.query(Order)
            .options(joinedload(Order.items))
            .filter(Order.id == order_id)
            .first()
        )
        if not order:
            return JSONResponse(content={"error": "Order not found."}, status_code=404)

        # Restore stock
        for item in order.items:
            product = db.query(Product).filter(Product.id == item.product_id).first()
            if product:
                product.quantity += item.quantity

        # Soft delete
        order.deleted = True

        # Log the deletion
        log = OrderLog(
            order_id=order_id,
            action=f"Order soft-deleted. Total: ${order.total:.2f}",
            staff_name=staff_name.strip(),
            timestamp=get_melbourne_time(),
        )
        db.add(log)
        db.commit()

        return JSONResponse(content={"success": True, "order_id": order_id})
    except Exception as e:
        db.rollback()
        return JSONResponse(content={"error": str(e)}, status_code=500)
    finally:
        db.close()


@router.post("/orders/{order_id}/restore")
def restore_order(request: Request, order_id: int, staff_name: str = Form("")):
    """Restore a soft-deleted order."""
    db = SessionLocal()
    try:
        if not staff_name.strip():
            staff_name = get_staff_name(request)

        order = (
            db.query(Order)
            .options(joinedload(Order.items))
            .filter(Order.id == order_id)
            .first()
        )
        if not order:
            return JSONResponse(content={"error": "Order not found."}, status_code=404)

        if not order.deleted:
            return JSONResponse(content={"error": "Order is not deleted."}, status_code=400)

        # Deduct stock again when restoring
        for item in order.items:
            product = db.query(Product).filter(Product.id == item.product_id).first()
            if product:
                product.quantity -= item.quantity

        order.deleted = False

        # Log the restoration
        log = OrderLog(
            order_id=order_id,
            action=f"Order restored. Total: ${order.total:.2f}",
            staff_name=staff_name.strip(),
            timestamp=get_melbourne_time(),
        )
        db.add(log)
        db.commit()

        return JSONResponse(content={"success": True, "order_id": order_id})
    except Exception as e:
        db.rollback()
        return JSONResponse(content={"error": str(e)}, status_code=500)
    finally:
        db.close()


@router.get("/orders")
def order_history(request: Request, category_ids: str = "", subcategory_ids: str = "", customer_search: str = "", customer_id: str = "", show_deleted: str = "", product_id: str = ""):
    db = SessionLocal()
    try:
        query = (
            db.query(Order)
            .options(
                joinedload(Order.customer),
                joinedload(Order.items).joinedload(OrderItem.product).joinedload(Product.category),
            )
        )

        # By default, filter out soft-deleted orders unless show_deleted is set
        if not show_deleted:
            query = query.filter(Order.deleted == False)

        # Filter by multiple categories if specified (comma-separated IDs)
        if category_ids.strip():
            cat_ids = [int(c.strip()) for c in category_ids.split(",") if c.strip()]
            if cat_ids:
                query = query.filter(
                    Order.items.any(
                        OrderItem.product.has(Product.category_id.in_(cat_ids))
                    )
                )

        # Filter by multiple Set Names if specified (comma-separated IDs)
        if subcategory_ids.strip():
            subcat_ids = [int(c.strip()) for c in subcategory_ids.split(",") if c.strip()]
            if subcat_ids:
                query = query.filter(
                    Order.items.any(
                        OrderItem.product.has(Product.subcategory_id.in_(subcat_ids))
                    )
                )

        # Filter by exact customer ID (from "View Orders" link on customers page)
        if customer_id.strip():
            query = query.filter(Order.customer_id == int(customer_id.strip()))

        # Filter by customer name search (first_name or last_name)
        elif customer_search.strip():
            search_term = f"%{customer_search.strip()}%"
            query = query.filter(
                Order.customer.has(
                    (Customer.first_name.ilike(search_term))
                    | (Customer.last_name.ilike(search_term))
                    | (Customer.phone.ilike(search_term))
                )
            )

        # Filter by product ID (orders containing a specific item)
        if product_id.strip():
            query = query.filter(Order.items.any(OrderItem.product_id == int(product_id.strip())))

        # Sort: deleted orders at bottom, then non-picked-up first, then picked-up
        orders = query.order_by(Order.deleted.asc(), Order.picked_up.asc(), Order.id.desc()).all()
        categories = db.query(Category).order_by(Category.name.asc()).all()
        subcategories = db.query(Subcategory).options(
            joinedload(Subcategory.category)
        ).order_by(Subcategory.category_id.asc(), Subcategory.name.asc()).all()
        customers = db.query(Customer).order_by(Customer.last_name.asc(), Customer.first_name.asc()).all()
        products = db.query(Product).order_by(Product.name.asc()).all()
        selected_categories = [int(c.strip()) for c in category_ids.split(",") if c.strip()] if category_ids.strip() else []
        selected_subcategories = [int(c.strip()) for c in subcategory_ids.split(",") if c.strip()] if subcategory_ids.strip() else []
        
        # Get selected product name for display
        selected_product_name = ""
        if product_id.strip():
            prod = db.query(Product).filter(Product.id == int(product_id.strip())).first()
            if prod:
                selected_product_name = prod.name
    finally:
        db.close()
    return templates.TemplateResponse("orders.html", {
        "request": request,
        "orders": orders,
        "categories": categories,
        "subcategories": subcategories,
        "customers": customers,
        "products": products,
        "selected_categories": selected_categories,
        "selected_subcategories": selected_subcategories,
        "customer_search": customer_search,
        "customer_id": customer_id,
        "product_id": product_id,
        "selected_product_name": selected_product_name,
        "show_deleted": bool(show_deleted),
    })


@router.post("/orders/{order_id}/add-note")
def add_note_to_order(request: Request, order_id: int, note_text: str = Form(...), staff_name: str = Form("")):
    """Add a note to an order via AJAX."""
    db = SessionLocal()
    try:
        if not staff_name.strip():
            staff_name = get_staff_name(request)
        order = db.query(Order).filter(Order.id == order_id).first()
        if not order:
            return JSONResponse(content={"error": "Order not found."}, status_code=404)

        note = OrderNote(
            order_id=order_id,
            text=note_text.strip(),
            staff_name=staff_name.strip() if staff_name else None,
            created_at=get_melbourne_time(),
        )
        db.add(note)
        db.commit()
        db.refresh(note)

        return JSONResponse(content={
            "success": True,
            "note": {
                "id": note.id,
                "text": note.text,
                "staff_name": note.staff_name or "-",
                "created_at": note.created_at.strftime('%Y-%m-%d %H:%M'),
            }
        })
    except Exception as e:
        db.rollback()
        return JSONResponse(content={"error": str(e)}, status_code=500)
    finally:
        db.close()


@router.post("/orders/{order_id}/delete-note/{note_id}")
def delete_note_from_order(request: Request, order_id: int, note_id: int):
    """Delete a note from an order via AJAX."""
    db = SessionLocal()
    try:
        note = db.query(OrderNote).filter(OrderNote.id == note_id, OrderNote.order_id == order_id).first()
        if not note:
            return JSONResponse(content={"error": "Note not found."}, status_code=404)

        db.delete(note)
        db.commit()

        return JSONResponse(content={"success": True})
    except Exception as e:
        db.rollback()
        return JSONResponse(content={"error": str(e)}, status_code=500)
    finally:
        db.close()
