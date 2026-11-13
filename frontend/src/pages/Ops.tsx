import { useQuery } from "@tanstack/react-query";
import { api, fmtTime, vnd, type AgentStats } from "../api";
import { Stat } from "../components";

interface Metrics { agents: AgentStats[]; feedback: { up: number; down: number }; pending_approvals: number }
interface Policy { defaults: Record<string, string>; tools: Record<string, string>; disabled_tools: string[]; disabled_agents: string[] }
interface AuditRow { id: number; ts: string; actor: string; action: string; target: string; detail: object }

const secs = (ms: number | null) => (ms === null ? "—" : `${(ms / 1000).toFixed(1)}s`);

export default function Ops() {
  const metrics = useQuery({ queryKey: ["metrics"], queryFn: () => api<Metrics>("/api/metrics") });
  const policy = useQuery({ queryKey: ["policy"], queryFn: () => api<Policy>("/api/policy") });
  const audit = useQuery({ queryKey: ["audit"], queryFn: () => api<AuditRow[]>("/api/audit?limit=50") });
  const m = metrics.data;
  const totalRuns = m?.agents.reduce((s, a) => s + a.runs, 0) ?? 0;

  return (
    <>
      <h1>AgentOps</h1>
      <div className="grid">
        <Stat label="Tổng số run" value={String(totalRuns)} />
        <Stat label="Chờ duyệt" value={String(m?.pending_approvals ?? 0)} />
        <Stat label="Phản hồi 👍 / 👎" value={`${m?.feedback.up ?? 0} / ${m?.feedback.down ?? 0}`} />
      </div>

      <div className="card section table-wrap">
        <h2>Theo agent</h2>
        <table>
          <thead><tr><th>Agent</th><th className="num">Run</th><th className="num">Thành công</th><th className="num">p50</th>
            <th className="num">p95</th><th className="num">Token vào TB</th><th className="num">Token ra TB</th>
            <th className="num">Bước TB</th><th className="num">Chi phí</th></tr></thead>
          <tbody>
            {m?.agents.map((a) => (
              <tr key={a.agent}>
                <td>{a.agent}</td><td className="num">{a.runs}</td>
                <td className="num">{Math.round(a.success_rate * 100)}%</td>
                <td className="num">{secs(a.p50_ms)}</td><td className="num">{secs(a.p95_ms)}</td>
                <td className="num">{a.avg_input_tokens.toLocaleString("vi-VN")}</td>
                <td className="num">{a.avg_output_tokens.toLocaleString("vi-VN")}</td>
                <td className="num">{a.avg_steps}</td><td className="num">{vnd(a.total_cost_vnd)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className="small muted">Chi phí "—" nghĩa là chưa điền giá trong backend/config/pricing.yaml.</p>
      </div>

      <div className="grid section">
        <div className="card small">
          <h2>Policy (config/policies.yaml)</h2>
          <div>Mặc định: {policy.data && Object.entries(policy.data.defaults).map(([k, v]) => `${k} → ${v}`).join(" · ")}</div>
          <div>Riêng từng tool: {policy.data && Object.entries(policy.data.tools).map(([k, v]) => `${k} → ${v}`).join(" · ")}</div>
          <div>Kill switch — agent tắt: {policy.data?.disabled_agents.join(", ") || "không"} · tool tắt: {policy.data?.disabled_tools.join(", ") || "không"}</div>
          <p className="muted">Sửa file YAML là có hiệu lực ngay ở lần gọi tool tiếp theo.</p>
        </div>
        <div className="card small table-wrap">
          <h2>Audit gần đây</h2>
          <table><tbody>
            {audit.data?.map((r) => (
              <tr key={r.id}><td className="mono">{fmtTime(r.ts)}</td><td>{r.actor}</td><td>{r.action}</td><td>{r.target}</td></tr>
            ))}
          </tbody></table>
        </div>
      </div>
    </>
  );
}
