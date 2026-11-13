"""Phụ thuộc dùng chung cho các router: runtime, người dùng đã đăng nhập, phiên DB."""

from __future__ import annotations

from collections.abc import Iterator

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.session import session_scope
from app.harness.security.auth import AuthError, verify_token
from app.runtime import Runtime

COOKIE = "session"


def get_runtime(request: Request) -> Runtime:
    return request.app.state.runtime


def require_user(request: Request) -> str:
    token = request.cookies.get(COOKIE)
    secret = get_settings().jwt_secret
    if not token or not secret:
        raise HTTPException(401, "Chưa đăng nhập")
    try:
        return verify_token(secret, token)
    except AuthError as e:
        raise HTTPException(401, str(e)) from e


def db(rt: Runtime = Depends(get_runtime)) -> Iterator[Session]:
    with session_scope(rt.session_factory) as s:
        yield s
