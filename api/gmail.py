"""API routes for Gmail OAuth2 connection."""
import os
import json

from fastapi import APIRouter, Request, Query
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates

import config
from models.base import SessionLocal
from models.store_settings import StoreSettings
from services.audit import log_change

router = APIRouter()
templates: Jinja2Templates = None  # type: ignore[assignment]

# Gmail OAuth2 configuration
GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.send"]
GMAIL_REDIRECT_URI = "http://localhost:8000/gmail/callback"


@router.get("/gmail/connect")
def gmail_connect(request: Request):
    """Start the Gmail OAuth2 flow."""
    try:
        from google_auth_oauthlib.flow import Flow

        if not os.path.exists(config.GMAIL_CREDENTIALS_FILE):
            return RedirectResponse(
                url="/settings?error=Gmail credentials file not found. Please download 'gmail_credentials.json' from your Google Cloud project and place it in the project root.",
                status_code=303,
            )

        flow = Flow.from_client_secrets_file(
            config.GMAIL_CREDENTIALS_FILE,
            scopes=GMAIL_SCOPES,
            redirect_uri=GMAIL_REDIRECT_URI,
        )

        authorization_url, state = flow.authorization_url(
            access_type="offline",
            prompt="consent",
        )

        # Store only the state in the session (serialization() was removed in newer versions)
        request.session["gmail_oauth_state"] = state

        return RedirectResponse(url=authorization_url, status_code=302)
    except Exception as e:
        return RedirectResponse(
            url=f"/settings?error=Failed to start Gmail connection: {str(e)}",
            status_code=303,
        )


@router.get("/gmail/callback")
def gmail_callback(request: Request, code: str = None, error: str = None):
    """Handle the Gmail OAuth2 callback."""
    if error:
        return RedirectResponse(
            url=f"/settings?error=Gmail connection denied: {error}",
            status_code=303,
        )

    if not code:
        return RedirectResponse(url="/settings?error=No authorization code received.", status_code=303)

    try:
        from google_auth_oauthlib.flow import Flow

        state = request.session.get("gmail_oauth_state")
        if not state:
            return RedirectResponse(url="/settings?error=OAuth session expired. Please try again.", status_code=303)

        # Recreate the flow with the stored state (instead of reverse_serialization)
        flow = Flow.from_client_secrets_file(
            config.GMAIL_CREDENTIALS_FILE,
            scopes=GMAIL_SCOPES,
            state=state,
        )
        flow.redirect_uri = GMAIL_REDIRECT_URI
        flow.fetch_token(code=code)

        # Save the token
        os.makedirs(os.path.dirname(config.GMAIL_TOKEN_FILE) or ".", exist_ok=True)
        with open(config.GMAIL_TOKEN_FILE, "w") as f:
            json.dump({
                "token": flow.credentials.token,
                "refresh_token": flow.credentials.refresh_token,
                "token_uri": flow.credentials.token_uri,
                "client_id": flow.credentials.client_id,
                "client_secret": flow.credentials.client_secret,
                "scopes": flow.credentials.scopes,
            }, f)

        log_change("settings", None, "Connected Gmail for email sending", None)

        return RedirectResponse(url="/settings?success=1&gmail_connected=1", status_code=303)
    except Exception as e:
        return RedirectResponse(
            url=f"/settings?error=Failed to connect Gmail: {str(e)}",
            status_code=303,
        )


@router.post("/gmail/disconnect")
def gmail_disconnect(request: Request):
    """Disconnect Gmail by removing the token."""
    if os.path.exists(config.GMAIL_TOKEN_FILE):
        try:
            os.remove(config.GMAIL_TOKEN_FILE)
        except OSError:
            pass

    log_change("settings", None, "Disconnected Gmail", None)
    return RedirectResponse(url="/settings?success=1", status_code=303)


@router.get("/gmail/status")
def gmail_status():
    """Check if Gmail is connected."""
    connected = os.path.exists(config.GMAIL_TOKEN_FILE)
    return JSONResponse(content={"connected": connected})
