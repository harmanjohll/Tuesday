"""Simple bearer token authentication for production deployment."""

from __future__ import annotations

import secrets
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.config import settings

# Paths that don't require auth
PUBLIC_PATHS = {"/health", "/docs", "/openapi.json"}

# Path prefixes that don't require auth (static frontend assets)
PUBLIC_PREFIXES = ("/assets/", "/favicon", "/icon", "/manifest", "/nebula")


class AuthMiddleware(BaseHTTPMiddleware):
    """Bearer token auth. Disabled when TUESDAY_AUTH_TOKEN is empty."""

    async def dispatch(self, request: Request, call_next):
        token = settings.tuesday_auth_token

        # No token configured = no auth required (dev mode)
        if not token:
            return await call_next(request)

        # Skip auth for public paths
        if request.url.path in PUBLIC_PATHS:
            return await call_next(request)

        # Skip auth for static frontend assets and the root page
        path = request.url.path
        if path == "/" or any(path.startswith(p) for p in PUBLIC_PREFIXES):
            return await call_next(request)

        # Check Authorization header
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            provided = auth_header[7:]
            if secrets.compare_digest(provided, token):
                return await call_next(request)

        # Check query param (for SSE/EventSource which can't set headers)
        query_token = request.query_params.get("token", "")
        if query_token and secrets.compare_digest(query_token, token):
            return await call_next(request)

        return JSONResponse(
            status_code=401,
            content={"error": "Unauthorized. Provide a valid Bearer token."},
        )
