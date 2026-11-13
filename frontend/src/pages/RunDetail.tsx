import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, fmtTime, vnd, type Run, type RunEvent } from "../api";
import { StatusBadge } from "../components";

/** Trang trả lời câu hỏi gốc của dự án: "agent đã đọc CHÍNH XÁC prompt nào, dùng tool nào, ở từng bước?" */
export default function RunDetail() {
  const { runId } = useParams();
  const detail = useQuery({ queryKey: ["runs", runId],
    queryFn: () => api<{ run: Run; events: RunEvent[]; children: Run[] }>(`/api/runs/${runId}`) });
  const [showPrompt, setShowPrompt] = useState(false);
  if (!detail.data) return <p className="muted">Đang tải…</p>;
  const { run, events, children } = detail.data;
  const start = events.find((e) => e.type === "run_start")?.data;

  return (
    <>
      <div className="spread">
        <h1>{run.agent} · <span className="mono">{run.run_id}</span></h1>
        <StatusBadge status={run.status} />
      </div>
      {run.parent_run_id && <p><Link to={`/runs/${run.parent_run_id}`}>↑ Run cha (supervisor)</Link></p>}
      <div className="grid">
        <div className="card small">
          <div>Model <span className="mono">{run.model}</span> · prompt <span className="mono">{run.prompt_version}</span></div>
          <div>Kênh {run.channel} · {fmtTime(run.started_at)}</div>
          <div>{run.steps} bước · {run.tool_calls} tool call · {run.latency_ms !== null ? `${(run.latency_ms / 1000).toFixed(1)}s` : "—"}</div>
          <div>Token vào {run.input_tokens} · ra {run.output_tokens} · suy nghĩ {run.thinking_tokens} · {vnd(run.cost_vnd)}</div>
        </div>
        {children.length > 0 && (
          <div className="card small">
            <strong>Run con (sub-agent)</strong>
            {children.map((c) => (
              <div key={c.run_id} className="spread">
                <Link to={`/runs/${c.run_id}`}>{c.agent}</Link>
                <span>{c.steps} bước · <StatusBadge status={c.status} /></span>
              </div>
            ))}
          </div>
        )}
      </div>

      {start && (
        <div className="card section">
          <div className="spread">
            <h2>Prompt & tool model nhìn thấy</h2>
            <button className="small" onClick={() => setShowPrompt(!showPrompt)}>{showPrompt ? "Ẩn" : "Xem"} system prompt</button>
          </div>
          {showPrompt && <pre className="box small">{start.system}</pre>}
          <div className="small section">
            <strong>Tool ({start.tools?.length ?? 0}):</strong>{" "}
            {start.tools?.map((t: { name: string; description: string }) => (
              <span key={t.name} className="badge" title={t.description} style={{ marginRight: 4 }}>{t.name}</span>
            ))}
          </div>
          <div className="small section"><strong>Tin nhắn (kèm thời điểm):</strong><pre className="box">{start.input}</pre></div>
        </div>
      )}

      <div className="card section timeline">
        <h2>Thought → Action → Observation</h2>
        {events.map((e) => <EventRow key={e.seq} event={e} />)}
      </div>
    </>
  );
}

function EventRow({ event }: { event: RunEvent }) {
  const d = event.data;
  if (event.type === "llm_response") {
    return (
      <div className="step">
        <div className="small muted">Bước {d.step} · {d.latency_ms} ms · in {d.usage.input_tokens} · out {d.usage.output_tokens}</div>
        {d.thoughts.map((t: string, i: number) => <div key={i}><span className="tag thought">THOUGHT</span> <span className="small">{t}</span></div>)}
        {d.tool_calls.map((c: { name: string; args: object }, i: number) => (
          <div key={i}><span className="tag action">ACTION</span> <span className="mono">{c.name}({JSON.stringify(c.args)})</span></div>
        ))}
        {d.text && <div><span className="tag answer">ANSWER</span> {d.text}</div>}
      </div>
    );
  }
  if (event.type === "tool_call") {
    return (
      <div className="step">
        <span className="tag observation">OBSERVATION</span> <span className="badge">{d.status}</span>{" "}
        <span className="mono small">{JSON.stringify(d.output).slice(0, 600)}</span>
      </div>
    );
  }
  if (event.type === "run_end" && d.error) return <div className="error-box">{d.error}</div>;
  return null;
}
