"""OAuth2 flow for Google Gmail.

Token flow:
  1. GET  /auth/gmail          → redirect to Google login
  2. GET  /auth/gmail/callback → exchange code for tokens, store on disk
  3. Tokens auto-refresh in gmail_service.py
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter
from fastapi.responses import RedirectResponse, HTMLResponse

from app.config import settings

logger = logging.getLogger("tuesday.gmail_auth")

router = APIRouter(prefix="/auth/gmail", tags=["gmail-auth"])

SCOPES = "https://www.googleapis.com/auth/gmail.readonly https://www.googleapis.com/auth/gmail.send https://www.googleapis.com/auth/gmail.modify"
GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"

_SECRETS_DIR = Path(__file__).resolve().parents[1] / "secrets"


def _token_path() -> Path:
    _SECRETS_DIR.mkdir(parents=True, exist_ok=True)
    return _SECRETS_DIR / "gmail_personal_tokens.json"


def load_tokens() -> dict | None:
    """Load stored Gmail tokens. Returns None if not found."""
    path = _token_path()
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return None


def save_tokens(tokens: dict) -> None:
    """Persist tokens to disk."""
    path = _token_path()
    path.write_text(json.dumps(tokens, indent=2))
    logger.info("Gmail tokens saved")


async def refresh_access_token() -> str | None:
    """Refresh and return a valid access token. Returns None on failure."""
    tokens = load_tokens()
    if not tokens or "refresh_token" not in tokens:
        return None

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            GOOGLE_TOKEN_URL,
            data={
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "grant_type": "refresh_token",
                "refresh_token": tokens["refresh_token"],
            },
        )

    if resp.status_code != 200:
        logger.error(f"Gmail token refresh failed: {resp.status_code} {resp.text[:200]}")
        return None

    new_tokens = resp.json()
    # Google doesn't always re-issue refresh_token
    if "refresh_token" not in new_tokens:
        new_tokens["refresh_token"] = tokens["refresh_token"]
    save_tokens(new_tokens)
    return new_tokens.get("access_token")


def _check_config() -> str | None:
    """Return error message if Google app is not configured."""
    if not settings.google_client_id:
        return "Google app not configured. Set GOOGLE_CLIENT_ID in your .env file."
    return None


@router.get("")
async def start_auth():
    """Redirect user to Google login."""
    if err := _check_config():
        return HTMLResponse(f"<h2>Setup needed</h2><p>{err}</p>", status_code=503)

    params = urlencode({
        "client_id": settings.google_client_id,
        "redirect_uri": settings.google_redirect_uri,
        "response_type": "code",
        "scope": SCOPES,
        "access_type": "offline",  # Needed for refresh_token
        "prompt": "consent",       # Force consent to always get refresh_token
    })
    return RedirectResponse(f"{GOOGLE_AUTH_URL}?{params}")


@router.get("/callback")
async def auth_callback(code: str = "", error: str = ""):
    """Handle OAuth callback from Google."""
    if error:
        return HTMLResponse(f"<h2>Auth failed</h2><p>{error}</p>", status_code=400)

    if not code:
        return HTMLResponse("<h2>No code received</h2>", status_code=400)

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            GOOGLE_TOKEN_URL,
            data={
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": settings.google_redirect_uri,
            },
        )

    if resp.status_code != 200:
        logger.error(f"Gmail token exchange failed: {resp.status_code} {resp.text[:300]}")
        return HTMLResponse(
            f"<h2>Token exchange failed</h2><pre>{resp.text[:500]}</pre>",
            status_code=502,
        )

    tokens = resp.json()
    save_tokens(tokens)

    return HTMLResponse(
        "<h2>Connected!</h2>"
        "<p>Your Gmail account is now linked to Tuesday.</p>"
        "<p>You can close this window and talk to Tuesday.</p>"
    )


@router.get("/status")
async def auth_status():
    """Check if Gmail is connected."""
    connected = load_tokens() is not None
    return {"gmail": "connected" if connected else "not connected"}
