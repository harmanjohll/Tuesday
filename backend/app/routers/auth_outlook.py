"""OAuth2 flow for Microsoft Graph (Outlook calendar + email).

Supports two accounts:
  - work  : School/M365 account (calendar + email)
  - personal : Personal Outlook.com account

Token flow:
  1. GET  /auth/outlook?account=work   → redirect to Microsoft login
  2. GET  /auth/outlook/callback       → exchange code for tokens, store on disk
  3. Tokens auto-refresh in outlook_service.py
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Query
from fastapi.responses import RedirectResponse, HTMLResponse

from app.config import settings

logger = logging.getLogger("tuesday.outlook_auth")

router = APIRouter(prefix="/auth/outlook", tags=["outlook-auth"])

SCOPES = "offline_access Calendars.ReadWrite Mail.Read Mail.Send"

# Token storage — encrypted in production, plain JSON for now
_SECRETS_DIR = Path(__file__).resolve().parents[1] / "secrets"


def _token_path(account: str) -> Path:
    _SECRETS_DIR.mkdir(parents=True, exist_ok=True)
    return _SECRETS_DIR / f"outlook_{account}_tokens.json"


def _authority(account: str) -> str:
    """Return the OAuth authority URL based on account type."""
    if account == "work":
        # Use tenant ID for work accounts if configured, else 'organizations'
        tenant = settings.microsoft_tenant_id
        if tenant and tenant != "common":
            return f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0"
        return "https://login.microsoftonline.com/organizations/oauth2/v2.0"
    else:
        # Personal accounts use 'consumers' endpoint
        return "https://login.microsoftonline.com/consumers/oauth2/v2.0"


def load_tokens(account: str) -> dict | None:
    """Load stored tokens for an account. Returns None if not found."""
    path = _token_path(account)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return None


def save_tokens(account: str, tokens: dict) -> None:
    """Persist tokens to disk."""
    path = _token_path(account)
    path.write_text(json.dumps(tokens, indent=2))
    logger.info(f"Tokens saved for {account} account")


async def refresh_access_token(account: str) -> str | None:
    """Refresh and return a valid access token. Returns None on failure."""
    tokens = load_tokens(account)
    if not tokens or "refresh_token" not in tokens:
        return None

    authority = _authority(account)
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            f"{authority}/token",
            data={
                "client_id": settings.microsoft_client_id,
                "client_secret": settings.microsoft_client_secret,
                "grant_type": "refresh_token",
                "refresh_token": tokens["refresh_token"],
                "scope": SCOPES,
            },
        )

    if resp.status_code != 200:
        logger.error(f"Token refresh failed for {account}: {resp.status_code} {resp.text[:200]}")
        return None

    new_tokens = resp.json()
    # Preserve refresh_token if not returned (some flows don't re-issue it)
    if "refresh_token" not in new_tokens:
        new_tokens["refresh_token"] = tokens["refresh_token"]
    save_tokens(account, new_tokens)
    return new_tokens.get("access_token")


def _check_config() -> str | None:
    """Return error message if Microsoft app is not configured."""
    if not settings.microsoft_client_id:
        return "Microsoft app not configured. Set MICROSOFT_CLIENT_ID in your .env file."
    return None


@router.get("")
async def start_auth(account: str = Query("work", regex="^(work|personal)$")):
    """Redirect user to Microsoft login."""
    if err := _check_config():
        return HTMLResponse(f"<h2>Setup needed</h2><p>{err}</p>", status_code=503)

    authority = _authority(account)
    params = urlencode({
        "client_id": settings.microsoft_client_id,
        "response_type": "code",
        "redirect_uri": settings.microsoft_redirect_uri,
        "scope": SCOPES,
        "response_mode": "query",
        "state": account,  # Carry account type through OAuth callback
    })
    return RedirectResponse(f"{authority}/authorize?{params}")


@router.get("/callback")
async def auth_callback(code: str = "", error: str = "", state: str = "work"):
    """Handle OAuth callback from Microsoft."""
    if error:
        return HTMLResponse(f"<h2>Auth failed</h2><p>{error}</p>", status_code=400)

    if not code:
        return HTMLResponse("<h2>No code received</h2>", status_code=400)

    account = state if state in ("work", "personal") else "work"
    authority = _authority(account)

    # Exchange authorization code for tokens
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            f"{authority}/token",
            data={
                "client_id": settings.microsoft_client_id,
                "client_secret": settings.microsoft_client_secret,
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": settings.microsoft_redirect_uri,
                "scope": SCOPES,
            },
        )

    if resp.status_code != 200:
        logger.error(f"Token exchange failed: {resp.status_code} {resp.text[:300]}")
        return HTMLResponse(
            f"<h2>Token exchange failed</h2><pre>{resp.text[:500]}</pre>",
            status_code=502,
        )

    tokens = resp.json()
    save_tokens(account, tokens)

    return HTMLResponse(
        f"<h2>Connected!</h2>"
        f"<p>Your <b>{account}</b> Outlook account is now linked to Tuesday.</p>"
        f"<p>You can close this window and talk to Tuesday.</p>"
    )


@router.get("/status")
async def auth_status():
    """Check which accounts are connected."""
    work = load_tokens("work") is not None
    personal = load_tokens("personal") is not None
    return {
        "work": "connected" if work else "not connected",
        "personal": "connected" if personal else "not connected",
    }
