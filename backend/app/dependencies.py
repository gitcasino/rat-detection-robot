"""Shared FastAPI dependencies."""

from __future__ import annotations

from fastapi import Depends, Header, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.database import get_db


def settings_dep() -> Settings:
    return get_settings()


def session_dep(session: Session = Depends(get_db)) -> Session:
    return session


def api_key_guard(
    request: Request,
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    api_key: str | None = Query(default=None),
    settings: Settings = Depends(settings_dep),
) -> None:
    """Optional shared-secret gate for ingestion endpoints.

    No keys configured means the deployment is open, which is the documented
    default for a local-network demo. Keys are compared in constant time.
    """
    import hmac

    expected = settings.api_key_list
    if not expected:
        return
    provided = x_api_key or api_key
    if not provided:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key",
        )
    if not any(hmac.compare_digest(provided, candidate) for candidate in expected):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid API key")
