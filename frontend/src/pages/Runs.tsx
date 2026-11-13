import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api, fmtTime, vnd, type Run } from "../api";
import { StatusBadge } from "../components";

export default function Runs() {
  const runs = useQuery({ queryKey: ["runs"], queryFn: () => api<Run[]>("/api/runs?limit=100") });
  return (
    <>
      <h1>Agent Runs</h1>
      <p className="muted small">Mỗi tin nhắn là một run. Bấm vào để xem chính xác prompt, tool và từng bước suy luận.</p>
      <div className="card table-wrap">
        <table>
          <thead><tr>
            <th>Thời điểm</th><th>Kênh</th><th>Agent</th><th>Tin nhắn</th><th>Trạng thái</th>
            <th className="num">Bước</th><th className="num">Độ trễ</th><th className="num">Token vào</th><th className="num">Chi phí</th>
          </tr></thead>
          <tbody>
            {runs.data?.map((r) => (
              <tr key={r.run_id}>
                <td className="mono"><Link to={`/runs/${r.run_id}`}>{fmtTime(r.started_at)}</Link></td>
                <td>{r.channel}</td>
                <td>{r.agent}</td>
                <td>{r.input.split("\n").pop()?.slice(0, 70)}</td>
                <td><StatusBadge status={r.status} /></td>
                <td className="num">{r.steps}</td>
                <td className="num">{r.latency_ms !== null ? `${(r.latency_ms / 1000).toFixed(1)}s` : "—"}</td>
                <td className="num">{r.input_tokens.toLocaleString("vi-VN")}</td>
                <td className="num">{vnd(r.cost_vnd)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {!runs.data?.length && <p className="muted">Chưa có run nào.</p>}
      </div>
    </>
  );
}
