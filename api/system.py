from fastapi import APIRouter, Request, Form
from fastapi.responses import JSONResponse, RedirectResponse
from pathlib import Path
import os
import sys
import subprocess
import threading
import time
import shutil
from datetime import datetime

from models.base import SessionLocal, Base, engine
from models.store_settings import StoreSettings
from services.backup import create_backup
from api.auth import get_staff_name

router = APIRouter(prefix="/system", tags=["System"])


@router.get("/")
def system_page(request: Request):
    """Return the System section HTML for AJAX loading."""
    db = SessionLocal()
    try:
        settings = StoreSettings.get(db)
        current_port = settings.app_port or 8000
    finally:
        db.close()
    
    return templates.TemplateResponse("system.html", {
        "request": request,
        "current_port": current_port,
    })


@router.post("/update-port")
def update_port(request: Request, port: int = Form(...), staff_name: str = Form("")):
    """Update the app port setting."""
    if not staff_name.strip():
        staff_name = get_staff_name(request)
    # Validate port range
    if port < 1024 or port > 65535:
        return JSONResponse(status_code=400, content={"status": "error", "message": "Port must be between 1024 and 65535."})
    
    db = SessionLocal()
    try:
        settings = StoreSettings.get(db)
        old_port = settings.app_port or 8000
        settings.app_port = port
        db.commit()
        
        # Log the change
        from services.audit import log_change
        log_change(
            entity_type="Settings",
            entity_id=1,
            action=f"Changed app port from {old_port} to {port}",
            staff_name=staff_name
        )
    finally:
        db.close()
    
    return JSONResponse(content={"status": "success", "message": f"Port changed to {port}. Restart the app to apply."})


@router.post("/restart")
def restart_app(request: Request, staff_name: str = Form("")):
    """Create a backup and restart the app gracefully."""
    if not staff_name.strip():
        staff_name = get_staff_name(request)
    db = SessionLocal()
    try:
        settings = StoreSettings.get(db)
        new_port = settings.app_port or 8000
        
        # Create a backup before restarting
        try:
            create_backup()
        except Exception as e:
            print(f"Backup before restart failed: {e}")
        
        # Log the restart
        from services.audit import log_change
        log_change(
            entity_type="Settings",
            entity_id=1,
            action=f"Restarted app (port {new_port})",
            staff_name=staff_name
        )
    finally:
        db.close()
    
    # Save the new port to an env file so the restarted process knows which port to use
    env_file = Path(__file__).resolve().parent.parent / ".app_port"
    env_file.write_text(str(new_port))
    
    # Restart the app in a new process
    script_path = Path(__file__).resolve().parent.parent / "main.py"
    python_exe = sys.executable
    
    # Start new process in background
    subprocess.Popen(
        [python_exe, str(script_path)],
        cwd=str(script_path.parent),
        creationflags=subprocess.CREATE_NEW_CONSOLE if os.name == "nt" else 0
    )
    
    # Give the new process time to start
    time.sleep(2)
    
    # Log the shutdown
    print(f"Shutting down old process. New process started on port {new_port}.")
    
    # Exit the current process
    os._exit(0)


@router.post("/reset-settings")
def reset_settings_to_defaults(request: Request):
    """Reset all store settings to their default values."""
    staff_name = get_staff_name(request)
    db = SessionLocal()
    try:
        settings = StoreSettings.get(db)
        
        # Reset all settings to defaults
        settings.store_name = None
        settings.address = None
        settings.contact_number = None
        settings.email = None
        settings.website = None
        settings.abn = None
        settings.logo_path = None
        settings.gmail_sender_email = None
        settings.primary_color = "#3b82f6"
        settings.secondary_color = "#6b7280"
        settings.background_color = "#f9fafb"
        settings.text_color = "#111827"
        settings.nav_bg_color = "#1e293b"
        settings.nav_text_color = "#f8fafc"
        settings.card_bg_color = "#ffffff"
        settings.border_color = "#e5e7eb"
        settings.backup_enabled = False
        settings.backup_storage = "local"
        settings.backup_schedule = "daily"
        settings.backup_time = "02:00"
        settings.backup_weekday = "monday"
        settings.backup_google_folder_id = None
        settings.backup_google_token_path = None
        settings.backup_last_run = None
        settings.backup_last_status = None
        settings.backup_last_message = None
        settings.app_port = 8000
        settings.logo_size = 40
        settings.timeout_enabled = False
        settings.timeout_seconds = 1800
        # Keep setup_complete, recovery_token_hash as they are
        
        db.commit()
        
        from services.audit import log_change
        log_change(
            entity_type="Settings",
            entity_id=1,
            action="Reset all settings to defaults",
            staff_name=staff_name
        )
    finally:
        db.close()
    
    return JSONResponse(content={"status": "success", "message": "All settings have been reset to defaults."})


@router.post("/delete-database")
def delete_database(request: Request, confirmation_word: str = Form(...)):
    """Delete the entire database and all data. Requires exact confirmation word."""
    staff_name = get_staff_name(request)
    
    # Validate the confirmation word
    if confirmation_word.strip().upper() != "DELETE":
        return JSONResponse(status_code=400, content={"status": "error", "message": "Confirmation word incorrect. Type DELETE to confirm."})
    
    # Create a backup before deleting
    try:
        create_backup()
    except Exception as e:
        print(f"Backup before database deletion failed: {e}")
    
    db_path = Path(__file__).resolve().parent.parent / "database" / "app.db"
    
    # Log the deletion before we lose the database
    from services.audit import log_change
    try:
        log_change(
            entity_type="System",
            entity_id=None,
            action="Deleted entire database",
            staff_name=staff_name
        )
    except Exception:
        pass  # Database may already be gone
    
    # Dispose the SQLAlchemy engine to release the SQLite file lock
    try:
        engine.dispose()
    except Exception:
        pass
    
    # Small delay to ensure file handles are released
    time.sleep(0.5)
    
    # Delete the database file
    tables_dropped = False
    if db_path.exists():
        try:
            db_path.unlink()
        except PermissionError:
            # If still locked, try removing contents instead of the file itself
            import sqlite3
            try:
                conn = sqlite3.connect(str(db_path))
                cur = conn.cursor()
                # Drop all tables
                cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = cur.fetchall()
                for (table,) in tables:
                    cur.execute(f"DROP TABLE IF EXISTS {table}")
                conn.commit()
                conn.close()
                tables_dropped = True
                print("Database tables dropped instead of file deletion (file was locked).")
            except Exception as e:
                print(f"Failed to drop tables: {e}")
    
    # Also delete any journal/wal files
    for ext in ["-wal", "-shm", ".db-journal"]:
        journal = db_path.parent / (db_path.name + ext)
        if journal.exists():
            try:
                journal.unlink()
            except PermissionError:
                pass
    
    # Recreate all tables so the app can continue running
    try:
        engine.dispose()
        from models.base import init_db
        init_db()
        print("Database tables recreated after deletion.")
    except Exception as e:
        print(f"Failed to recreate tables: {e}")
    
    # Remove the .app_port file if it exists
    env_file = Path(__file__).resolve().parent.parent / ".app_port"
    if env_file.exists():
        env_file.unlink()
    
    return JSONResponse(content={
        "status": "success",
        "message": "Database has been deleted. The app will redirect to the setup wizard."
    })
