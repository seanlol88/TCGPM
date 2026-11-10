"""API routes for the first-run setup wizard."""
import os
import json

from fastapi import APIRouter, Request, Form, Query
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates

import config
from models.base import SessionLocal
from models.staff import Staff, ADMIN_PERMISSIONS, DEFAULT_PERMISSIONS
from models.store_settings import StoreSettings
from services.audit import log_change

router = APIRouter()
templates: Jinja2Templates = None  # type: ignore[assignment]

# Gmail OAuth2 configuration (reused from gmail.py)
GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.send"]
GMAIL_REDIRECT_URI = "http://localhost:8000/gmail/callback"


def _is_first_run() -> bool:
    """Check if this is the first run (no staff and setup not complete)."""
    db = SessionLocal()
    try:
        settings = StoreSettings.get(db)
        if settings.setup_complete:
            return False
        staff_count = db.query(Staff).count()
        return staff_count == 0
    finally:
        db.close()


@router.get("/setup")
def setup_wizard(request: Request, step: str = "1", error: str = ""):
    """Display the setup wizard page."""
    db = SessionLocal()
    try:
        settings = StoreSettings.get(db)
        # If setup is already complete, redirect to dashboard
        if settings.setup_complete:
            return RedirectResponse(url="/", status_code=302)
        # If setup is not complete, allow the wizard to proceed regardless of staff count
        # (staff may have been created in earlier wizard steps)
    finally:
        db.close()

    # Check Gmail connection status for step display
    gmail_connected = os.path.exists(config.GMAIL_TOKEN_FILE)
    # Check if recovery token already exists
    recovery_token = settings.recovery_token_hash is not None

    return templates.TemplateResponse("setup_wizard.html", {
        "request": request,
        "step": step,
        "error": error,
        "gmail_connected": gmail_connected,
        "recovery_token": recovery_token,
    })


@router.post("/setup/admin-pin")
def setup_admin_pin(request: Request, pin: str = Form(...), pin_confirm: str = Form(...)):
    """Step 1: Create the admin PIN (required)."""
    pin = pin.strip()
    pin_confirm = pin_confirm.strip()

    # Validate PIN format
    if len(pin) != 4 or not pin.isdigit():
        return templates.TemplateResponse("setup_wizard.html", {
            "request": request,
            "step": "1",
            "error": "PIN must be exactly 4 digits.",
            "gmail_connected": os.path.exists(config.GMAIL_TOKEN_FILE),
        })

    if pin != pin_confirm:
        return templates.TemplateResponse("setup_wizard.html", {
            "request": request,
            "step": "1",
            "error": "PINs do not match. Please try again.",
            "gmail_connected": os.path.exists(config.GMAIL_TOKEN_FILE),
        })

    db = SessionLocal()
    try:
        # Check if an admin already exists
        admin = db.query(Staff).filter(Staff.name == "Admin").first()
        if admin:
            # Admin already exists — just update the PIN
            admin.pin = pin
            db.commit()
            log_change("settings", None, "Updated admin PIN during setup wizard", "Admin")
            return RedirectResponse(url="/setup?step=2", status_code=303)

        # Check if PIN is already taken by another staff member
        existing = db.query(Staff).filter(Staff.pin == pin).first()
        if existing:
            return templates.TemplateResponse("setup_wizard.html", {
                "request": request,
                "step": "1",
                "error": "This PIN is already in use.",
                "gmail_connected": os.path.exists(config.GMAIL_TOKEN_FILE),
            })

        # Create the admin staff member
        admin = Staff(
            name="Admin",
            pin=pin,
            active=True,
            permissions=json.dumps(ADMIN_PERMISSIONS),
        )
        db.add(admin)
        db.commit()

        # Log the action
        log_change("settings", None, "Created admin account during setup wizard", "Admin")
    except Exception as e:
        db.rollback()
        return templates.TemplateResponse("setup_wizard.html", {
            "request": request,
            "step": "1",
            "error": f"Error creating admin account: {str(e)}",
            "gmail_connected": os.path.exists(config.GMAIL_TOKEN_FILE),
        })
    finally:
        db.close()

    return RedirectResponse(url="/setup?step=2", status_code=303)


@router.post("/setup/staff")
def setup_staff(request: Request,
                staff_names: str = Form(""),
                staff_pins: str = Form("")):
    """Step 2: Add staff members and their PINs (skippable)."""
    db = SessionLocal()
    try:
        errors = []
        added = 0

        # Parse names and pins (comma or newline separated)
        names = [n.strip() for n in staff_names.split("\n") if n.strip()]
        pins = [p.strip() for p in staff_pins.split("\n") if p.strip()]

        if names and not pins:
            errors.append("Please provide PINs for all staff members.")
        elif pins and not names:
            errors.append("Please provide names for all staff members.")
        elif len(names) != len(pins):
            errors.append(f"Name count ({len(names)}) doesn't match PIN count ({len(pins)}).")
        else:
            for name, pin in zip(names, pins):
                if len(pin) != 4 or not pin.isdigit():
                    errors.append(f"Invalid PIN '{pin}' for {name}.")
                    continue

                existing_pin = db.query(Staff).filter(Staff.pin == pin).first()
                if existing_pin:
                    errors.append(f"PIN '{pin}' is already in use.")
                    continue

                existing_name = db.query(Staff).filter(Staff.name == name).first()
                if existing_name:
                    errors.append(f"Staff member '{name}' already exists.")
                    continue

                staff = Staff(
                    name=name,
                    pin=pin,
                    active=True,
                    permissions=json.dumps(DEFAULT_PERMISSIONS),
                )
                db.add(staff)
                added += 1

        if errors:
            db.rollback()
            return templates.TemplateResponse("setup_wizard.html", {
                "request": request,
                "step": "2",
                "error": "; ".join(errors),
                "gmail_connected": os.path.exists(config.GMAIL_TOKEN_FILE),
            })

        if added:
            db.commit()
            log_change("settings", None, f"Added {added} staff member(s) during setup wizard", "Admin")
    finally:
        db.close()

    return RedirectResponse(url="/setup?step=3", status_code=303)


@router.post("/setup/port")
def setup_port(request: Request, app_port: int = Form(8000)):
    """Step 3: Configure the app port (skippable)."""
    # Validate port range
    if app_port < 1024 or app_port > 65535:
        return templates.TemplateResponse("setup_wizard.html", {
            "request": request,
            "step": "3",
            "error": "Port must be between 1024 and 65535.",
            "gmail_connected": os.path.exists(config.GMAIL_TOKEN_FILE),
        })

    db = SessionLocal()
    try:
        settings = StoreSettings.get(db)
        settings.app_port = app_port
        db.commit()
        log_change("settings", None, f"Set app port to {app_port} during setup wizard", "Admin")
    finally:
        db.close()

    return RedirectResponse(url="/setup?step=4", status_code=303)


@router.post("/setup/store-info")
def setup_store_info(request: Request,
                     store_name: str = Form(""),
                     address: str = Form(""),
                     contact_number: str = Form(""),
                     email: str = Form(""),
                     website: str = Form(""),
                     abn: str = Form("")):
    """Step 4: Set up store name and info (skippable)."""
    db = SessionLocal()
    try:
        settings = StoreSettings.get(db)
        settings.store_name = store_name or None
        settings.address = address or None
        settings.contact_number = contact_number or None
        settings.email = email or None
        settings.website = website or None
        settings.abn = abn or None
        db.commit()
        log_change("settings", None, "Set store information during setup wizard", "Admin")
    finally:
        db.close()

    return RedirectResponse(url="/setup?step=5", status_code=303)


@router.get("/setup/gmail-connect")
def setup_gmail_connect(request: Request):
    """Step 5/6: Start the Gmail OAuth2 flow from the setup wizard."""
    try:
        from google_auth_oauthlib.flow import Flow

        if not os.path.exists(config.GMAIL_CREDENTIALS_FILE):
            return RedirectResponse(
                url="/setup?step=5&error=Gmail credentials file not found.",
                status_code=303,
            )

        flow = Flow.from_client_secrets_file(
            config.GMAIL_CREDENTIALS_FILE,
            scopes=GMAIL_SCOPES,
            redirect_uri=GMAIL_REDIRECT_URI,
        )

        authorization_url, state = flow.authorization_url(
            access_type="offline",
            prompt="consent",
        )

        request.session["gmail_oauth_state"] = state
        request.session["gmail_callback_return"] = "/setup?step=6"  # Step 6 is now Recovery Token

        return RedirectResponse(url=authorization_url, status_code=302)
    except Exception as e:
        return RedirectResponse(
            url=f"/setup?step=5&error=Failed to start Gmail connection: {str(e)}",
            status_code=303,
        )


@router.get("/setup/skip-gmail")
def setup_skip_gmail(request: Request):
    """Skip Gmail connection and go to the recovery token step."""
    return RedirectResponse(url="/setup?step=6", status_code=303)


@router.get("/setup/complete")
def setup_complete(request: Request):
    """Step 7: Mark setup as complete and redirect to login."""
    db = SessionLocal()
    try:
        settings = StoreSettings.get(db)
        settings.setup_complete = True
        db.commit()
        log_change("settings", None, "Completed first-run setup wizard", "Admin")
    finally:
        db.close()

    # Create desktop shortcut
    try:
        from services.desktop_shortcut import create_desktop_shortcut
        create_desktop_shortcut()
    except Exception as e:
        print(f"Warning: Could not create desktop shortcut: {e}")

    return RedirectResponse(url="/login", status_code=302)


@router.post("/setup/recovery/generate")
def setup_generate_recovery_token(request: Request):
    """Generate a recovery token during the setup wizard (no auth required)."""
    import secrets
    import hashlib

    db = SessionLocal()
    try:
        settings = StoreSettings.get(db)
        raw_token = secrets.token_hex(16)
        settings.recovery_token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        db.commit()

        log_change("settings", None, "Recovery token generated during setup wizard", "Setup Wizard")

        return {"token": raw_token}
    finally:
        db.close()


@router.post("/setup/recovery/regenerate")
def setup_regenerate_recovery_token(request: Request):
    """Regenerate a recovery token during the setup wizard (no auth required)."""
    import secrets
    import hashlib

    db = SessionLocal()
    try:
        settings = StoreSettings.get(db)
        raw_token = secrets.token_hex(16)
        settings.recovery_token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        db.commit()

        log_change("settings", None, "Recovery token regenerated during setup wizard", "Setup Wizard")

        return {"token": raw_token}
    finally:
        db.close()


@router.post("/setup/skip-to-complete")
def setup_skip_to_complete(request: Request):
    """Allow skipping remaining steps and completing setup."""
    return RedirectResponse(url="/setup/complete", status_code=303)
