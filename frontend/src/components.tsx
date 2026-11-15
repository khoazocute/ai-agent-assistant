import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Component, useState, type ErrorInfo, type ReactNode } from "react";

/** Lỗi khi hiển thị → hiện thông báo + nút tải lại thay vì trang trắng (React gỡ cả cây khi có lỗi chưa bắt). */
type State = { error: Error | null; componentStack: string };

export class ErrorBoundary extends Component<{ children: ReactNode }, State> {
  state: State = { error: null, componentStack: "" };

  static getDerivedStateFromError(error: Error) {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    this.setState({ componentStack: info.componentStack ?? "" });
    console.error("Lỗi giao diện:", error, info.componentStack);
  }

  render() {
    if (!this.state.error) return this.props.children;
    return (
      <div className="card stack" style={{ margin: 24 }}>
        <h2>Giao diện gặp lỗi</h2>
        <div className="error-box mono">{this.state.error.message}</div>
        {/* "Component stack" nói đúng component nào đang hiển thị khi lỗi xảy ra — không bị minify
            che tên như stack trace JS thường (nhờ esbuild.keepNames trong vite.config.ts). */}
        {this.state.componentStack && (
          <div className="small">
            <strong>Xảy ra trong:</strong>
            <pre className="box small">{this.state.componentStack.trim()}</pre>
          </div>
        )}
        <pre className="box small">{this.state.error.stack?.split("\n").slice(0, 8).join("\n")}</pre>
        <div className="row">
          <button className="primary" onClick={() => this.setState({ error: null, componentStack: "" })}>
            Thử lại
          </button>
          <button onClick={() => window.location.reload()}>Tải lại trang</button>
        </div>
      </div>
    );
  }
}
import { api, fmtTime, type Approval } from "./api";

export function Stat({ label, value, tone }: { label: string; value: string; tone?: "income" }) {
  return (
    <div className="card stat">
      <div className="label">{label}</div>
      <div className={`value ${tone ?? ""}`}>{value}</div>
    </div>
  );
}

export function ErrorBox({ error }: { error: unknown }) {
  if (!error) return null;
  return <div className="error-box">{error instanceof Error ? error.message : String(error)}</div>;
}

const STATUS_TONE: Record<string, string> = {
  pending: "warn", executed: "ok", ok: "ok", rejected: "", expired: "", failed: "err", error: "err",
  max_steps: "warn", running: "info", disabled: "warn",
};

export function StatusBadge({ status }: { status: string }) {
  return <span className={`badge ${STATUS_TONE[status] ?? ""}`}>{status}</span>;
}

/** Thẻ yêu cầu duyệt: hiện ĐÚNG điều sẽ xảy ra (summary do backend dựng) + nút Duyệt / Từ chối. */
export function ApprovalCard({ approval }: { approval: Approval }) {
  const qc = useQueryClient();
  const [result, setResult] = useState<Approval | null>(null);
  const decide = useMutation({
    mutationFn: (action: "approve" | "reject") =>
      api<Approval>(`/api/approvals/${approval.id}/${action}`, { method: "POST" }),
    onSuccess: (a) => {
      setResult(a);
      qc.invalidateQueries();
    },
  });
  const current = result ?? approval;
  return (
    <div className="card">
      <div className="spread">
        <strong>🔐 #{current.id} · {current.tool}</strong>
        <StatusBadge status={current.status} />
      </div>
      <pre className="box small">{current.summary}</pre>
      <div className="spread small muted section">
        <span>agent {current.agent} · tạo {fmtTime(current.created_at)} · hết hạn {fmtTime(current.expires_at)}</span>
        {current.status === "pending" && (
          <div className="row">
            <button className="primary" disabled={decide.isPending} onClick={() => decide.mutate("approve")}>
              ✅ Duyệt
            </button>
            <button className="danger" disabled={decide.isPending} onClick={() => decide.mutate("reject")}>
              ❌ Từ chối
            </button>
          </div>
        )}
      </div>
      {current.error && <div className="error-box small section">{current.error}</div>}
      <ErrorBox error={decide.error} />
    </div>
  );
}
