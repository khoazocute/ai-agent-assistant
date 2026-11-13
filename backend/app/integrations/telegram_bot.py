"""Bot Telegram — kênh điều khiển trên điện thoại.

    python -m app.integrations.telegram_bot          # long polling (dev — không cần domain/HTTPS)

Thiết lập (README → "Kết nối Telegram"):
  1. Nhắn @BotFather → /newbot → lấy token → `.env`: TELEGRAM_BOT_TOKEN=...
  2. Chạy bot, nhắn /start → bot trả lời chat_id của bạn → `.env`: TELEGRAM_ALLOWED_CHAT_IDS=<chat_id>
  3. Chạy lại bot. Chỉ chat_id trong danh sách được dùng (mọi người khác đều bị từ chối).

Lớp này chỉ lo hiển thị (định dạng, nút bấm); xử lý nằm ở ChatService. Agent chạy đồng bộ nên được đẩy
sang thread (`asyncio.to_thread`) để bot vẫn nhận tin khác trong lúc chờ.
"""

from __future__ import annotations

import asyncio
import html
import logging
import re
from collections import deque
from typing import Any

from app.chat import ChatReply, ChatService
from app.harness.orchestration.approvals import ApprovalError, PendingAction
from app.runtime import Runtime

log = logging.getLogger(__name__)
MAX_LEN = 4000  # Telegram giới hạn 4096 ký tự/tin

HELP = (
    "Mình là trợ lý cá nhân của bạn 👋\n"
    "• Chi tiêu: \"trưa ăn phở 45k\", \"tháng này tôi chi bao nhiêu?\"\n"
    "• Lịch: \"chiều mai 3h họp nhóm\", \"mai xếp 2 tiếng học tiếng Anh\"\n"
    "• Email: \"có thư gì mới không?\", \"trả lời anh Minh là em đồng ý\"\n"
    "• 📷 Gửi ảnh hóa đơn → mình đề xuất khoản chi để bạn bấm xác nhận\n"
    "• 🎙 Gửi tin nhắn thoại — mình nghe rồi làm như tin gõ\n\n"
    "/approvals — yêu cầu chờ duyệt · /trace — run gần nhất · /reset — quên ngữ cảnh · /help"
)


# ---------- Hàm thuần (test được, không cần Telegram) ----------

def is_allowed(chat_id: int, allowed: set[int]) -> bool:
    return chat_id in allowed  # danh sách trống = không ai được dùng (fail closed)


def md_to_html(text: str) -> str:
    """Model hay trả markdown (**đậm**, `code`). Chuyển sang HTML an toàn cho Telegram (escape trước)."""
    out = html.escape(text)
    out = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", out, flags=re.S)
    out = re.sub(r"`([^`\n]+)`", r"<code>\1</code>", out)
    return out


def truncate(text: str, limit: int = MAX_LEN) -> str:
    return text if len(text) <= limit else text[: limit - 20] + "\n… (đã cắt bớt)"


def format_reply(reply: ChatReply) -> str:
    body = md_to_html(reply.answer or "(không có câu trả lời)")
    if reply.tools_used:
        body += "\n\n<i>🔧 " + html.escape(" → ".join(dict.fromkeys(reply.tools_used))) + "</i>"
    return truncate(body)


def format_approval(pa: PendingAction) -> str:
    return truncate(f"🔐 <b>Yêu cầu duyệt #{pa.id}</b> · {html.escape(pa.tool)}\n\n"
                    f"{html.escape(pa.summary)}\n\n<i>Hết hạn: {pa.expires_at:%H:%M %d/%m}</i>")


def parse_callback(data: str) -> tuple[str, str, str]:
    """'ap:12:y' → ('ap', '12', 'y') · 'fb:<run_id>:1' → ('fb', run_id, '1')."""
    kind, _, rest = data.partition(":")
    target, _, value = rest.rpartition(":")
    if kind not in ("ap", "fb") or not target or not value:
        raise ValueError(f"callback không hợp lệ: {data!r}")
    return kind, target, value


# ---------- Bot ----------

def build_application(token: str, rt: Runtime, allowed: set[int]) -> Any:
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
    from telegram.constants import ChatAction, ParseMode
    from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters

    chat = ChatService(rt)
    seen_updates: deque[int] = deque(maxlen=500)  # chống xử lý trùng một update (Telegram có thể gửi lại)

    def approval_buttons(pa: PendingAction) -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup([[InlineKeyboardButton("✅ Duyệt", callback_data=f"ap:{pa.id}:y"),
                                      InlineKeyboardButton("❌ Từ chối", callback_data=f"ap:{pa.id}:n")]])

    async def guard(update: Update) -> bool:
        chat_id = update.effective_chat.id
        if is_allowed(chat_id, allowed):
            return True
        log.warning("Từ chối chat_id %s", chat_id)
        if update.effective_message:
            await update.effective_message.reply_text(
                f"Bạn chưa có quyền dùng bot này. chat_id của bạn: {chat_id}\n"
                "Chủ bot thêm số này vào TELEGRAM_ALLOWED_CHAT_IDS trong .env rồi khởi động lại bot.")
        return False

    async def on_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if await guard(update):
            await update.message.reply_text(HELP)

    async def on_reset(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if await guard(update):
            await asyncio.to_thread(chat.reset, "telegram", str(update.effective_chat.id))
            await update.message.reply_text("Đã xoá ngữ cảnh hội thoại. Bắt đầu chủ đề mới nhé.")

    async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await guard(update) or update.update_id in seen_updates:
            return
        seen_updates.append(update.update_id)
        text = (update.message.text or "").strip()[:2000]  # giới hạn độ dài đầu vào
        await context.bot.send_chat_action(update.effective_chat.id, ChatAction.TYPING)
        reply = await asyncio.to_thread(chat.handle, "telegram", str(update.effective_chat.id), text)
        feedback = InlineKeyboardMarkup([[InlineKeyboardButton("👍", callback_data=f"fb:{reply.run_id}:1"),
                                          InlineKeyboardButton("👎", callback_data=f"fb:{reply.run_id}:-1")]])
        await update.message.reply_text(format_reply(reply), parse_mode=ParseMode.HTML,
                                        reply_markup=feedback if reply.run_id else None)
        for pa in reply.approvals:
            await update.message.reply_text(format_approval(pa), parse_mode=ParseMode.HTML,
                                            reply_markup=approval_buttons(pa))

    async def on_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Ảnh hóa đơn → đề xuất khoản chi + nút ✅ Ghi / ❌ Bỏ (không ghi gì khi chưa bấm)."""
        from app.agents.receipt.workflow import ReceiptError

        if not await guard(update):
            return
        msg = update.message
        if msg.photo:
            tg_file, mime = await msg.photo[-1].get_file(), "image/jpeg"  # [-1] = độ phân giải cao nhất
        else:
            tg_file, mime = await msg.document.get_file(), msg.document.mime_type or ""
        await context.bot.send_chat_action(update.effective_chat.id, ChatAction.TYPING)
        image = bytes(await tg_file.download_as_bytearray())
        try:
            proposal, pending = await asyncio.to_thread(rt.propose_receipt, image, mime, "telegram")
        except ReceiptError as e:
            await msg.reply_text(f"⚠ {e}")
            return
        except Exception:
            log.exception("Đọc hóa đơn lỗi")
            await msg.reply_text("Xin lỗi, chưa đọc được ảnh lúc này (lỗi gọi AI). Thử lại sau nhé.")
            return
        if pending is None:
            await msg.reply_text("Mình không đọc được tổng tiền trên ảnh này. Bạn nhắn số tiền giúp mình nhé.")
            return
        await msg.reply_text(format_approval(pending), parse_mode=ParseMode.HTML,
                             reply_markup=approval_buttons(pending))

    async def on_voice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Tin thoại → chữ (faster-whisper trên máy) → xử lý như tin gõ; hiện lại câu đã nghe."""
        from app.integrations.speech import default_transcriber

        if not await guard(update):
            return
        voice = update.message.voice or update.message.audio
        await context.bot.send_chat_action(update.effective_chat.id, ChatAction.TYPING)
        audio = bytes(await (await voice.get_file()).download_as_bytearray())
        heard, reply = await asyncio.to_thread(chat.handle_voice, "telegram", str(update.effective_chat.id), audio,
                                               default_transcriber(), voice.duration or 0)
        prefix = f"🎙 <i>Mình nghe: «{html.escape(heard)}»</i>\n\n" if heard else ""
        await update.message.reply_text(prefix + format_reply(reply), parse_mode=ParseMode.HTML)
        for pa in reply.approvals:
            await update.message.reply_text(format_approval(pa), parse_mode=ParseMode.HTML,
                                            reply_markup=approval_buttons(pa))

    async def on_approvals(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await guard(update):
            return
        pending = await asyncio.to_thread(rt.approvals.list, "pending")
        if not pending:
            await update.message.reply_text("Không có yêu cầu nào đang chờ duyệt.")
        for pa in pending:
            await update.message.reply_text(format_approval(pa), parse_mode=ParseMode.HTML,
                                            reply_markup=approval_buttons(pa))

    async def on_trace(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await guard(update):
            return
        from app.harness.agentops.store import child_runs, recent_runs, run_events

        def last_run_text() -> str:
            runs = [r for r in recent_runs(rt.session_factory, 20) if r.channel == "telegram"]
            if not runs:
                return "Chưa có run nào."
            run, events = run_events(rt.session_factory, runs[0].run_id)
            calls = [e.data["name"] for e in events if e.type == "tool_call"]
            for child in child_runs(rt.session_factory, run.run_id):
                _, child_events = run_events(rt.session_factory, child.run_id)
                calls += [f"{child.agent}.{e.data['name']}" for e in child_events if e.type == "tool_call"]
            return (f"Run {run.run_id}\nAgent: {run.agent} · prompt {run.prompt_version} · {run.status}\n"
                    f"{run.steps} bước · {(run.latency_ms or 0) / 1000:.1f}s · {run.input_tokens} token vào\n"
                    f"Tool: {' → '.join(calls) or '(không)'}\n\nChi tiết: python -m app.cli run {run.run_id}")

        await update.message.reply_text(await asyncio.to_thread(last_run_text))

    async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        if not is_allowed(update.effective_chat.id, allowed):
            await query.answer("Không có quyền.", show_alert=True)
            return
        try:
            kind, target, value = parse_callback(query.data or "")
        except ValueError:
            await query.answer("Nút không hợp lệ.")
            return
        if kind == "fb":
            await asyncio.to_thread(chat.feedback.record, target, int(value), "telegram")
            await query.answer("Cảm ơn phản hồi!")
            await query.edit_message_reply_markup(None)
            return
        actor = f"user:telegram:{update.effective_user.id}"
        try:
            if value == "y":
                pa = await asyncio.to_thread(rt.approve, int(target), actor)
                result = "✅ Đã duyệt và thực hiện." if pa.status == "executed" else f"❌ Thực hiện lỗi: {pa.error}"
            else:
                pa = await asyncio.to_thread(rt.reject, int(target), actor)
                result = "🚫 Đã từ chối — không có gì được thực hiện."
        except ApprovalError as e:
            result = f"⚠ {e}"
        await query.answer()
        await query.edit_message_text(f"{query.message.text_html}\n\n<b>{html.escape(result)}</b>",
                                      parse_mode=ParseMode.HTML)

    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler(["start", "help"], on_start))
    app.add_handler(CommandHandler("reset", on_reset))
    app.add_handler(CommandHandler("approvals", on_approvals))
    app.add_handler(CommandHandler("trace", on_trace))
    app.add_handler(CallbackQueryHandler(on_callback))
    app.add_handler(MessageHandler(filters.PHOTO | filters.Document.IMAGE, on_photo))
    app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, on_voice))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
    return app


def main() -> None:
    import sys

    from app.config import get_settings

    sys.stdout.reconfigure(encoding="utf-8")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)  # httpx log cả URL có chứa token bot
    settings = get_settings()
    if not settings.telegram_bot_token:
        sys.exit("Thiếu TELEGRAM_BOT_TOKEN trong .env — tạo bot qua @BotFather.")
    allowed = settings.allowed_chat_ids
    if not allowed:
        print("⚠ TELEGRAM_ALLOWED_CHAT_IDS trống: bot sẽ từ chối mọi người và báo chat_id để bạn thêm vào .env.")
    app = build_application(settings.telegram_bot_token, Runtime.create(), allowed)
    print("Bot đang chạy (long polling). Ctrl+C để dừng.")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
