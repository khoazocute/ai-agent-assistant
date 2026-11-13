import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api, toDateStr, vnd, type Approval, type EventItem, type Summary } from "../api";
import { ApprovalCard, Stat } from "../components";

export default function Dashboard() {
  const today = toDateStr(new Date());
  const summary = useQuery({ queryKey: ["summary", "this_month"],
    queryFn: () => api<Summary>("/api/finance/summary?period=this_month") });
  const todaySpend = useQuery({ queryKey: ["summary", "today"],
    queryFn: () => api<Summary>("/api/finance/summary?period=today") });
  const events = useQuery({ queryKey: ["events", today, today],
    queryFn: () => api<EventItem[]>(`/api/events?start=${today}&end=${today}`) });
  const approvals = useQuery({ queryKey: ["approvals", "pending"], queryFn: () => api<Approval[]>("/api/approvals") });

  return (
    <>
      <h1>Tổng quan</h1>
      <div className="grid">
        <Stat label="Chi hôm nay" value={vnd(todaySpend.data?.total_expense_vnd)} />
        <Stat label="Chi tháng này" value={vnd(summary.data?.total_expense_vnd)} />
        <Stat label="Thu tháng này" value={vnd(summary.data?.total_income_vnd)} tone="income" />
        <Stat label="Chi ròng (chi − thu)" value={vnd(summary.data?.net_spending_vnd)} />
      </div>

      <div className="grid section">
        <div className="card">
          <div className="spread"><h2>Lịch hôm nay</h2><Link to="/calendar" className="small">Xem lịch →</Link></div>
          {events.data?.length ? (
            <table><tbody>
              {events.data.map((e) => (
                <tr key={e.id}>
                  <td className="mono">{e.start_at.slice(11, 16)}–{e.end_at.slice(11, 16)}</td>
                  <td>{e.title}</td>
                </tr>
              ))}
            </tbody></table>
          ) : <p className="muted">Không có sự kiện nào hôm nay.</p>}
        </div>
        <div className="card">
          <div className="spread"><h2>Chi nhiều nhất tháng này</h2><Link to="/finance" className="small">Chi tiết →</Link></div>
          {summary.data?.by_category.filter((c) => c.kind === "expense").slice(0, 5).map((c) => (
            <div key={c.category} className="spread small">
              <span>{c.category_name}</span>
              <span className="mono">{vnd(c.amount_vnd)} · {c.percent_of_expense}%</span>
            </div>
          )) ?? null}
          {!summary.data?.by_category.length && <p className="muted">Chưa có giao dịch.</p>}
        </div>
      </div>

      <div className="section">
        <h2>Chờ duyệt ({approvals.data?.length ?? 0})</h2>
        <div className="stack">
          {approvals.data?.map((a) => <ApprovalCard key={a.id} approval={a} />)}
          {!approvals.data?.length && <p className="muted">Không có yêu cầu nào. <Link to="/chat">Nhắn trợ lý →</Link></p>}
        </div>
      </div>
    </>
  );
}
