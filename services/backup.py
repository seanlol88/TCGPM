"""Backup service for managing database backups locally and on Google Drive."""
import json
import os
import shutil
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional

from config import BASE_DIR, DATABASE_URL
from models.base import SessionLocal
from models.store_settings import StoreSettings

# Local backup directory
BACKUP_DIR = BASE_DIR / "backups" / "local"
MAX_BACKUPS = 5


def ensure_backup_dir():
    """Create the backup directory if it doesn't exist."""
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)


def get_db_path():
    """Extract the SQLite database file path from DATABASE_URL."""
    # DATABASE_URL format: sqlite:///C:/path/to/app.db
    url = DATABASE_URL
    if url.startswith("sqlite:///"):
        return url[10:]  # Remove "sqlite:///" prefix
    return None


def create_local_backup(notes: str = "") -> Dict:
    """Create a local backup of the database file.
    
    Optionally saves notes as a companion .json file alongside the backup.
    Returns a dict with backup info: {path, filename, size, timestamp, status, message}
    """
    ensure_backup_dir()
    db_path = get_db_path()
    
    if not db_path or not os.path.exists(db_path):
        return {
            "status": "error",
            "message": f"Database file not found: {db_path}",
            "path": None,
            "filename": None,
            "size": 0,
            "timestamp": None,
        }
    
    # Create a timestamped backup filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"backup_{timestamp}.db"
    backup_path = BACKUP_DIR / filename
    
    # Copy the database file
    try:
        shutil.copy2(db_path, str(backup_path))
        size = backup_path.stat().st_size
        
        # Save notes as a companion .json file
        if notes:
            notes_path = BACKUP_DIR / filename.replace(".db", ".json")
            with open(notes_path, "w", encoding="utf-8") as f:
                json.dump({"notes": notes, "timestamp": timestamp}, f)
        
        # Rotate old backups, keeping only MAX_BACKUPS
        rotate_local_backups()
        
        return {
            "status": "success",
            "message": f"Backup created: {filename}",
            "path": str(backup_path),
            "filename": filename,
            "size": size,
            "timestamp": timestamp,
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to create backup: {str(e)}",
            "path": None,
            "filename": None,
            "size": 0,
            "timestamp": None,
        }


def rotate_local_backups():
    """Remove old backups, keeping only the MAX_BACKUPS most recent ones."""
    ensure_backup_dir()
    backups = sorted(
        BACKUP_DIR.glob("backup_*.db"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    
    for old_backup in backups[MAX_BACKUPS:]:
        try:
            old_backup.unlink()
            # Also remove companion notes file if it exists
            notes_path = old_backup.with_suffix('.json')
            if notes_path.exists():
                notes_path.unlink()
        except OSError:
            pass


def list_local_backups() -> List[Dict]:
    """List all local backup files sorted by modification time (newest first)."""
    ensure_backup_dir()
    backups = []
    
    for backup_file in sorted(
        BACKUP_DIR.glob("backup_*.db"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    ):
        stat = backup_file.stat()
        # Read notes from companion .json file if it exists
        notes = ""
        notes_path = backup_file.with_suffix('.json')
        if notes_path.exists():
            try:
                with open(notes_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    notes = data.get("notes", "")
            except Exception:
                pass
        backups.append({
            "filename": backup_file.name,
            "path": str(backup_file),
            "size": stat.st_size,
            "size_mb": round(stat.st_size / (1024 * 1024), 2),
            "created": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
            "storage": "local",
            "notes": notes,
        })
    
    return backups


def delete_local_backup(filename: str) -> Dict:
    """Delete a specific local backup file."""
    backup_path = BACKUP_DIR / filename
    
    # Safety check: only delete our backup files
    if not backup_path.exists() or not filename.startswith("backup_"):
        return {"status": "error", "message": "Backup file not found."}
    
    try:
        backup_path.unlink()
        return {"status": "success", "message": f"Deleted: {filename}"}
    except Exception as e:
        return {"status": "error", "message": f"Failed to delete: {str(e)}"}


def restore_local_backup(filename: str) -> Dict:
    """Restore the database from a local backup file.
    
    Returns a dict with restore info: {status, message}
    """
    ensure_backup_dir()
    db_path = get_db_path()
    backup_path = BACKUP_DIR / filename
    
    # Safety check: only restore from our backup files
    if not backup_path.exists() or not filename.startswith("backup_"):
        return {"status": "error", "message": "Backup file not found."}
    
    if not db_path:
        return {"status": "error", "message": "Could not determine database path."}
    
    try:
        # Close any open database sessions by ensuring no active connections
        # Copy the backup over the current database
        shutil.copy2(str(backup_path), db_path)
        return {
            "status": "success",
            "message": f"Database restored from {filename}. Please restart the application.",
        }
    except Exception as e:
        return {"status": "error", "message": f"Failed to restore backup: {str(e)}"}


def import_backup_file(file_path: str) -> Dict:
    """Import a database from an uploaded backup file.
    
    Validates the file is a valid SQLite database, then replaces the current database.
    Returns a dict with import info: {status, message}
    """
    db_path = get_db_path()
    
    if not db_path:
        return {"status": "error", "message": "Could not determine database path."}
    
    if not os.path.exists(file_path):
        return {"status": "error", "message": "Uploaded file not found."}
    
    # Validate the file is a valid SQLite database
    try:
        conn = sqlite3.connect(file_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        conn.close()
    except Exception as e:
        return {"status": "error", "message": f"Invalid database file: {str(e)}"}
    
    # Check for essential tables
    essential_tables = ['products', 'customers', 'orders']
    missing = [t for t in essential_tables if t not in tables]
    if missing:
        return {"status": "error", "message": f"Invalid backup file: missing tables ({', '.join(missing)})."}
    
    try:
        # Copy the imported file over the current database
        shutil.copy2(file_path, db_path)
        filename = os.path.basename(file_path)
        return {
            "status": "success",
            "message": f"Database imported from {filename}. Please restart the application.",
        }
    except Exception as e:
        return {"status": "error", "message": f"Failed to import backup: {str(e)}"}


def get_google_drive_service(token_path: str):
    """Get a Google Drive API service object using stored credentials.
    
    Returns the service object or None if authentication fails.
    """
    try:
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
        
        if not token_path or not os.path.exists(token_path):
            return None
        
        creds = Credentials.from_authorized_user_file(token_path)
        service = build("drive", "v3", credentials=creds)
        return service
    except Exception:
        return None


BACKUP_FOLDER_NAME = "TCG Preorder Manager Backups"


def get_or_create_backup_folder(token_path: str) -> Optional[str]:
    """Get the backup folder ID from Google Drive, creating it if it doesn't exist.
    
    Returns the folder ID or None if authentication fails.
    """
    try:
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
        from googleapiclient.errors import HttpError
        
        if not token_path or not os.path.exists(token_path):
            return None
        
        creds = Credentials.from_authorized_user_file(token_path)
        service = build("drive", "v3", credentials=creds)
        
        # Search for the folder
        results = service.files().list(
            q=f"name = '{BACKUP_FOLDER_NAME}' and mimeType = 'application/vnd.google-apps.folder' and trashed = false",
            pageSize=10,
            fields="files(id, name)",
        ).execute()
        
        folders = results.get("files", [])
        if folders:
            # Folder already exists
            return folders[0]["id"]
        
        # Create the folder
        folder_metadata = {
            "name": BACKUP_FOLDER_NAME,
            "mimeType": "application/vnd.google-apps.folder",
        }
        folder = service.files().create(body=folder_metadata, fields="id,name").execute()
        return folder.get("id")
    except HttpError as e:
        # Log the actual error for debugging
        import logging
        logging.getLogger(__name__).error(f"Google Drive folder error: {e}")
        return None
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Unexpected error creating backup folder: {e}")
        return None


def upload_to_google_drive(filename: str, file_path: str, folder_id: Optional[str] = None) -> Dict:
    """Upload a backup file to Google Drive.
    
    If no folder_id is provided, automatically creates or uses the "TCG Preorder Manager Backups" folder.
    Returns a dict with upload info: {status, message, file_id, file_name}
    """
    try:
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload
        
        # Get the token path from settings
        db = SessionLocal()
        try:
            settings = StoreSettings.get(db)
            token_path = settings.backup_google_token_path
        finally:
            db.close()
        
        if not token_path or not os.path.exists(token_path):
            return {"status": "error", "message": "Google Drive not connected. Please link your Google Drive first."}
        
        creds = Credentials.from_authorized_user_file(token_path)
        service = build("drive", "v3", credentials=creds)
        
        # If no folder_id provided, create or find the default backup folder
        if not folder_id:
            folder_id = get_or_create_backup_folder(token_path)
            if not folder_id:
                return {"status": "error", "message": "Failed to create backup folder on Google Drive. Make sure the Google Drive API is enabled in your Google Cloud Console (APIs & Services > Library > Drive API > Enable)."}
        
        # Prepare the file metadata
        metadata = {
            "name": filename,
            "mimeType": "application/x-sqlite3",
        }
        if folder_id:
            metadata["parents"] = [folder_id]
        
        # Upload the file
        media = MediaFileUpload(file_path, mimetype="application/x-sqlite3", resumable=True)
        file = service.files().create(body=metadata, media_body=media, fields="id,name").execute()
        
        return {
            "status": "success",
            "message": f"Uploaded to Google Drive: {filename}",
            "file_id": file.get("id"),
            "file_name": file.get("name"),
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Google Drive upload failed: {str(e)}",
            "file_id": None,
            "file_name": None,
        }


def list_google_drive_backups(folder_id: Optional[str] = None) -> List[Dict]:
    """List backup files stored on Google Drive.
    
    If no folder_id is provided, searches the default "TCG Preorder Manager Backups" folder.
    """
    try:
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
        
        # Get the token path from settings
        db = SessionLocal()
        try:
            settings = StoreSettings.get(db)
            token_path = settings.backup_google_token_path
        finally:
            db.close()
        
        if not token_path or not os.path.exists(token_path):
            return []
        
        creds = Credentials.from_authorized_user_file(token_path)
        service = build("drive", "v3", credentials=creds)
        
        # If no folder_id provided, try to find the default backup folder
        if not folder_id:
            folder_id = get_or_create_backup_folder(token_path)
        
        # Build query for backup files
        query = "name starts with 'backup_' and mimeType = 'application/x-sqlite3'"
        if folder_id:
            query += f" and '{folder_id}' in parents"
        
        results = service.files().list(
            q=query,
            pageSize=50,
            fields="files(id, name, size, modifiedTime)",
            orderBy="modifiedTime desc",
        ).execute()
        
        files = results.get("files", [])
        backups = []
        for f in files:
            backups.append({
                "filename": f["name"],
                "file_id": f["id"],
                "size": int(f.get("size", 0)),
                "size_mb": round(int(f.get("size", 0)) / (1024 * 1024), 2),
                "created": f.get("modifiedTime", "Unknown"),
                "storage": "google_drive",
            })
        
        return backups
    except Exception:
        return []


def delete_google_drive_backup(file_id: str) -> Dict:
    """Delete a backup file from Google Drive."""
    try:
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
        
        # Get the token path from settings
        db = SessionLocal()
        try:
            settings = StoreSettings.get(db)
            token_path = settings.backup_google_token_path
        finally:
            db.close()
        
        if not token_path or not os.path.exists(token_path):
            return {"status": "error", "message": "Google Drive not connected."}
        
        creds = Credentials.from_authorized_user_file(token_path)
        service = build("drive", "v3", credentials=creds)
        
        service.files().delete(fileId=file_id).execute()
        return {"status": "success", "message": f"Deleted from Google Drive: {file_id}"}
    except Exception as e:
        return {"status": "error", "message": f"Failed to delete: {str(e)}"}


def restore_google_drive_backup(file_id: str) -> Dict:
    """Restore the database from a Google Drive backup file.
    
    Downloads the backup from Google Drive and replaces the current database.
    Returns a dict with restore info: {status, message}
    """
    try:
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaIoBaseDownload
        import io
        
        # Get the token path from settings
        db = SessionLocal()
        try:
            settings = StoreSettings.get(db)
            token_path = settings.backup_google_token_path
        finally:
            db.close()
        
        if not token_path or not os.path.exists(token_path):
            return {"status": "error", "message": "Google Drive not connected."}
        
        db_path = get_db_path()
        if not db_path:
            return {"status": "error", "message": "Could not determine database path."}
        
        creds = Credentials.from_authorized_user_file(token_path)
        service = build("drive", "v3", credentials=creds)
        
        # Download the backup file
        request = service.files().get_media(fileId=file_id)
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()
        
        # Write the downloaded content to the database path
        fh.seek(0)
        with open(db_path, "wb") as f:
            f.write(fh.read())
        
        return {
            "status": "success",
            "message": f"Database restored from Google Drive backup. Please restart the application.",
        }
    except Exception as e:
        return {"status": "error", "message": f"Failed to restore backup: {str(e)}"}


def rotate_google_drive_backups(folder_id: Optional[str] = None):
    """Remove old backups from Google Drive, keeping only MAX_BACKUPS."""
    backups = list_google_drive_backups(folder_id)
    
    for old_backup in backups[MAX_BACKUPS:]:
        try:
            delete_google_drive_backup(old_backup["file_id"])
        except Exception:
            pass


def create_backup(notes: str = "") -> Dict:
    """Create a backup using the configured storage method.
    
    This is the main entry point called by the scheduler and manual backup button.
    Returns a dict with the backup result.
    """
    db = SessionLocal()
    try:
        settings = StoreSettings.get(db)
        
        # Create a local backup first (always keep a local copy)
        result = create_local_backup(notes=notes)
        
        if result["status"] == "success":
            # If Google Drive is configured, also upload there
            if settings.backup_storage == "google_drive" and settings.backup_google_token_path:
                drive_result = upload_to_google_drive(
                    result["filename"],
                    result["path"],
                )
                if drive_result["status"] == "success":
                    result["message"] += f" (also uploaded to Google Drive)"
                    # Rotate Google Drive backups
                    rotate_google_drive_backups()
                else:
                    result["message"] += f" (Google Drive upload failed: {drive_result['message']})"
            
            # Update last run info
            settings.backup_last_run = datetime.now()
            settings.backup_last_status = "success"
            settings.backup_last_message = result["message"]
            db.commit()
        else:
            settings.backup_last_status = "error"
            settings.backup_last_message = result["message"]
            db.commit()
        
        return result
    except Exception as e:
        settings = StoreSettings.get(db)
        settings.backup_last_status = "error"
        settings.backup_last_message = str(e)
        db.commit()
        return {"status": "error", "message": str(e)}
    finally:
        db.close()


def list_all_backups(folder_id: Optional[str] = None) -> List[Dict]:
    """List all backups from both local and Google Drive storage."""
    local = list_local_backups()
    remote = []
    
    if folder_id:
        remote = list_google_drive_backups(folder_id)
    
    # Combine and sort by created date (newest first)
    all_backups = local + remote
    all_backups.sort(key=lambda b: b["created"], reverse=True)
    
    return all_backups


def get_backup_status() -> Dict:
    """Get the current backup configuration and status."""
    db = SessionLocal()
    try:
        settings = StoreSettings.get(db)
        return {
            "enabled": settings.backup_enabled,
            "storage": settings.backup_storage,
            "schedule": settings.backup_schedule,
            "google_connected": bool(settings.backup_google_token_path and os.path.exists(settings.backup_google_token_path)),
            "google_folder_id": settings.backup_google_folder_id,
            "last_run": settings.backup_last_run.strftime("%Y-%m-%d %H:%M:%S") if settings.backup_last_run else None,
            "last_status": settings.backup_last_status,
            "last_message": settings.backup_last_message,
        }
    finally:
        db.close()
