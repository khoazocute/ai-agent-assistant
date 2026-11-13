import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api, toDateStr, vnd, type Approval, type Category, type Summary, type Transaction } from "../api";
import { ApprovalCard, ErrorBox, Stat } from "../components";

const PERIODS = [
  ["today", "Hôm nay"], ["this_week", "Tuần này"], ["this_month", "Tháng này"],
  ["last_month", "Tháng trước"], ["this_year", "Năm nay"],
] as const;

export default function Finance() {
  const qc = useQueryClient();
  const [period, setPeriod] = useState<string>("this_month");
  const summary = useQuery({ queryKey: ["summary", period],
    queryFn: () => api<Summary>(`/api/finance/summary?period=${period}`) });
  const txs = useQuery({ queryKey: ["transactions", summary.data?.start, summary.data?.end],
    enabled: !!summary.data,
    queryFn: () => api<Transaction[]>(
      `/api/finance/transactions?limit=200&start=${summary.data!.start}&end=${summary.data!.end}`) });
  const categories = useQuery({ queryKey: ["categories"], queryFn: () => api<Category[]>("/api/finance/categories") });

  const [form, setForm] = useState({ amount: "", category: "an_uong", occurred_on: toDateStr(new Date()), note: "" });
  const add = useMutation({
    mutationFn: () => api("/api/finance/transactions", { method: "POST", json: {
      amount_vnd: Number(form.amount.replace(/\D/g, "")), category: form.category,
      occurred_on: form.occurred_on, note: form.note } }),
    onSuccess: () => { setForm({ ...form, amount: "", note: "" }); qc.invalidateQueries(); },
  });
  const remove = useMutation({
    mutationFn: (id: number) => api(`/api/finance/transactions/${id}`, { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries(),
  });

  const [receipt, setReceipt] = useState<{ approval: Approval | null; proposal: { warnings: string[] } } | null>(null);
  const upload = useMutation({
    mutationFn: (file: File) => {
      const body = new FormData();
      body.append("file", file);
      return api<{ approval: Approval | null; proposal: { warnings: string[] } }>(
        "/api/finance/receipts", { method: "POST", body });
    },
    onSuccess: setReceipt,
  });

  const chartData = summary.data?.by_category.filter((c) => c.kind === "expense")
    .map((c) => ({ name: c.category_name, amount: c.amount_vnd })) ?? [];

  return (
    <>
      <div className="spread">
        <h1>Chi tiêu</h1>
        <select value={period} onChange={(e) => setPeriod(e.target.value)}>
          {PERIODS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
        </select>
      </div>
      <div className="grid">
        <Stat label="Tổng chi" value={vnd(summary.data?.total_expense_vnd)} />
        <Stat label="Tổng thu" value={vnd(summary.data?.total_income_vnd)} tone="income" />
        <Stat label="Chi ròng (chi − thu)" value={vnd(summary.data?.net_spending_vnd)} />
      </div>

      <div className="grid section">
        <div className="card">
          <h2>Chi theo danh mục</h2>
          {chartData.length ? (
            <ResponsiveContainer width="100%" height={240}>
              <BarChart data={chartData} margin={{ left: 10 }}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="var(--border)" />
                <XAxis dataKey="name" tick={{ fontSize: 12, fill: "var(--muted)" }} />
                <YAxis tickFormatter={(v: number) => `${Math.round(v / 1000)}k`} tick={{ fontSize: 12, fill: "var(--muted)" }} />
                <Tooltip formatter={(v) => vnd(Number(v))} />
                <Bar dataKey="amount" name="Số tiền" fill="var(--accent)" radius={[6, 6, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : <p className="muted">Chưa có khoản chi trong khoảng này.</p>}
        </div>
        <form className="card stack" onSubmit={(e) => { e.preventDefault(); add.mutate(); }}>
          <h2>Thêm khoản thu/chi</h2>
          <div className="row">
            <input placeholder="Số tiền (VND)" inputMode="numeric" value={form.amount}
              onChange={(e) => setForm({ ...form, amount: e.target.value })} />
            <select value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })}>
              {categories.data?.map((c) => (
                <option key={c.key} value={c.key}>{c.name}{c.kind === "income" ? " (thu)" : ""}</option>
              ))}
            </select>
          </div>
          <div className="row">
            <input type="date" value={form.occurred_on} onChange={(e) => setForm({ ...form, occurred_on: e.target.value })} />
            <input placeholder="Ghi chú" value={form.note} onChange={(e) => setForm({ ...form, note: e.target.value })} />
          </div>
          <button className="primary" disabled={!form.amount || add.isPending}>Thêm</button>
          <ErrorBox error={add.error} />
          <label className="btn small" style={{ textAlign: "center" }}>
            {upload.isPending ? "Đang đọc hóa đơn…" : "📷 Đọc ảnh hóa đơn"}
            <input type="file" accept="image/*" hidden disabled={upload.isPending}
              onChange={(e) => e.target.files?.[0] && upload.mutate(e.target.files[0])} />
          </label>
          <ErrorBox error={upload.error} />
          {receipt && !receipt.approval && <div className="warn-box small">Không đọc được tổng tiền trên ảnh.</div>}
          {receipt?.approval && <ApprovalCard approval={receipt.approval} />}
        </form>
      </div>

      <div className="card section table-wrap">
        <h2>Giao dịch ({txs.data?.length ?? 0})</h2>
        <table>
          <thead><tr><th>Ngày</th><th>Danh mục</th><th>Ghi chú</th><th className="num">Số tiền</th><th /></tr></thead>
          <tbody>
            {txs.data?.map((t) => (
              <tr key={t.id}>
                <td className="mono">{t.occurred_on.split("-").reverse().join("/")}</td>
                <td>{t.category_name}</td>
                <td>{t.note}</td>
                <td className={`num ${t.kind === "income" ? "income" : ""}`}>{t.kind === "income" ? "+" : "−"}{vnd(t.amount_vnd)}</td>
                <td className="num">
                  <button className="danger small" disabled={remove.isPending}
                    onClick={() => confirm(`Xoá ${vnd(t.amount_vnd)} · ${t.category_name}?`) && remove.mutate(t.id)}>Xoá</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <ErrorBox error={remove.error} />
      </div>
    </>
  );
}
