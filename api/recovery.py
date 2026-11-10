"""API routes for PIN recovery system."""
import hashlib
import secrets

from fastapi import APIRouter, Request, Form
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from models.base import SessionLocal
from models.store_settings import StoreSettings
from models.staff import Staff
from services.audit import log_change

router = APIRouter()
templates: Jinja2Templates = None  # type: ignore[assignment]


def _generate_recovery_token() -> str:
    """Generate a random recovery token (32 hex chars = 16 bytes)."""
    return secrets.token_hex(16)


def _hash_token(token: str) -> str:
    """Hash a recovery token using SHA-256."""
    return hashlib.sha256(token.encode()).hexdigest()


def _verify_token(token: str, token_hash: str) -> bool:
    """Verify a recovery token against its stored hash."""
    if not token_hash:
        return False
    return _hash_token(token.strip()) == token_hash


@router.get("/recovery")
def recovery_page(request: Request, error: str = ""):
    """Display the PIN recovery page."""
    return templates.TemplateResponse("recovery.html", {
        "request": request,
        "error": error,
    })


@router.post("/recovery/verify")
def verify_recovery_token(request: Request, token: str = Form(...)):
    """Verify the recovery token and redirect to reset page if valid."""
    db = SessionLocal()
    try:
        settings = StoreSettings.get(db)
        if not settings.recovery_token_hash:
            return templates.TemplateResponse("recovery.html", {
                "request": request,
                "error": "Recovery is not enabled. No recovery token has been set.",
            })

        if not _verify_token(token, settings.recovery_token_hash):
            return templates.TemplateResponse("recovery.html", {
                "request": request,
                "error": "Invalid recovery token. Please check and try again.",
            })

        # Token is valid — store a flag in session to allow reset
        request.session["recovery_verified"] = True
        return RedirectResponse(url="/recovery/reset", status_code=302)
    finally:
        db.close()


@router.get("/recovery/reset")
def recovery_reset_page(request: Request, error: str = ""):
    """Display the PIN reset page (only accessible after token verification)."""
    if not request.session.get("recovery_verified"):
        return RedirectResponse(url="/recovery", status_code=302)

    db = SessionLocal()
    try:
        staff_list = db.query(Staff).all()
        return templates.TemplateResponse("recovery_reset.html", {
            "request": request,
            "staff_list": staff_list,
            "error": error,
        })
    finally:
        db.close()


@router.post("/recovery/reset")
async def reset_pins(request: Request):
    """Reset all staff PINs or individual staff PINs based on the action."""
    if not request.session.get("recovery_verified"):
        return RedirectResponse(url="/recovery", status_code=302)

    form = await request.form()
    action = form.get("action", "")

    db = SessionLocal()
    try:
        if action == "reset_all":
            # Generate new random PINs for all staff
            new_pins = {}
            existing_pins = {s.pin for s in db.query(Staff).all()}
            for staff in db.query(Staff).all():
                # Generate a random 4-digit PIN
                new_pin = f"{secrets.randbelow(10000):04d}"
                # Ensure uniqueness
                while new_pin in existing_pins:
                    new_pin = f"{secrets.randbelow(10000):04d}"
                staff.pin = new_pin
                existing_pins.add(new_pin)
                new_pins[staff.name] = new_pin
            db.commit()

            # Invalidate the recovery token after use (one-time use)
            settings = StoreSettings.get(db)
            settings.recovery_token_hash = None
            db.commit()

            log_change("settings", None, "All PINs reset via recovery system", "Recovery System")

            # Clear the recovery session flag
            request.session.pop("recovery_verified", None)

            return templates.TemplateResponse("recovery_complete.html", {
                "request": request,
                "new_pins": new_pins,
                "action": "reset_all",
            })

        elif action == "reset_individual":
            # Reset specific staff PINs
            new_pins = {}
            for staff in db.query(Staff).all():
                pin_key = f"pin_{staff.id}"
                new_pin = form.get(pin_key, "").strip()
                if new_pin and len(new_pin) == 4 and new_pin.isdigit():
                    # Check uniqueness
                    if db.query(Staff).filter(Staff.pin == new_pin, Staff.id != staff.id).first():
                        return templates.TemplateResponse("recovery_reset.html", {
                            "request": request,
                            "staff_list": db.query(Staff).all(),
                            "error": f"PIN {new_pin} is already in use by another staff member.",
                        })
                    staff.pin = new_pin
                    new_pins[staff.name] = new_pin
                elif new_pin:
                    return templates.TemplateResponse("recovery_reset.html", {
                        "request": request,
                        "staff_list": db.query(Staff).all(),
                        "error": f"PIN for {staff.name} must be exactly 4 digits.",
                    })
            db.commit()

            # Invalidate the recovery token after use
            settings = StoreSettings.get(db)
            settings.recovery_token_hash = None
            db.commit()

            log_change("settings", None, "Individual PINs reset via recovery system", "Recovery System")

            request.session.pop("recovery_verified", None)

            return templates.TemplateResponse("recovery_complete.html", {
                "request": request,
                "new_pins": new_pins,
                "action": "reset_individual",
            })

        else:
            return templates.TemplateResponse("recovery_reset.html", {
                "request": request,
                "staff_list": db.query(Staff).all(),
                "error": "Invalid action.",
            })
    finally:
        db.close()


@router.post("/settings/recovery/generate")
def generate_recovery_token(request: Request):
    """Generate a new recovery token. Returns the raw token (shown only once)."""
    from api.auth import has_permission
    if not has_permission(request, "manage_settings"):
        return {"error": "Permission denied."}

    db = SessionLocal()
    try:
        settings = StoreSettings.get(db)
        raw_token = _generate_recovery_token()
        settings.recovery_token_hash = _hash_token(raw_token)
        db.commit()

        log_change("settings", None, "Recovery token generated", request.session.get("staff_name", "Unknown"))

        return {"token": raw_token}
    finally:
        db.close()


@router.post("/settings/recovery/regenerate")
def regenerate_recovery_token(request: Request):
    """Regenerate the recovery token (invalidates the old one)."""
    from api.auth import has_permission
    if not has_permission(request, "manage_settings"):
        return {"error": "Permission denied."}

    db = SessionLocal()
    try:
        settings = StoreSettings.get(db)
        raw_token = _generate_recovery_token()
        settings.recovery_token_hash = _hash_token(raw_token)
        db.commit()

        log_change("settings", None, "Recovery token regenerated (old token invalidated)", request.session.get("staff_name", "Unknown"))

        return {"token": raw_token}
    finally:
        db.close()


@router.post("/settings/recovery/disable")
def disable_recovery_token(request: Request):
    """Disable the recovery token."""
    from api.auth import has_permission
    if not has_permission(request, "manage_settings"):
        return {"error": "Permission denied."}

    db = SessionLocal()
    try:
        settings = StoreSettings.get(db)
        settings.recovery_token_hash = None
        db.commit()

        log_change("settings", None, "Recovery token disabled", request.session.get("staff_name", "Unknown"))

        return {"success": True}
    finally:
        db.close()
