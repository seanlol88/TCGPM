from fastapi import APIRouter, Request, Form
from fastapi.responses import JSONResponse, RedirectResponse
from pathlib import Path
import os
import sys
import subprocess
import threading
import time
from datetime import datetime

from models.base import SessionLocal
from models.store_settings import StoreSettings
from services.backup import create_backup

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
def update_port(request: Request, port: int = Form(...), staff_name: str = Form(None)):
    """Update the app port setting."""
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
def restart_app(request: Request, staff_name: str = Form(None)):
    """Create a backup and restart the app gracefully."""
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
