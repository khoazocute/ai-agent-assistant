"""Ứng dụng web (FastAPI): API cho website + phục vụ bản build React (frontend/dist) ở cùng domain.

    cd backend
    uvicorn app.main:app --reload            # dev: API ở http://localhost:8000, React dev ở :5173 (proxy /api)

Cùng một domain cho API và giao diện → không cần mở CORS; cookie đăng nhập SameSite=Lax hoạt động.
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from app.api.deps import require_user
from app.config import ROOT, get_settings
from app.harness.orchestration.approvals import ApprovalError
from app.runtime import Runtime
from app.services.email_service import EmailError
from app.services.finance_service import FinanceError
from app.services.schedule_service import ScheduleError

FRONTEND_DIST = ROOT / "frontend" / "dist"
log = logging.getLogger(__name__)


def create_app(runtime: Runtime | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        rt = app.state.runtime = runtime or Runtime.create()
        rt.bus.bind(asyncio.get_running_loop())
        bot = app.state.telegram = await _start_telegram(rt)
        scheduler = _start_jobs(rt)
        yield
        if scheduler is not None:
            scheduler.shutdown(wait=False)
        if bot is not None:
            await _stop_telegram(bot)

    app = FastAPI(title="Trợ lý cá nhân multi-agent", version="0.1.0", lifespan=lifespan)
    if runtime is not None:
        app.state.runtime = runtime  # test dùng TestClient không qua lifespan vẫn có runtime

    from app.api import agentops, approvals, auth, chat, email, finance, schedule

    for module in (auth, finance, schedule, email, approvals, agentops, chat):
        app.include_router(module.router)

    @app.exception_handler(FinanceError)
    @app.exception_handler(ScheduleError)
    @app.exception_handler(EmailError)
    @app.exception_handler(ApprovalError)
    async def business_error(request: Request, exc: Exception) -> JSONResponse:
        # Lỗi nghiệp vụ (số tiền âm, trùng trạng thái…) → 400 với thông điệp tiếng Việt cho người dùng.
        return JSONResponse({"detail": str(exc)}, status_code=400)

    @app.get("/api/stream", include_in_schema=False)
    async def stream(request: Request, user: str = Depends(require_user)) -> StreamingResponse:
        # SSE: trình duyệt giữ một kết nối HTTP; server đẩy {"topic": "finance"|"schedule"|…} khi dữ liệu đổi.
        return StreamingResponse(request.app.state.runtime.bus.subscribe(), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    @app.post("/api/telegram/webhook", include_in_schema=False)
    async def telegram_webhook(request: Request) -> dict:
        import hmac

        from fastapi import HTTPException

        bot = getattr(request.app.state, "telegram", None)
        secret = get_settings().telegram_webhook_secret
        given = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
        # Chỉ Telegram biết secret (đặt lúc set_webhook) → chặn ai đó tự POST update giả vào đây.
        if not secret or not hmac.compare_digest(given.encode(), secret.encode()):
            raise HTTPException(403, "Sai secret")
        if bot is None:
            raise HTTPException(503, "Bot chưa chạy ở chế độ webhook")
        from telegram import Update

        await bot.process_update(Update.de_json(await request.json(), bot.bot))
        return {"ok": True}

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok"}

    @app.get("/ready")
    def ready(request: Request) -> dict:
        from sqlalchemy import text

        with request.app.state.runtime.session_factory() as s:
            s.execute(text("SELECT 1"))
        return {"status": "ready"}

    if FRONTEND_DIST.exists():
        app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

        @app.get("/{path:path}", include_in_schema=False)
        def spa(path: str) -> FileResponse:
            # React Router xử lý đường dẫn phía trình duyệt → mọi đường không phải /api trả index.html.
            target = FRONTEND_DIST / path
            return FileResponse(target if path and target.is_file() else FRONTEND_DIST / "index.html")

    return app


async def _start_telegram(rt: Runtime):
    """Bot chạy CHUNG tiến trình với web → tin Telegram ghi DB → SSE → web cập nhật.
    polling: bot tự hỏi Telegram (dev, không cần domain) · webhook: Telegram gọi vào URL HTTPS của mình (production).
    """
    settings = get_settings()
    if settings.telegram_mode not in ("polling", "webhook") or not settings.telegram_bot_token:
        return None
    from app.integrations.telegram_bot import build_application

    bot = build_application(settings.telegram_bot_token, rt, settings.allowed_chat_ids)
    await bot.initialize()
    await bot.start()
    if settings.telegram_mode == "polling":
        await bot.updater.start_polling(drop_pending_updates=True)
    else:
        if not settings.public_base_url.startswith("https://") or len(settings.telegram_webhook_secret) < 16:
            raise RuntimeError("Webhook cần PUBLIC_BASE_URL https://… và TELEGRAM_WEBHOOK_SECRET ≥ 16 ký tự")
        await bot.bot.set_webhook(f"{settings.public_base_url.rstrip('/')}/api/telegram/webhook",
                                  secret_token=settings.telegram_webhook_secret, drop_pending_updates=True)
    log.info("Telegram bot đang chạy (%s) trong tiến trình web", settings.telegram_mode)
    return bot


def _start_jobs(rt: Runtime):
    if runtime_is_test(rt) or not get_settings().jobs_enabled:
        return None
    from app.jobs.scheduler import Jobs, build_scheduler
    from app.notify import default_notifier

    scheduler = build_scheduler(Jobs(rt, default_notifier()))
    scheduler.start()
    log.info("Job nền đã chạy: %s", [j.id for j in scheduler.get_jobs()])
    return scheduler


def runtime_is_test(rt: Runtime) -> bool:
    return str(rt.session_factory.kw["bind"].url) == "sqlite://"


async def _stop_telegram(bot) -> None:
    if bot.updater and bot.updater.running:
        await bot.updater.stop()
    await bot.stop()
    await bot.shutdown()


app = create_app()
