"""
Desktop shortcut creation service for TCG Preorder Manager.
Creates a .url shortcut on the Windows desktop that opens the app in the browser.
"""
import os
import sys
from pathlib import Path


def get_app_port():
    """Get the current port from database or file."""
    port = 8000
    base_dir = Path(__file__).parent.parent
    env_file = base_dir / ".app_port"
    if env_file.exists():
        try:
            port = int(env_file.read_text().strip())
        except (ValueError, IOError):
            pass
    # Check database
    try:
        from models.base import SessionLocal
        from models.store_settings import StoreSettings
        db = SessionLocal()
        settings = StoreSettings.get(db)
        if settings and settings.app_port:
            port = settings.app_port
        db.close()
    except Exception:
        pass
    return port


def create_desktop_shortcut():
    """Create a desktop shortcut (.url file) that opens the app in the default browser."""
    if sys.platform != "win32":
        return False

    port = get_app_port()
    url = f"http://localhost:{port}"

    # Get the desktop path
    desktop = Path(os.path.expanduser("~")) / "Desktop"
    if not desktop.exists():
        # Fallback to user profile if Desktop doesn't exist
        desktop = Path(os.path.expanduser("~"))

    shortcut_path = desktop / "TCG Preorder Manager.url"

    # Create .url file (InternetShortcut format)
    content = f"[InternetShortcut]\nURL={url}\nIconIndex=0\n"
    shortcut_path.write_text(content, encoding="utf-8")

    return True


def create_start_menu_shortcut():
    """Create a Start Menu shortcut that opens the app in the default browser."""
    if sys.platform != "win32":
        return False

    port = get_app_port()
    url = f"http://localhost:{port}"

    # Get the Start Menu Programs path
    start_menu = Path(os.path.expanduser("~")) / "AppData" / "Roaming" / "Microsoft" / "Windows" / "Start Menu" / "Programs"
    start_menu.mkdir(parents=True, exist_ok=True)

    shortcut_path = start_menu / "TCG Preorder Manager.url"

    # Create .url file
    content = f"[InternetShortcut]\nURL={url}\nIconIndex=0\n"
    shortcut_path.write_text(content, encoding="utf-8")

    return True
