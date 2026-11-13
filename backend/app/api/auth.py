from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel

from app.api.deps import COOKIE, require_user
from app.config import get_settings
from app.harness.security.auth import LoginRateLimiter, check_password, create_token

router = APIRouter(prefix="/api/auth", tags=["auth"])
limiter = LoginRateLimiter()


class LoginIn(BaseModel):
    password: str


@router.post("/login")
def login(body: LoginIn, request: Request, response: Response) -> dict:
    settings = get_settings()
    if not settings.web_password or len(settings.jwt_secret) < 32:
        raise HTTPException(503, "Chưa cấu hình WEB_PASSWORD và JWT_SECRET (≥ 32 ký tự) trong .env")
    ip = request.client.host if request.client else "?"
    if limiter.blocked(ip):
        raise HTTPException(429, "Sai quá nhiều lần — thử lại sau 5 phút")
    if not check_password(body.password, settings.web_password):
        limiter.fail(ip)
        raise HTTPException(401, "Sai mật khẩu")
    limiter.reset(ip)
    response.set_cookie(COOKIE, create_token(settings.jwt_secret, "owner"), httponly=True, samesite="lax",
                        secure=settings.cookie_secure, max_age=7 * 24 * 3600)
    return {"ok": True}


@router.post("/logout")
def logout(response: Response) -> dict:
    response.delete_cookie(COOKIE)
    return {"ok": True}


@router.get("/me")
def me(user: str = Depends(require_user)) -> dict:
    return {"user": user}
