"""Test Google Drive API connection and folder creation."""
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

token_path = r"C:\Users\seana\PycharmProjects\PythonProject\database\drive_token.json"

print("Loading credentials...")
creds = Credentials.from_authorized_user_file(token_path)
print("Scopes:", creds.scopes)

print("Building Drive service...")
service = build("drive", "v3", credentials=creds)

# Try searching for the folder
print("\nSearching for folder...")
try:
    results = service.files().list(
        q="name = 'TCG Preorder Manager Backups' and mimeType = 'application/vnd.google-apps.folder' and trashed = false",
        pageSize=10,
        fields="files(id, name)",
    ).execute()
    print("Search results:", results)
except HttpError as e:
    print("HttpError:", e)
    print("Error details:", e.error_details)
    print("Error status:", e.status_code)
except Exception as e:
    print("Error:", type(e).__name__, str(e))

# Try creating the folder
print("\nTrying to create folder...")
try:
    folder_metadata = {"name": "TCG Preorder Manager Backups", "mimeType": "application/vnd.google-apps.folder"}
    folder = service.files().create(body=folder_metadata, fields="id,name").execute()
    print("Created folder:", folder)
except HttpError as e:
    print("HttpError:", e)
    print("Error details:", e.error_details)
    print("Error status:", e.status_code)
except Exception as e:
    print("Error:", type(e).__name__, str(e))

# Try listing files
print("\nListing files...")
try:
    results = service.files().list(pageSize=5, fields="files(id, name)").execute()
    files = results.get("files", [])
    print(f"Found {len(files)} files:")
    for f in files:
        print(f"  - {f['name']} (id: {f['id']})")
except HttpError as e:
    print("HttpError:", e)
    print("Error details:", e.error_details)
    print("Error status:", e.status_code)
except Exception as e:
    print("Error:", type(e).__name__, str(e))
