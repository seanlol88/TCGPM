"""
Build script for TCG Preorder Manager Windows Installer.

This script automates the entire build process:
1. Installs PyInstaller if not already installed
2. Builds the executable using PyInstaller
3. Creates the Inno Setup installer script
4. Compiles the Windows installer (.exe)

Usage:
    python build_installer.py
"""

import subprocess
import sys
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent
DIST_DIR = PROJECT_ROOT / "dist"
BUILD_DIR = PROJECT_ROOT / "build"
SPEC_FILE = PROJECT_ROOT / "TCG Preorder Manager.spec"


def print_step(step, message):
    print(f"\n{'='*60}")
    print(f"Step {step}: {message}")
    print(f"{'='*60}")


def run_command(cmd, cwd=None):
    """Run a command and return the result."""
    print(f"Running: {' '.join(cmd) if isinstance(cmd, list) else cmd}")
    result = subprocess.run(
        cmd,
        cwd=cwd,
        capture_output=True,
        text=True,
        shell=isinstance(cmd, str)
    )
    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(result.stderr)
    return result.returncode == 0


def check_python():
    """Check Python version."""
    print_step(0, "Checking Python version")
    version = sys.version
    print(f"Python: {version}")
    
    # Check if running in virtual environment
    if hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix):
        print("✓ Running in virtual environment")
    else:
        print("⚠ Not running in virtual environment. Consider using one.")
    
    return True


def install_pyinstaller():
    """Install PyInstaller if not already installed."""
    print_step(1, "Checking PyInstaller")
    
    try:
        import PyInstaller
        print(f"✓ PyInstaller {PyInstaller.__version__} is installed")
        return True
    except ImportError:
        print("Installing PyInstaller...")
        success = run_command([sys.executable, "-m", "pip", "install", "pyinstaller"])
        if success:
            print("✓ PyInstaller installed successfully")
            return True
        else:
            print("✗ Failed to install PyInstaller")
            return False


def create_spec_file():
    """Create the PyInstaller spec file."""
    print_step(2, "Creating PyInstaller spec file")
    
    spec_content = '''# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('templates', 'templates'),
        ('static', 'static'),
        ('config.py', '.'),
        ('migrate.py', '.'),
        ('models', 'models'),
        ('api', 'api'),
        ('services', 'services'),
        ('database', 'database'),
        ('backups', 'backups'),
        ('gmail_credentials.json', '.'),
        ('drive_credentials.json', '.'),
    ],
    hiddenimports=[
        'jinja2',
        'uvicorn',
        'fastapi',
        'sqlalchemy',
        'starlette',
        'google',
        'google.api',
        'google.api_core',
        'google.auth',
        'google.oauth2',
        'googleapiclient',
        'googleapiclient.discovery',
        'reportlab',
        'reportlab.pdfgen',
        'itsdangerous',
        'pystray',
        'PIL',
        'PIL.Image',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='TCG Preorder Manager',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='static/favicon.ico',
)
'''
    
    with open(SPEC_FILE, 'w', encoding='utf-8') as f:
        f.write(spec_content)
    
    print(f"✓ Spec file created: {SPEC_FILE}")
    return True


def build_executable():
    """Build the executable using PyInstaller."""
    print_step(3, "Building executable with PyInstaller")
    
    # Clean previous builds
    print("Cleaning previous builds...")
    if DIST_DIR.exists():
        import shutil
        shutil.rmtree(DIST_DIR)
    if BUILD_DIR.exists():
        import shutil
        shutil.rmtree(BUILD_DIR)
    
    # Build using the spec file
    success = run_command([
        sys.executable, "-m", "PyInstaller",
        str(SPEC_FILE),
        "--clean",
        "--noconfirm"
    ])
    
    if success:
        exe_path = DIST_DIR / "TCG Preorder Manager.exe"
        if exe_path.exists():
            size_mb = exe_path.stat().st_size / (1024 * 1024)
            print(f"✓ Executable built: {exe_path} ({size_mb:.1f} MB)")
            return True
    
    print("✗ Failed to build executable")
    return False


def create_inno_setup_script():
    """Create the Inno Setup installer script."""
    print_step(4, "Creating Inno Setup script")
    
    inno_script = """; Inno Setup Script for TCG Preorder Manager
; Generated by build_installer.py

#define MyAppName "TCG Preorder Manager"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "TCG Preorder Manager"
#define MyAppURL "http://localhost:8000"
#define MyAppExeName "TCG Preorder Manager.exe"

[Setup]
AppId={{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\\{#MyAppName}
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
OutputDir=installer
OutputBaseFilename=TCG_Preorder_Manager_Setup_{#MyAppVersion}
SetupIconFile=static\favicon.ico
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "quicklaunchicon"; Description: "{cm:CreateQuickLaunchIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked; OnlyBelowVersion: 6.1; Check: not IsAdminInstallMode
Name: "autostart"; Description: "Start app on Windows login"; GroupDescription: "Startup:"; Flags: unchecked

[Files]
Source: "dist\\TCG Preorder Manager.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "dist\\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
; Note: Don't use "Flags: ignoreversion" on any shared system files

[Icons]
Name: "{group}\\{#MyAppName}"; Filename: "{app}\\{#MyAppExeName}"
Name: "{group}\\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\\{#MyAppName}"; Filename: "{app}\\{#MyAppExeName}"; Tasks: desktopicon
Name: "{userappdata}\\Microsoft\\Internet Explorer\\Quick Launch\\{#MyAppName}"; Filename: "{app}\\{#MyAppExeName}"; Tasks: quicklaunchicon

[Ini]
; Add auto-start registry entry
Filename: "{userappdata}\\Microsoft\\Windows\\Start Menu\\Programs\\Startup\\TCG Preorder Manager.lnk"; Section: "InternetShortcut"; Key: "URL"; String: "{app}\\{#MyAppExeName}"; Tasks: autostart

[Run]
Filename: "{app}\\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[Code]
function InitializeSetup(): Boolean;
var
  ResultCode: Integer;
begin
  Result := True;
  
  // Check if app is already running
  if RegValueExists(HKEY_CURRENT_USER, 'Software\\Microsoft\\Windows\\CurrentVersion\\Run', 'TCGPreorderManager') then
  begin
    if MsgBox('TCG Preorder Manager may be running. Close it before installing?', mbConfirmation, MB_OKCANCEL) = IDCANCEL then
    begin
      Result := False;
    end;
  end;
end;
"""
    
    inno_file = PROJECT_ROOT / "installer_setup.iss"
    with open(inno_file, 'w', encoding='utf-8') as f:
        f.write(inno_script)
    
    print(f"✓ Inno Setup script created: {inno_file}")
    return True


def check_inno_setup():
    """Check if Inno Setup is installed."""
    print_step(5, "Checking Inno Setup")
    
    # Common Inno Setup locations
    inno_paths = [
        r"C:\Program Files (x86)\Inno Setup 6\iscc.exe",
        r"C:\Program Files\Inno Setup 6\iscc.exe",
        r"C:\Program Files (x86)\Inno Setup 5\iscc.exe",
        r"C:\Program Files\Inno Setup 5\iscc.exe",
    ]
    
    for path in inno_paths:
        if Path(path).exists():
            print(f"✓ Inno Setup found: {path}")
            return path
    
    print("✗ Inno Setup not found")
    print("\nTo install Inno Setup:")
    print("1. Download from: https://jrsoftware.org/isdl.php")
    print("2. Install Inno Setup 6")
    print("3. Run this script again")
    return None


def build_installer(inno_path):
    """Build the Windows installer using Inno Setup."""
    print_step(6, "Building Windows installer")
    
    success = run_command([inno_path, str(PROJECT_ROOT / "installer_setup.iss")])
    
    if success:
        installer_file = PROJECT_ROOT / "installer" / "TCG_Preorder_Manager_Setup_1.0.0.exe"
        if installer_file.exists():
            size_mb = installer_file.stat().st_size / (1024 * 1024)
            print(f"\n{'='*60}")
            print(f"✓ Installer built successfully!")
            print(f"  Location: {installer_file}")
            print(f"  Size: {size_mb:.1f} MB")
            print(f"{'='*60}")
            return True
    
    print("✗ Failed to build installer")
    return False


def main():
    print("\n" + "="*60)
    print("TCG Preorder Manager - Windows Installer Builder")
    print("="*60)
    
    # Step 0: Check Python
    if not check_python():
        return
    
    # Step 1: Install PyInstaller
    if not install_pyinstaller():
        return
    
    # Step 2: Create spec file
    if not create_spec_file():
        return
    
    # Step 3: Build executable
    if not build_executable():
        print("\n✗ Build failed. Please check the errors above.")
        return
    
    # Step 4: Create Inno Setup script
    if not create_inno_setup_script():
        return
    
    # Step 5: Check Inno Setup
    inno_path = check_inno_setup()
    if inno_path is None:
        print("\n" + "="*60)
        print("Partial build complete!")
        print(f"  Executable: {DIST_DIR / 'TCG Preorder Manager.exe'}")
        print(f"  Inno Setup script: {PROJECT_ROOT / 'installer_setup.iss'}")
        print("\nInstall Inno Setup 6 to create the final installer:")
        print("https://jrsoftware.org/isdl.php")
        print("="*60)
        return
    
    # Step 6: Build installer
    if not build_installer(inno_path):
        print("\n✗ Installer build failed. Please check the errors above.")
        return
    
    print("\n" + "="*60)
    print("Build complete! Your installer is ready.")
    print("="*60)


if __name__ == "__main__":
    main()