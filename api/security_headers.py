"""Production HTTP security headers -- applied to every response via ASGI
middleware (api/main.py: app.add_middleware(SecurityHeadersMiddleware)).

This is an API-only backend; the actual user-facing frontend is a
SEPARATE Vercel deployment. That matters for two of these headers:

  - CSP here does NOT affect the Vercel frontend's own rendering (CSP is
    per-origin) -- it only governs content THIS backend serves directly.
    Almost everything this backend returns is JSON, where CSP is inert,
    with one deliberate exception: FastAPI's auto-generated /docs and
    /redoc pages, which load Swagger/ReDoc's JS from a CDN via inline
    <script> tags. A strict `default-src 'none'` CSP breaks those pages
    outright. Rather than silently ship a CSP that breaks /docs (or
    silently exempt it without saying so), this middleware applies a
    strict CSP to everything EXCEPT /docs, /redoc, /openapi.json, which
    get a CSP permissive enough for Swagger/ReDoc's known CDN sources.
    If /docs is not meant to be public in production, disable it via
    FastAPI's own `docs_url=None`/`redoc_url=None` at the app level
    instead -- this middleware does not do that itself (a scope decision,
    not this file's job).
  - frame-ancestors/X-Frame-Options here protects against THIS backend's
    own responses (including /docs) being framed -- it says nothing about
    whether the Vercel frontend can be framed, which is that deployment's
    own concern.
"""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

_DOCS_PATHS = {"/docs", "/redoc", "/openapi.json"}

_STRICT_CSP = "default-src 'none'; frame-ancestors 'none'"
# Swagger UI (/docs) and ReDoc (/redoc) load JS/CSS from jsdelivr's CDN and
# use inline styles -- this is FastAPI's own documented default, not a
# choice made here. Kept as narrow as still works, not a blanket allowlist.
_DOCS_CSP = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
    "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
    "img-src 'self' data: https://fastapi.tiangolo.com; "
    "frame-ancestors 'none'"
)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)

        # HSTS: safe to send unconditionally -- browsers only act on it
        # when the page was actually loaded over HTTPS, and Render
        # terminates TLS in front of this process either way.
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        # This API doesn't use any of these browser features; deny all
        # rather than leave them at the (permissive) browser default.
        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=(), payment=(), usb=()"
        )
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Content-Security-Policy"] = (
            _DOCS_CSP if request.url.path in _DOCS_PATHS else _STRICT_CSP
        )

        return response
