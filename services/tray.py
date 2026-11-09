"""
System tray icon service for TCG Preorder Manager.
Provides a Windows notification area icon with right-click menu options.
"""
import os
import sys
import threading
from io import BytesIO
from pathlib import Path
import webbrowser

try:
    from pystray import Icon as TrayIcon
    from pystray import Menu as tray_menu
    from pystray import MenuItem as tray_menu_item
    from PIL import Image
    HAS_PYSTRAY = True
except ImportError:
    HAS_PYSTRAY = False


def create_icon_image(size=32):
    """Create the icon image for the system tray."""
    if not HAS_PYSTRAY:
        return None

    # Try to use the favicon first
    favicon_path = Path(__file__).parent.parent / "static" / "favicon-32x32.png"
    if favicon_path.exists():
        try:
            img = Image.open(favicon_path)
            img = img.resize((size, size), Image.LANCZOS)
            return img
        except Exception:
            pass

    # Try to use the store logo if available
    logo_path = Path(__file__).parent.parent / "static" / "logos"
    if logo_path.exists():
        logo_files = list(logo_path.glob("*"))
        if logo_files:
            try:
                img = Image.open(logo_files[0])
                img = img.resize((size, size), Image.LANCZOS)
                return img
            except Exception:
                pass

    # Fallback: create a simple icon
    img = Image.new("RGBA", (size, size), (52, 152, 219, 255))
    return img


def restart_app(port=8000):
    """Restart the application by spawning a new process and exiting."""
    # Save the port to a file for the new process
    base_dir = Path(sys.executable).parent if getattr(sys, 'frozen', False) else Path(__file__).parent.parent
    env_file = base_dir / ".app_port"
    env_file.write_text(str(port))
    
    # Spawn new process
    if getattr(sys, 'frozen', False):
        # Running as PyInstaller executable — restart the .exe itself
        exe_path = sys.executable
        if os.name == 'nt':
            os.startfile(exe_path)
        else:
            os.system(f'start {exe_path}')
    else:
        # Running as Python script
        python_exe = sys.executable
        main_path = Path(__file__).parent.parent / "main.py"
        os.system(f'start {python_exe} {main_path}')
    
    # Exit current process
    os._exit(0)


def get_port():
    """Get the current port from database or file."""
    port = 8000
    env_file = Path(__file__).parent.parent / ".app_port"
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


def open_in_browser(port=8000):
    """Open the app's web address in the default system browser."""
    url = f"http://localhost:{port}"
    webbrowser.open(url)
    # Ensure the window comes to the foreground
    import time
    time.sleep(0.1)


def run_tray_icon():
    """Run the system tray icon in a separate thread."""
    if not HAS_PYSTRAY:
        return
    
    icon_img = create_icon_image()
    if icon_img is None:
        return
    
    port = get_port()
    
    menu = tray_menu(
        tray_menu_item("Open in Browser", lambda: open_in_browser(port)),
        tray_menu_item("Restart App", lambda: restart_app(port)),
        tray_menu_item("Close App", lambda: os._exit(0)),
    )
    
    tray = TrayIcon("TCG Preorder Manager", icon_img, "TCG Preorder Manager", menu)
    tray.run_detached()


def start_tray():
    """Start the system tray icon in a background thread."""
    if not HAS_PYSTRAY:
        return
    tray_thread = threading.Thread(target=run_tray_icon, daemon=True)
    tray_thread.start()
