// Lớp gọi API: cùng origin (cookie httpOnly tự gửi kèm), lỗi → Error với thông điệp tiếng Việt từ backend.

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

export async function api<T>(path: string, init: RequestInit & { json?: unknown } = {}): Promise<T> {
  const { json, ...rest } = init;
  const res = await fetch(path, {
    credentials: "same-origin",
    ...rest,
    headers: { ...(json !== undefined ? { "Content-Type": "application/json" } : {}), ...rest.headers },
    body: json !== undefined ? JSON.stringify(json) : rest.body,
  });
  if (res.status === 401 && !path.startsWith("/api/auth/login")) {
    window.location.assign("/login");
    throw new ApiError(401, "Chưa đăng nhập");
  }
  const data = res.headers.get("content-type")?.includes("json") ? await res.json() : await res.text();
  if (!res.ok) {
    const detail = typeof data === "object" && data ? (data as { detail?: unknown }).detail : data;
    throw new ApiError(res.status, typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return data as T;
}

export const vnd = (n: number | null | undefined) =>
  n === null || n === undefined ? "—" : `${n.toLocaleString("vi-VN")}đ`;

export const fmtTime = (iso: string) =>
  new Date(iso).toLocaleString("vi-VN", { hour: "2-digit", minute: "2-digit", day: "2-digit", month: "2-digit" });

/** Date → "YYYY-MM-DDTHH:MM" theo giờ máy (backend lưu giờ VN không kèm múi giờ). */
export function toLocalISO(d: Date): string {
  const p = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}T${p(d.getHours())}:${p(d.getMinutes())}`;
}

export const toDateStr = (d: Date) => toLocalISO(d).slice(0, 10);

// ---------- Kiểu dữ liệu (khớp pydantic model ở backend) ----------

export interface CategoryTotal {
  category: string;
  category_name: string;
  kind: "expense" | "income";
  amount_vnd: number;
  count: number;
  percent_of_expense: number | null;
}

export interface Summary {
  start: string;
  end: string;
  total_expense_vnd: number;
  total_income_vnd: number;
  net_spending_vnd: number;
  transaction_count: number;
  by_category: CategoryTotal[];
}

export interface Transaction {
  id: number;
  amount_vnd: number;
  category: string;
  category_name: string;
  kind: "expense" | "income";
  occurred_on: string;
  note: string;
}

export interface Category {
  key: string;
  name: string;
  kind: "expense" | "income";
}

export interface EventItem {
  id: number;
  title: string;
  start_at: string;
  end_at: string;
  location: string;
  note: string;
  source: string;
}

export interface Task {
  id: number;
  title: string;
  duration_min: number;
  deadline: string | null;
  priority: number;
  status: "todo" | "scheduled" | "done";
  event_id: number | null;
}

export interface Plan {
  plan_id: number;
  status: string;
  items: { task_id: number; title: string; start: string; end: string }[];
  unscheduled: { task_id: number; title: string; reason: string }[];
}

export interface Approval {
  id: number;
  tool: string;
  agent: string;
  risk: string;
  summary: string;
  status: string;
  run_id: string;
  created_at: string;
  expires_at: string;
  decided_by: string;
  error: string;
}

export interface EmailView {
  id: number;
  from_addr: string;
  subject: string;
  snippet: string;
  received_at: string;
  category: string | null;
  summary: string;
  injection_flags: string[];
}

export interface Draft {
  id: number;
  to: string[];
  subject: string;
  body: string;
  status: string;
  pii_warnings: string[];
}

export interface ChatReply {
  answer: string;
  run_id: string;
  status: string;
  tools_used: string[];
  approvals: Approval[];
}

export interface Run {
  run_id: string;
  parent_run_id: string | null;
  agent: string;
  channel: string;
  model: string;
  prompt_version: string;
  input: string;
  output: string;
  status: string;
  error: string;
  steps: number;
  tool_calls: number;
  input_tokens: number;
  output_tokens: number;
  thinking_tokens: number;
  cost_vnd: number | null;
  latency_ms: number | null;
  started_at: string;
}

export interface RunEvent {
  seq: number;
  type: string;
  ts: string;
  data: Record<string, any>;
}

export interface AgentStats {
  agent: string;
  runs: number;
  ok: number;
  errors: number;
  success_rate: number;
  p50_ms: number | null;
  p95_ms: number | null;
  avg_input_tokens: number;
  avg_output_tokens: number;
  avg_steps: number;
  total_cost_vnd: number | null;
}
