"""Tool của Finance Agent — lớp MỎNG bọc FinanceService (ADR-0004).

Mỗi tool chỉ làm 3 việc: mở phiên DB → gọi đúng 1 hàm service → trả kết quả. Không có nghiệp vụ ở đây.
Docstring + mô tả Field là thứ model đọc: viết cho model hiểu KHI NÀO dùng và tham số nghĩa là gì.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
from typing import Annotated, TypeVar

from pydantic import Field

from app.config import today_vn
from app.db.session import SessionFactory, session_scope
from app.harness.tools.registry import Risk, ToolRegistry, agent_tool
from app.services.finance_service import (
    CategoryKey,
    FinanceError,
    FinanceService,
    Period,
    Summary,
    TransactionOut,
    resolve_period,
)

T = TypeVar("T")

PeriodArg = Annotated[Period | None, Field(
    description="Khoảng thời gian thông dụng (tuần bắt đầu thứ Hai). Bỏ trống nếu dùng start/end.")]
StartArg = Annotated[date | None, Field(description="Ngày bắt đầu YYYY-MM-DD, dùng khi không có period phù hợp")]
EndArg = Annotated[date | None, Field(description="Ngày kết thúc YYYY-MM-DD (tính cả ngày này)")]


def build_finance_tools(session_factory: SessionFactory, today: Callable[[], date] = today_vn) -> ToolRegistry:
    def with_service(fn: Callable[[FinanceService], T]) -> T:
        # Mỗi lần gọi tool = một phiên DB = một transaction: lỗi giữa chừng thì rollback toàn bộ.
        with session_scope(session_factory) as s:
            return fn(FinanceService(s, today))

    def date_range(period: Period | None, start: date | None, end: date | None) -> tuple[date, date]:
        if period:
            return resolve_period(period, today())
        if start and end:
            return start, end
        raise FinanceError("Cần truyền period, hoặc truyền đủ cả start và end.")

    @agent_tool(risk=Risk.WRITE)
    def add_transaction(
        amount_vnd: Annotated[int, Field(gt=0, description="Số tiền VND, số nguyên dương. 45k → 45000")],
        category: Annotated[CategoryKey, Field(description="Danh mục; thu_nhap/phu_cap_gia_dinh là khoản THU")],
        occurred_on: Annotated[date | None, Field(description="Ngày phát sinh YYYY-MM-DD; bỏ trống = hôm nay")]
        = None,
        note: Annotated[str, Field(max_length=200, description="Mô tả ngắn, vd. 'phở bò', 'đổ xăng'")] = "",
    ) -> TransactionOut:
        """Ghi MỘT khoản thu hoặc chi. Người dùng nhắc nhiều khoản thì gọi nhiều lần, mỗi khoản một lần.
        Chỉ gọi khi đã biết rõ số tiền; chưa có số tiền thì hỏi người dùng, không gọi tool này."""
        return with_service(lambda svc: svc.add_transaction(amount_vnd, category, occurred_on, note))

    @agent_tool(risk=Risk.READ)
    def get_summary(period: PeriodArg = None, start: StartArg = None, end: EndArg = None) -> Summary:
        """Tổng chi, tổng thu, chi ròng (= chi − thu) và chi tiết theo danh mục trong một khoảng thời gian.
        Luôn dùng tool này cho câu hỏi về tổng tiền — không tự cộng."""
        s, e = date_range(period, start, end)
        return with_service(lambda svc: svc.get_summary(s, e))

    @agent_tool(risk=Risk.READ)
    def list_transactions(
        period: PeriodArg = None,
        start: StartArg = None,
        end: EndArg = None,
        category: Annotated[CategoryKey | None, Field(description="Lọc theo danh mục")] = None,
        limit: Annotated[int, Field(ge=1, le=50, description="Số giao dịch tối đa, mới nhất trước")] = 20,
    ) -> list[TransactionOut]:
        """Liệt kê các giao dịch (có id) — dùng để xem chi tiết hoặc tìm id trước khi xoá.
        Bỏ trống period/start/end để lấy các giao dịch gần nhất."""
        s, e = (None, None) if not (period or start or end) else date_range(period, start, end)
        return with_service(lambda svc: svc.list_transactions(s, e, category, limit))

    @agent_tool(risk=Risk.DESTRUCTIVE)
    def delete_transaction(
        transaction_id: Annotated[int, Field(description="id lấy từ list_transactions")],
    ) -> TransactionOut:
        """Xoá một giao dịch theo id. Cần người dùng duyệt nên có thể bị từ chối."""
        return with_service(lambda svc: svc.delete_transaction(transaction_id))

    return ToolRegistry([add_transaction, get_summary, list_transactions, delete_transaction])
