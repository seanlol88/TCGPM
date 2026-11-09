# Update Check System

## Overview

The TCG Preorder Manager includes a built-in update check system accessible from the **Settings > System** page. It works by fetching a simple `version.json` file from a URL you host, comparing the version, and displaying the result to the user.

---

## How It Works

1. The app reads its current version from `config.py` (`APP_VERSION = "1.0.0"`).
2. When you click **"Check for Updates"**, the app fetches a `version.json` file from the URL configured in `config.py` (`UPDATE_CHECK_URL`).
3. It compares the `version` field in the JSON with the current version.
4. If a newer version is available, it shows a download link and any release notes.

---

## The `version.json` File Format

Create a JSON file with this structure:

```json
{
    "version": "1.1.0",
    "download_url": "https://your-domain.com/TCG_Preorder_Manager_Setup_1.1.0.exe",
    "release_notes": "Bug fixes and performance improvements.\nNew feature: customer export.\nUpdated favicon support."
}
```

### Fields

| Field | Required | Description |
|-------|----------|-------------|
| `version` | Yes | The latest version string (e.g., `"1.1.0"`). Must follow `major.minor.patch` format. |
| `download_url` | Yes | Direct download link to the latest installer `.exe` file. |
| `release_notes` | No | Optional release notes. Use `\n` for line breaks. |

---

## How to Host the Update Files

You need to host two things:
1. The `version.json` file (must be publicly accessible via HTTP/HTTPS)
2. The installer `.exe` file (direct download link)

### Option 1: GitHub Releases (Recommended — Free)

1. Go to your GitHub repository → **Releases** → **Draft a new release**
2. Tag the release with the version (e.g., `v1.1.0`)
3. Upload the `TCG_Preorder_Manager_Setup_1.1.0.exe` as a release asset
4. Create a `version.json` file and upload it as a release asset too
5. Set `UPDATE_CHECK_URL` to the raw URL of the `version.json`:

```python
UPDATE_CHECK_URL = "https://raw.githubusercontent.com/your-username/your-repo/main/version.json"
```

Or use the release asset URL:
```
https://github.com/your-username/your-repo/releases/latest/download/version.json
```

**For `download_url` in version.json**, use the release asset download link:
```
https://github.com/your-username/your-repo/releases/download/v1.1.0/TCG_Preorder_Manager_Setup_1.1.0.exe
```

### Option 2: Google Drive

1. Upload `version.json` and the `.exe` installer to a Google Drive folder
2. Right-click each file → **Share** → **Anyone with the link**
3. For `version.json`, get the direct download link:
   - Normal share link: `https://drive.google.com/file/d/FILE_ID/view?usp=sharing`
   - Direct link: `https://drive.google.com/uc?export=download&id=FILE_ID`
4. Set `UPDATE_CHECK_URL` to the direct link of `version.json`

**Note:** For large files (>25MB) on Google Drive, the download link may show a quarantine warning page. For this reason, Google Drive is better for `version.json` only, and you may want to host the `.exe` elsewhere.

### Option 3: Your Own Web Server

1. Upload `version.json` and the `.exe` to any web server
2. Set `UPDATE_CHECK_URL` to the URL of `version.json`:

```python
UPDATE_CHECK_URL = "https://your-domain.com/updates/version.json"
```

3. In `version.json`, set `download_url` to the `.exe` URL:

```json
{
    "version": "1.1.0",
    "download_url": "https://your-domain.com/updates/TCG_Preorder_Manager_Setup_1.1.0.exe",
    "release_notes": "What's new in this version."
}
```

### Option 4: GitHub Gist (Quick & Simple)

1. Go to [gist.github.com](https://gist.github.com)
2. Create a new gist with the `version.json` content
3. Make it a **public** gist
4. Get the raw URL and set it as `UPDATE_CHECK_URL`:

```python
UPDATE_CHECK_URL = "https://gist.githubusercontent.com/your-username/GIST_ID/raw/version.json"
```

---

## Enabling Update Checks

Edit `config.py` and set the `UPDATE_CHECK_URL`:

```python
UPDATE_CHECK_URL = "https://your-hosted-url/version.json"
```

To **disable** update checks, leave it as an empty string:

```python
UPDATE_CHECK_URL = ""
```

You can also set it via environment variable:

```
set UPDATE_CHECK_URL=https://your-hosted-url/version.json
```

---

## Releasing a New Version

When you release a new version:

1. Update `APP_VERSION` in `config.py` to the new version
2. Rebuild the installer (`python build_installer.py`)
3. Update your hosted `version.json` with the new version, download URL, and release notes
4. Users will now see the update available when they click "Check for Updates"

---

## Sample `version.json`

```json
{
    "version": "1.1.0",
    "download_url": "https://github.com/your-username/tcg-preorder-manager/releases/download/v1.1.0/TCG_Preorder_Manager_Setup_1.1.0.exe",
    "release_notes": "Version 1.1.0:\n- Added update check system\n- Integrated favicon package\n- Bug fixes and improvements"
}
```
