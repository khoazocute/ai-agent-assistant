import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api, fmtTime, type Approval, type Draft, type EmailView } from "../api";
import { ApprovalCard, ErrorBox, StatusBadge } from "../components";

const CATEGORY_LABEL: Record<string, string> = {
  important: "Quan trọng", needs_reply: "Cần trả lời", newsletter: "Bản tin / QC", other: "Khác",
};

export default function Inbox() {
  const qc = useQueryClient();
  const [tab, setTab] = useState<"pending" | "all">("pending");
  const approvals = useQuery({ queryKey: ["approvals", tab],
    queryFn: () => api<Approval[]>(`/api/approvals?status=${tab === "pending" ? "pending" : ""}`) });
  const emails = useQuery({ queryKey: ["emails"], queryFn: () => api<EmailView[]>("/api/emails") });
  const drafts = useQuery({ queryKey: ["drafts"], queryFn: () => api<Draft[]>("/api/emails/drafts") });
  const sync = useMutation({ mutationFn: () => api("/api/emails/sync", { method: "POST" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["emails"] }) });

  return (
    <>
      <h1>Email & Duyệt</h1>
      <div className="spread">
        <h2>Yêu cầu duyệt</h2>
        <div className="row">
          <button className={tab === "pending" ? "primary" : ""} onClick={() => setTab("pending")}>Đang chờ</button>
          <button className={tab === "all" ? "primary" : ""} onClick={() => setTab("all")}>Tất cả</button>
        </div>
      </div>
      <div className="stack">
        {approvals.data?.map((a) => <ApprovalCard key={a.id} approval={a} />)}
        {!approvals.data?.length && <p className="muted">Không có yêu cầu nào.</p>}
      </div>

      <div className="section spread">
        <h2>Hộp thư</h2>
        <button disabled={sync.isPending} onClick={() => sync.mutate()}>↻ Kéo thư mới</button>
      </div>
      <ErrorBox error={sync.error} />
      <div className="stack">
        {emails.data?.map((m) => (
          <div key={m.id} className="card">
            <div className="spread">
              <strong>{m.subject}</strong>
              <span className="row small">
                {m.category && <span className="badge info">{CATEGORY_LABEL[m.category] ?? m.category}</span>}
                <span className="muted">{fmtTime(m.received_at)}</span>
              </span>
            </div>
            <div className="small muted">{m.from_addr}</div>
            {m.injection_flags.length > 0 && (
              <div className="warn-box small section">⚠ Thư có dấu hiệu cố điều khiển trợ lý: {m.injection_flags.join(", ")}</div>
            )}
            <p className="small">{m.summary || m.snippet}</p>
          </div>
        ))}
        {!emails.data?.length && <p className="muted">Chưa có thư. Kết nối Gmail (README) rồi bấm "Kéo thư mới".</p>}
      </div>

      <h2 className="section">Bản nháp</h2>
      <div className="stack">
        {drafts.data?.map((d) => (
          <div key={d.id} className="card">
            <div className="spread"><strong>#{d.id} · {d.subject}</strong><StatusBadge status={d.status} /></div>
            <div className="small muted">Tới: {d.to.join(", ")}</div>
            <pre className="box small">{d.body}</pre>
            {d.pii_warnings.length > 0 && <div className="warn-box small section">⚠ {d.pii_warnings.join(", ")}</div>}
          </div>
        ))}
        {!drafts.data?.length && <p className="muted">Chưa có bản nháp.</p>}
      </div>
    </>
  );
}
