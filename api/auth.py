from fastapi import APIRouter, Request, Form
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from models.base import SessionLocal
from models.staff import Staff
import time

router = APIRouter()
templates: Jinja2Templates = None  # type: ignore[assignment]


def get_current_staff(request: Request):
    """Get the currently logged-in staff member from the session."""
    db = SessionLocal()
    try:
        staff_id = request.session.get("staff_id")
        if staff_id:
            staff = db.query(Staff).filter(Staff.id == staff_id, Staff.active == True).first()
            return staff
        return None
    finally:
        db.close()


def get_global_timeout() -> tuple:
    """Get the global timeout settings from StoreSettings.
    Returns (timeout_enabled, timeout_seconds).
    """
    from models.store_settings import StoreSettings
    db = SessionLocal()
    try:
        settings = StoreSettings.get(db)
        return (settings.timeout_enabled or False, settings.timeout_seconds or 1800)
    finally:
        db.close()


def is_session_expired(request: Request) -> bool:
    """Check if the current session has expired due to inactivity timeout."""
    timeout_enabled, timeout_seconds = get_global_timeout()
    if not timeout_enabled:
        return False
    
    last_activity = request.session.get("last_activity")
    if last_activity is None:
        return False
    
    current_time = time.time()
    return (current_time - last_activity) > timeout_seconds


def update_last_activity(request: Request):
    """Update the last activity timestamp in the session."""
    request.session["last_activity"] = time.time()


def get_staff_name(request: Request) -> str:
    """Get the current staff name from the session for use in audit logs.
    
    Returns the staff name from the session, falling back to the DB lookup if needed.
    """
    # Fast path: check session cache
    name = request.session.get("staff_name")
    if name:
        return name
    # Fallback: look up from DB
    staff = get_current_staff(request)
    if staff:
        return staff.name
    return "Unknown"


def get_staff_permissions(request: Request) -> dict:
    """Get the current staff member's permissions dict."""
    db = SessionLocal()
    try:
        staff_id = request.session.get("staff_id")
        if staff_id:
            staff = db.query(Staff).filter(Staff.id == staff_id, Staff.active == True).first()
            if staff:
                return staff.get_permissions()
        return {}
    finally:
        db.close()


def has_permission(request: Request, permission_key: str) -> bool:
    """Check if the current staff member has a specific permission."""
    perms = get_staff_permissions(request)
    return perms.get(permission_key, False)


def require_permission(request: Request, permission_key: str):
    """Return a 403 RedirectResponse if the current staff member lacks the permission."""
    if not has_permission(request, permission_key):
        return RedirectResponse(url="/?error=Permission denied.", status_code=303)
    return None


@router.get("/login")
def login_page(request: Request, error: str = "", timeout: str = ""):
    """Display the login page."""
    # If already logged in, redirect to dashboard
    staff = get_current_staff(request)
    if staff:
        return RedirectResponse(url="/", status_code=302)
    return templates.TemplateResponse("login.html", {
        "request": request,
        "error": error,
        "timeout": timeout == "1",
    })


@router.post("/login")
def login(request: Request, pin: str = Form(...)):
    """Authenticate staff member with 4-digit PIN."""
    db = SessionLocal()
    try:
        # Validate PIN format
        pin = pin.strip()
        if len(pin) != 4 or not pin.isdigit():
            return templates.TemplateResponse("login.html", {
                "request": request,
                "error": "PIN must be exactly 4 digits.",
            })
        
        # Find staff with matching PIN who is active
        staff = db.query(Staff).filter(Staff.pin == pin, Staff.active == True).first()
        if staff:
            request.session["staff_id"] = staff.id
            request.session["staff_name"] = staff.name
            request.session["last_activity"] = time.time()
            return RedirectResponse(url="/", status_code=302)
        else:
            return templates.TemplateResponse("login.html", {
                "request": request,
                "error": "Invalid PIN. Please try again.",
            })
    finally:
        db.close()


@router.get("/logout")
def logout(request: Request):
    """Log out the current staff member."""
    request.session.clear()
    return RedirectResponse(url="/login", status_code=302)


@router.get("/auth/check")
def auth_check(request: Request):
    """API endpoint to check if user is authenticated (returns JSON)."""
    staff = get_current_staff(request)
    if staff:
        return {"authenticated": True, "staff_name": staff.name, "staff_id": staff.id}
    else:
        return {"authenticated": False, "staff_name": None, "staff_id": None}
