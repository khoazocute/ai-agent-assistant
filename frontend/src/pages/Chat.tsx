import { useMutation } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { api, type ChatReply } from "../api";
import { ApprovalCard } from "../components";

type Message = { role: "user" | "bot"; text: string; reply?: ChatReply; rated?: number };

const EXAMPLES = ["trưa nay ăn phở 45k, đổ xăng 60k", "tháng này tôi chi bao nhiêu rồi?",
  "chiều mai 3h họp nhóm 1 tiếng", "có thư gì mới không?"];

export default function Chat() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [text, setText] = useState("");
  const bottom = useRef<HTMLDivElement>(null);
  useEffect(() => bottom.current?.scrollIntoView({ behavior: "smooth" }), [messages]);

  const send = useMutation({
    mutationFn: (message: string) => api<ChatReply>("/api/chat", { method: "POST", json: { message } }),
    onMutate: (message) => setMessages((m) => [...m, { role: "user", text: message }]),
    onSuccess: (reply) => setMessages((m) => [...m, { role: "bot", text: reply.answer, reply }]),
    onError: (err) => setMessages((m) => [...m, { role: "bot", text: `⚠ ${(err as Error).message}` }]),
  });

  async function rate(index: number, rating: number) {
    const runId = messages[index].reply?.run_id;
    if (!runId) return;
    await api("/api/chat/feedback", { method: "POST", json: { run_id: runId, rating } });
    setMessages((m) => m.map((msg, i) => (i === index ? { ...msg, rated: rating } : msg)));
  }

  function submit(e: React.FormEvent) {
    e.preventDefault();
    if (text.trim()) send.mutate(text.trim());
    setText("");
  }

  return (
    <>
      <div className="spread">
        <h1>Chat với trợ lý</h1>
        <button className="small" onClick={async () => { await api("/api/chat/reset", { method: "POST" }); setMessages([]); }}>
          Cuộc trò chuyện mới
        </button>
      </div>
      <div className="card chat">
        {!messages.length && (
          <div className="row">
            {EXAMPLES.map((ex) => <button key={ex} className="small" onClick={() => send.mutate(ex)}>{ex}</button>)}
          </div>
        )}
        {messages.map((m, i) => (
          <div key={i} className={`bubble ${m.role}`}>
            {m.text}
            {m.reply && (
              <div className="small muted section spread">
                <span>
                  {m.reply.tools_used.length ? `🔧 ${[...new Set(m.reply.tools_used)].join(" → ")} · ` : ""}
                  <Link to={`/runs/${m.reply.run_id}`}>xem prompt & trace</Link>
                </span>
                <span className="row">
                  <button className="small" disabled={m.rated !== undefined} onClick={() => rate(i, 1)}>👍</button>
                  <button className="small" disabled={m.rated !== undefined} onClick={() => rate(i, -1)}>👎</button>
                </span>
              </div>
            )}
            {m.reply?.approvals.map((a) => <div key={a.id} className="section"><ApprovalCard approval={a} /></div>)}
          </div>
        ))}
        {send.isPending && <div className="bubble bot muted">Đang suy nghĩ…</div>}
        <div ref={bottom} />
      </div>
      <form className="row section" onSubmit={submit}>
        <input style={{ flex: 1 }} placeholder="Nhắn cho trợ lý…" value={text} onChange={(e) => setText(e.target.value)} />
        <button className="primary" disabled={send.isPending || !text.trim()}>Gửi</button>
      </form>
    </>
  );
}
