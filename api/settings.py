from fastapi import APIRouter, Request, Form, UploadFile, File
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from models.base import SessionLocal
from models.store_settings import StoreSettings
from services.audit import log_change
import os
import urllib.request
import json
import config

router = APIRouter()
templates: Jinja2Templates = None  # type: ignore[assignment]

# Directory for uploaded logos
LOGO_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static", "logos")


def ensure_logo_dir():
    os.makedirs(LOGO_DIR, exist_ok=True)


@router.get("/settings")
def get_settings(request: Request):
    db = SessionLocal()
    try:
        settings = StoreSettings.get(db)
        return templates.TemplateResponse("settings.html", {
            "request": request,
            "settings": settings,
        })
    finally:
        db.close()


@router.post("/settings")
def update_settings(
    request: Request,
    logo: UploadFile = File(None),
    store_name: str = Form(""),
    address: str = Form(""),
    contact_number: str = Form(""),
    email: str = Form(""),
    website: str = Form(""),
    abn: str = Form(""),
    gmail_sender_email: str = Form(""),
    logo_size: int = Form(40),
    primary_color: str = Form("#3b82f6"),
    secondary_color: str = Form("#6b7280"),
    background_color: str = Form("#f9fafb"),
    text_color: str = Form("#111827"),
    nav_bg_color: str = Form("#1e293b"),
    nav_text_color: str = Form("#f8fafc"),
    card_bg_color: str = Form("#ffffff"),
    border_color: str = Form("#e5e7eb"),
):
    db = SessionLocal()
    try:
        settings = StoreSettings.get(db)
        settings.store_name = store_name.strip() or None
        settings.address = address.strip() or None
        settings.contact_number = contact_number.strip() or None
        settings.email = email.strip() or None
        settings.website = website.strip() or None
        settings.abn = abn.strip() or None
        settings.gmail_sender_email = gmail_sender_email.strip() or None
        settings.logo_size = min(max(logo_size, 20), 80)  # Clamp between 20 and 80
        settings.primary_color = primary_color.strip() or "#3b82f6"
        settings.secondary_color = secondary_color.strip() or "#6b7280"
        settings.background_color = background_color.strip() or "#f9fafb"
        settings.text_color = text_color.strip() or "#111827"
        settings.nav_bg_color = nav_bg_color.strip() or "#1e293b"
        settings.nav_text_color = nav_text_color.strip() or "#f8fafc"
        settings.card_bg_color = card_bg_color.strip() or "#ffffff"
        settings.border_color = border_color.strip() or "#e5e7eb"

        # Handle logo upload
        if logo and logo.filename:
            ensure_logo_dir()
            # Sanitize filename
            filename = os.path.basename(logo.filename)
            safe_name = "".join(c for c in filename if c.isalnum() or c in "._- ")
            if not safe_name:
                safe_name = "logo.png"
            logo_path = os.path.join(LOGO_DIR, safe_name)
            with open(logo_path, "wb") as f:
                f.write(logo.file.read())
            settings.logo_path = f"static/logos/{safe_name}"

        db.commit()
    except Exception as e:
        db.rollback()
        settings = StoreSettings.get(db)
        return templates.TemplateResponse("settings.html", {
            "request": request,
            "settings": settings,
            "error": str(e),
        })
    finally:
        db.close()

    log_change("settings", None, f"Updated store settings: {store_name.strip() or 'Unnamed store'}", None)
    return RedirectResponse(url="/settings?success=1", status_code=303)


@router.post("/settings/remove-logo")
def remove_logo(request: Request):
    db = SessionLocal()
    try:
        settings = StoreSettings.get(db)
        if settings.logo_path:
            # Try to delete the file
            full_path = os.path.join(
                os.path.dirname(os.path.dirname(__file__)), settings.logo_path
            )
            if os.path.exists(full_path):
                try:
                    os.remove(full_path)
                except OSError:
                    pass
            settings.logo_path = None
            db.commit()
    except Exception as e:
        db.rollback()
    finally:
        db.close()
    log_change("settings", None, "Removed store logo", None)
    return RedirectResponse(url="/settings", status_code=303)


@router.post("/settings/reset-colors")
def reset_colors(request: Request):
    """Reset color scheme to defaults."""
    db = SessionLocal()
    try:
        settings = StoreSettings.get(db)
        settings.primary_color = "#3b82f6"
        settings.secondary_color = "#6b7280"
        settings.background_color = "#f9fafb"
        settings.text_color = "#111827"
        settings.nav_bg_color = "#1e293b"
        settings.nav_text_color = "#f8fafc"
        settings.card_bg_color = "#ffffff"
        settings.border_color = "#e5e7eb"
        db.commit()
    except Exception as e:
        db.rollback()
    finally:
        db.close()
    log_change("settings", None, "Reset color scheme to defaults", None)
    return RedirectResponse(url="/settings?success=1", status_code=303)


@router.get("/settings/json")
def get_settings_json():
    """Return settings as JSON for AJAX consumption."""
    db = SessionLocal()
    try:
        settings = StoreSettings.get(db)
        return {
            "store_name": settings.store_name,
            "logo_path": settings.logo_path,
            "logo_size": settings.logo_size or 40,
            "primary_color": settings.primary_color,
            "secondary_color": settings.secondary_color,
            "background_color": settings.background_color,
            "text_color": settings.text_color,
            "nav_bg_color": settings.nav_bg_color,
            "nav_text_color": settings.nav_text_color,
            "card_bg_color": settings.card_bg_color,
            "border_color": settings.border_color,
        }
    finally:
        db.close()


@router.get("/system/check-updates")
def check_for_updates():
    """Check for updates by fetching the hosted version.json file."""
    current_version = config.APP_VERSION
    update_url = config.UPDATE_CHECK_URL

    if not update_url:
        return {
            "current_version": current_version,
            "update_available": False,
            "message": "Update checking is disabled. Configure UPDATE_CHECK_URL in config.py to enable.",
        }

    try:
        req = urllib.request.Request(update_url, headers={"User-Agent": "TCG Preorder Manager"})
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode("utf-8"))

        latest_version = data.get("version", "")
        download_url = data.get("download_url", "")
        release_notes = data.get("release_notes", "")

        # Simple semantic version comparison
        def parse_version(v):
            try:
                return tuple(map(int, v.strip().split(".")))
            except (ValueError, AttributeError):
                return (0, 0, 0)

        update_available = parse_version(latest_version) > parse_version(current_version)

        return {
            "current_version": current_version,
            "latest_version": latest_version,
            "update_available": update_available,
            "download_url": download_url if update_available else "",
            "release_notes": release_notes,
            "message": "" if update_available else "You are running the latest version.",
        }
    except Exception as e:
        return {
            "current_version": current_version,
            "update_available": False,
            "message": f"Could not check for updates: {str(e)}",
        }
