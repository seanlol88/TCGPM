"""API routes for backup management and Google Drive integration."""
import os
import json
import threading
from datetime import datetime
from urllib.parse import urlencode

from fastapi import APIRouter, Request, Form, Query, UploadFile, File
from fastapi.responses import RedirectResponse, JSONResponse, FileResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from config import BASE_DIR
from models.base import SessionLocal
from models.store_settings import StoreSettings
from services.backup import (
    BACKUP_DIR,
    create_backup,
    list_local_backups,
    delete_local_backup,
    restore_local_backup,
    import_backup_file,
    list_google_drive_backups,
    delete_google_drive_backup,
    restore_google_drive_backup,
    get_backup_status,
    ensure_backup_dir,
)
from services.audit import log_change
from api.auth import get_staff_name

router = APIRouter()
templates: Jinja2Templates = None  # type: ignore[assignment]

# Google Drive OAuth2 configuration
GOOGLE_DRIVE_CLIENT_FILE = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "drive_credentials.json"
)
GOOGLE_DRIVE_TOKEN_DIR = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "database"
)
GOOGLE_DRIVE_SCOPES = [
    "https://www.googleapis.com/auth/drive.file",  # Only access files created by the app
]
GOOGLE_DRIVE_REDIRECT_URI = "http://localhost:8000/backups/google-drive/callback"


@router.get("/backups")
def backup_page(request: Request):
    """Show the backup management page."""
    db = SessionLocal()
    try:
        settings = StoreSettings.get(db)
        status = get_backup_status()
        local_backups = list_local_backups()
        google_backups = []
        
        if settings.backup_google_token_path and os.path.exists(settings.backup_google_token_path):
            google_backups = list_google_drive_backups()
        
        return templates.TemplateResponse("backups.html", {
            "request": request,
            "settings": settings,
            "status": status,
            "local_backups": local_backups,
            "google_backups": google_backups,
            "backup_dir": str(BACKUP_DIR),
        })
    finally:
        db.close()


@router.get("/backups/open-folder")
def open_backup_folder():
    """Open the local backup folder in the system file explorer."""
    ensure_backup_dir()
    try:
        os.startfile(str(BACKUP_DIR))
        return JSONResponse(content={"status": "success", "message": "Folder opened."})
    except Exception as e:
        return JSONResponse(content={"status": "error", "message": str(e)})


@router.post("/backups/run")
def run_manual_backup(request: Request, staff_name: str = Form(""), notes: str = Form("")):
    """Trigger a manual backup."""
    if not staff_name.strip():
        staff_name = get_staff_name(request)
    result = create_backup(notes=notes.strip() if notes else "")
    
    log_change(
        "settings",
        None,
        f"Manual backup: {result['message']}",
        staff_name.strip() or None,
    )
    
    if result["status"] == "success":
        return RedirectResponse(url="/backups?success=1", status_code=303)
    else:
        return RedirectResponse(url=f"/backups?error={result['message']}", status_code=303)


@router.post("/backups/run-json")
def run_manual_backup_json(request: Request, staff_name: str = Form(""), notes: str = Form("")):
    """Trigger a manual backup and return JSON."""
    if not staff_name.strip():
        staff_name = get_staff_name(request)
    result = create_backup(notes=notes.strip() if notes else "")
    
    log_change(
        "settings",
        None,
        f"Manual backup: {result['message']}",
        staff_name.strip() or None,
    )
    
    return JSONResponse(content=result)


@router.get("/backups/download-local/{filename}")
def download_local_backup(filename: str):
    """Download a local backup file."""
    backup_dir = os.path.join(BASE_DIR, "backups", "local")
    file_path = os.path.join(backup_dir, filename)
    
    # Prevent path traversal attacks
    if not os.path.abspath(file_path).startswith(os.path.abspath(backup_dir)):
        return JSONResponse(status_code=400, content={"status": "error", "message": "Invalid filename."})
    
    if not os.path.exists(file_path):
        return JSONResponse(status_code=404, content={"status": "error", "message": "Backup file not found."})
    
    return FileResponse(file_path, filename=filename)


@router.post("/backups/delete-local")
def delete_local_backup_endpoint(request: Request, filename: str = Form("")):
    """Delete a local backup file."""
    result = delete_local_backup(filename)
    
    if result["status"] == "success":
        return JSONResponse(content=result)
    else:
        return JSONResponse(status_code=400, content=result)


@router.post("/backups/import")
def import_backup_endpoint(request: Request, backup: UploadFile = File(None), staff_name: str = Form("")):
    """Import a database from an uploaded backup file."""
    if not staff_name.strip():
        staff_name = get_staff_name(request)
    
    # Validate file upload
    if not backup or not backup.filename:
        return JSONResponse(status_code=400, content={"status": "error", "message": "No file uploaded."})
    
    # Validate file extension
    if not backup.filename.endswith('.db'):
        return JSONResponse(status_code=400, content={"status": "error", "message": "Invalid file type. Please upload a .db file."})
    
    # Save the uploaded file temporarily
    import tempfile
    temp_dir = os.path.join(BASE_DIR, "backups", "temp")
    os.makedirs(temp_dir, exist_ok=True)
    temp_path = os.path.join(temp_dir, backup.filename)
    
    try:
        content = backup.file.read()
        with open(temp_path, 'wb') as f:
            f.write(content)
    except Exception as e:
        return JSONResponse(status_code=400, content={"status": "error", "message": f"Failed to save uploaded file: {str(e)}"})
    
    # Import the backup
    result = import_backup_file(temp_path)
    
    # Clean up temp file
    try:
        if os.path.exists(temp_path):
            os.remove(temp_path)
    except Exception:
        pass
    
    # Log the change
    log_change(
        "settings",
        None,
        f"Import backup: {result['message']}",
        staff_name.strip() or None,
    )
    
    if result["status"] == "success":
        return JSONResponse(content=result)
    else:
        return JSONResponse(status_code=400, content=result)


@router.post("/backups/delete-google")
def delete_google_backup_endpoint(request: Request, file_id: str = Form("")):
    """Delete a Google Drive backup file."""
    result = delete_google_drive_backup(file_id)
    
    if result["status"] == "success":
        return JSONResponse(content=result)
    else:
        return JSONResponse(status_code=400, content=result)


@router.post("/backups/restore-local")
def restore_local_backup_endpoint(request: Request, filename: str = Form(""), staff_name: str = Form("")):
    """Restore the database from a local backup file."""
    if not staff_name.strip():
        staff_name = get_staff_name(request)
    
    result = restore_local_backup(filename)
    
    log_change(
        "settings",
        None,
        f"Restored database from local backup: {filename}",
        staff_name.strip() or None,
    )
    
    if result["status"] == "success":
        return JSONResponse(content=result)
    else:
        return JSONResponse(status_code=400, content=result)


@router.post("/backups/restore-google")
def restore_google_backup_endpoint(request: Request, file_id: str = Form(""), staff_name: str = Form("")):
    """Restore the database from a Google Drive backup file."""
    if not staff_name.strip():
        staff_name = get_staff_name(request)
    
    result = restore_google_drive_backup(file_id)
    
    log_change(
        "settings",
        None,
        f"Restored database from Google Drive backup: {file_id}",
        staff_name.strip() or None,
    )
    
    if result["status"] == "success":
        return JSONResponse(content=result)
    else:
        return JSONResponse(status_code=400, content=result)


@router.get("/backups/google-drive/connect")
def google_drive_connect(request: Request):
    """Start the Google Drive OAuth2 flow."""
    try:
        from google_auth_oauthlib.flow import Flow
        
        if not os.path.exists(GOOGLE_DRIVE_CLIENT_FILE):
            return RedirectResponse(
                url="/backups?error=Google Drive credentials file not found. Please download 'drive_credentials.json' from your Google Cloud project and place it in the project root.",
                status_code=303,
            )
        
        flow = Flow.from_client_secrets_file(
            GOOGLE_DRIVE_CLIENT_FILE,
            scopes=GOOGLE_DRIVE_SCOPES,
            redirect_uri=GOOGLE_DRIVE_REDIRECT_URI,
        )
        
        authorization_url, state = flow.authorization_url(
            access_type="offline",
            prompt="consent",
        )
        
        # Store only the state in the session (serialization() was removed in newer versions)
        request.session["gd_oauth_state"] = state
        
        return RedirectResponse(url=authorization_url, status_code=302)
    except Exception as e:
        return RedirectResponse(
            url=f"/backups?error=Failed to start Google Drive connection: {str(e)}",
            status_code=303,
        )


@router.get("/backups/google-drive/callback")
def google_drive_callback(request: Request, code: str = None, error: str = None):
    """Handle the Google Drive OAuth2 callback."""
    if error:
        return RedirectResponse(
            url=f"/backups?error=Google Drive connection denied: {error}",
            status_code=303,
        )
    
    if not code:
        return RedirectResponse(url="/backups?error=No authorization code received.", status_code=303)
    
    try:
        from google_auth_oauthlib.flow import Flow
        
        state = request.session.get("gd_oauth_state")
        if not state:
            return RedirectResponse(url="/backups?error=OAuth session expired. Please try again.", status_code=303)
        
        # Recreate the flow with the stored state (instead of reverse_serialization)
        flow = Flow.from_client_secrets_file(
            GOOGLE_DRIVE_CLIENT_FILE,
            scopes=GOOGLE_DRIVE_SCOPES,
            state=state,
        )
        flow.redirect_uri = GOOGLE_DRIVE_REDIRECT_URI
        flow.fetch_token(code=code)
        
        # Save the token
        os.makedirs(GOOGLE_DRIVE_TOKEN_DIR, exist_ok=True)
        token_path = os.path.join(GOOGLE_DRIVE_TOKEN_DIR, "drive_token.json")
        
        # Write token to file
        with open(token_path, "w") as f:
            json.dump({
                "token": flow.credentials.token,
                "refresh_token": flow.credentials.refresh_token,
                "token_uri": flow.credentials.token_uri,
                "client_id": flow.credentials.client_id,
                "client_secret": flow.credentials.client_secret,
                "scopes": flow.credentials.scopes,
            }, f)
        
        # Update settings
        db = SessionLocal()
        try:
            settings = StoreSettings.get(db)
            settings.backup_google_token_path = token_path
            settings.backup_storage = "google_drive"
            db.commit()
        finally:
            db.close()
        
        log_change("settings", None, "Connected Google Drive for backups", None)
        
        return RedirectResponse(url="/backups?success=1&connected=1", status_code=303)
    except Exception as e:
        return RedirectResponse(
            url=f"/backups?error=Failed to connect Google Drive: {str(e)}",
            status_code=303,
        )


@router.post("/backups/google-drive/disconnect")
def google_drive_disconnect(request: Request):
    """Disconnect Google Drive by removing the token."""
    db = SessionLocal()
    try:
        settings = StoreSettings.get(db)
        if settings.backup_google_token_path and os.path.exists(settings.backup_google_token_path):
            try:
                os.remove(settings.backup_google_token_path)
            except OSError:
                pass
        settings.backup_google_token_path = None
        settings.backup_storage = "local"
        db.commit()
    finally:
        db.close()
    
    log_change("settings", None, "Disconnected Google Drive", None)
    return RedirectResponse(url="/backups?success=1", status_code=303)


@router.post("/backups/update-settings")
def update_backup_settings(
    request: Request,
    backup_enabled: str = Form(""),
    backup_storage: str = Form("local"),
    backup_schedule: str = Form("daily"),
    backup_time: str = Form("02:00"),
    backup_weekday: str = Form("monday"),
    backup_google_folder_id: str = Form(""),
):
    """Update backup configuration settings."""
    db = SessionLocal()
    try:
        settings = StoreSettings.get(db)
        settings.backup_enabled = (backup_enabled == "on")
        settings.backup_storage = backup_storage
        settings.backup_schedule = backup_schedule
        settings.backup_time = backup_time.strip() or "02:00"
        settings.backup_weekday = backup_weekday.strip() or "monday"
        settings.backup_google_folder_id = backup_google_folder_id.strip() or None
        db.commit()
        
        # Capture values before closing the session
        enabled = settings.backup_enabled
    finally:
        db.close()
    
    log_change(
        "settings",
        None,
        f"Updated backup settings: enabled={enabled}, storage={backup_storage}, schedule={backup_schedule}, time={backup_time}, weekday={backup_weekday}",
        None,
    )
    
    return RedirectResponse(url="/backups?success=1", status_code=303)


@router.get("/backups/status-json")
def backup_status_json():
    """Return backup status as JSON for AJAX polling."""
    return JSONResponse(content=get_backup_status())


@router.get("/backups/list-json")
def backup_list_json():
    """Return all backups as JSON."""
    db = SessionLocal()
    try:
        settings = StoreSettings.get(db)
        local = list_local_backups()
        google = []
        
        if settings.backup_google_token_path and os.path.exists(settings.backup_google_token_path):
            google = list_google_drive_backups()
        
        return JSONResponse(content={
            "local": local,
            "google": google,
        })
    finally:
        db.close()
