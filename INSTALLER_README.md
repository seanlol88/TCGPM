# TCG Preorder Manager - Windows Installer

This guide explains how to package the TCG Preorder Manager as a Windows 10/11 installer.

## Option 1: Automated Build (Recommended)

The easiest way to build the installer is using the automated build script:

```powershell
python build_installer.py
```

This script will:
1. Check your Python installation
2. Install PyInstaller if needed
3. Build the executable
4. Create the Inno Setup installer script
5. Compile the Windows installer (if Inno Setup is installed)

### Prerequisites

- **Python 3.8+** installed
- **Inno Setup 6** (optional, for creating the final .exe installer)
  - Download: https://jrsoftware.org/isdl.php

### If Inno Setup is Not Installed

The build script will still create the executable in the `dist/` folder. You can:
1. Install Inno Setup 6 from the link above
2. Run the build script again to create the installer
3. Or manually compile the installer using `installer_setup.iss`

## Option 2: Manual Build

### Step 1: Install PyInstaller

```powershell
pip install pyinstaller
```

### Step 2: Build the Executable

```powershell
pyinstaller --clean --noconfirm "TCG Preorder Manager.spec"
```

This creates the executable in the `dist/` folder.

### Step 3: Create the Installer (Optional)

If you have Inno Setup 6 installed:

```powershell
"C:\Program Files (x86)\Inno Setup 6\iscc.exe" installer_setup.iss
```

The installer will be created in the `installer/` folder.

## Running the Installer

1. Run `TCG_Preorder_Manager_Setup_1.0.0.exe`
2. Follow the installation wizard
3. Choose installation directory (default: `C:\Program Files\TCG Preorder Manager`)
4. Optional: Create desktop shortcut
5. Optional: Start app on Windows login
6. Click "Finish" to complete installation

## Running the Application

After installation, you can:
- Launch from the Start Menu
- Click the desktop shortcut (if created)
- Run `TCG Preorder Manager.exe` directly from the installation folder

The app will automatically open your default browser to `http://localhost:8000`.

## Configuration

### Gmail Integration

To enable email receipts:
1. Create a Google Cloud project
2. Enable Gmail API and Drive API
3. Download OAuth credentials as `gmail_credentials.json`
4. Place it in the installation folder
5. Go to Settings → connect Gmail

### Google Drive Backups

To enable Google Drive backups:
1. Download OAuth credentials as `drive_credentials.json`
2. Place it in the installation folder
3. Go to Settings → Backups → connect Google Drive

## Troubleshooting

### Windows Defender Blocks the Executable

Right-click the .exe → Properties → Unblock → Apply

### Port Already in Use

Go to Settings → System → change the port number → restart the app

### Database Not Found

The database is created automatically in the `database/` folder on first run.

## File Structure After Installation

```
C:\Program Files\TCG Preorder Manager\
├── TCG Preorder Manager.exe    # Main application
├── database/                    # SQLite database (auto-created)
├── backups/                     # Local backups
├── static/                      # Uploaded logos and files
├── templates/                   # Web templates
├── models/                      # Database models
├── api/                         # API routes
├── services/                    # Business logic
├── config.py                    # Configuration
└── migrate.py                   # Database migration script
```

## Uninstalling

- Use "Add or Remove Programs" in Windows Settings
- Or run the uninstaller from the Start Menu

## Support

For issues or questions, check the application logs or contact support.