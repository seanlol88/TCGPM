import os
from pathlib import Path

# Base directory
BASE_DIR = Path(__file__).resolve().parent

# Database
DATABASE_URL = f"sqlite:///{BASE_DIR / 'database' / 'app.db'}"

# Gmail API
GMAIL_CREDENTIALS_FILE = os.getenv("GMAIL_CREDENTIALS_FILE", str(BASE_DIR / "gmail_credentials.json"))
GMAIL_SENDER_EMAIL = os.getenv("GMAIL_SENDER_EMAIL", "")
GMAIL_TOKEN_FILE = os.getenv("GMAIL_TOKEN_FILE", str(BASE_DIR / "gmail_token.json"))

# App settings
APP_TITLE = "TCG Preorder Manager"
APP_VERSION = "1.0.0"
SESSION_SECRET = os.getenv("SESSION_SECRET", "tcg-preorder-secret-key-change-in-production")

# Update check - host a version.json file at this URL to enable update checks
# Set to empty string to disable update checks
UPDATE_CHECK_URL = os.getenv("UPDATE_CHECK_URL", "https://gist.githubusercontent.com/seanlol88/9d430876f19251805754071ccb416ecf/raw/e3a3584503d0948f73fb4671e1e96d56a67fc550/version.json")

# Google Custom Search API (for image search feature)
# Get API key from: https://console.cloud.google.com/apis/credentials
# Get CX (Search Engine ID) from: https://programmablesearchengine.google.com/controlpanel/all
GOOGLE_SEARCH_API_KEY = os.getenv("GOOGLE_SEARCH_API_KEY", "")
GOOGLE_SEARCH_CX = os.getenv("GOOGLE_SEARCH_CX", "")
