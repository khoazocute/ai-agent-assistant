import type { DateSelectArg, DatesSetArg, EventClickArg, EventDropArg } from "@fullcalendar/core";
import interactionPlugin from "@fullcalendar/interaction";
import FullCalendar from "@fullcalendar/react";
import timeGridPlugin from "@fullcalendar/timegrid";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api, toDateStr, toLocalISO, type EventItem, type Plan, type Task } from "../api";
import { ErrorBox, StatusBadge } from "../components";

export default function Calendar() {
  const qc = useQueryClient();
  const [range, setRange] = useState<{ start: string; end: string } | null>(null);
  const events = useQuery({
    queryKey: ["events", range?.start, range?.end], enabled: !!range,
    queryFn: () => api<EventItem[]>(`/api/events?start=${range!.start}&end=${range!.end}`),
  });
  const tasks = useQuery({ queryKey: ["tasks"], queryFn: () => api<Task[]>("/api/tasks") });
  const [plan, setPlan] = useState<Plan | null>(null);
  const [taskForm, setTaskForm] = useState({ title: "", duration_min: "60", priority: "2" });

  const invalidate = () => qc.invalidateQueries();
  const createEvent = useMutation({
    mutationFn: (body: object) => api("/api/events", { method: "POST", json: body }), onSuccess: invalidate });
  const moveEvent = useMutation({
    mutationFn: ({ id, ...body }: { id: number; start_at: string; end_at: string }) =>
      api(`/api/events/${id}`, { method: "PATCH", json: body }), onSuccess: invalidate });
  const deleteEvent = useMutation({
    mutationFn: (id: number) => api(`/api/events/${id}`, { method: "DELETE" }), onSuccess: invalidate });
  const addTask = useMutation({
    mutationFn: () => api("/api/tasks", { method: "POST", json: {
      title: taskForm.title, duration_min: Number(taskForm.duration_min), priority: Number(taskForm.priority) } }),
    onSuccess: () => { setTaskForm({ ...taskForm, title: "" }); invalidate(); } });
  const suggest = useMutation({
    mutationFn: () => {
      const start = new Date();
      const end = new Date(start.getTime() + 6 * 86_400_000);
      return api<Plan>("/api/schedule/suggest", { method: "POST", json: { start: toDateStr(start), end: toDateStr(end) } });
    },
    onSuccess: setPlan });
  const gsync = useMutation({
    mutationFn: () => api<Record<string, number>>("/api/schedule/sync-google", { method: "POST" }),
    onSuccess: invalidate });
  const apply = useMutation({
    mutationFn: (id: number) => api(`/api/schedule/plans/${id}/apply`, { method: "POST" }),
    onSuccess: () => { setPlan(null); invalidate(); } });

  function onSelect(sel: DateSelectArg) {
    const title = prompt("Tên sự kiện?");
    if (title) createEvent.mutate({ title, start_at: toLocalISO(sel.start), end_at: toLocalISO(sel.end) });
    sel.view.calendar.unselect();
  }
  function onDrop(info: EventDropArg) {
    if (!info.event.start || !info.event.end) return info.revert();
    moveEvent.mutate({ id: Number(info.event.id), start_at: toLocalISO(info.event.start), end_at: toLocalISO(info.event.end) });
  }
  function onClick(info: EventClickArg) {
    if (confirm(`Xoá "${info.event.title}"?`)) deleteEvent.mutate(Number(info.event.id));
  }
  function onDates(arg: DatesSetArg) {
    setRange({ start: toDateStr(arg.start), end: toDateStr(new Date(arg.end.getTime() - 1)) });
  }

  const error = createEvent.error ?? moveEvent.error ?? deleteEvent.error ?? addTask.error ?? suggest.error ??
    apply.error ?? gsync.error;
  return (
    <>
      <div className="spread">
        <h1>Lịch</h1>
        <button disabled={gsync.isPending} onClick={() => gsync.mutate()}>
          {gsync.isPending ? "Đang đồng bộ…" : "↻ Đồng bộ Google Calendar"}
        </button>
      </div>
      <ErrorBox error={error} />
      <div className="card">
        <FullCalendar
          plugins={[timeGridPlugin, interactionPlugin]} initialView="timeGridWeek" locale="vi" firstDay={1}
          slotMinTime="06:00:00" slotMaxTime="23:00:00" allDaySlot={false} nowIndicator height="auto"
          selectable editable select={onSelect} eventDrop={onDrop} eventResize={(i) => onDrop(i as unknown as EventDropArg)}
          eventClick={onClick} datesSet={onDates}
          headerToolbar={{ left: "prev,next today", center: "title", right: "" }}
          events={events.data?.map((e) => ({ id: String(e.id), title: e.title, start: e.start_at, end: e.end_at })) ?? []}
        />
        <p className="small muted">Kéo chọn khung giờ để tạo sự kiện · kéo thả để dời · bấm vào sự kiện để xoá.</p>
      </div>

      <div className="grid section">
        <div className="card stack">
          <h2>Việc cần làm</h2>
          <form className="row" onSubmit={(e) => { e.preventDefault(); addTask.mutate(); }}>
            <input placeholder="Việc gì?" value={taskForm.title} onChange={(e) => setTaskForm({ ...taskForm, title: e.target.value })} />
            <input type="number" min={15} step={15} style={{ width: 90 }} value={taskForm.duration_min}
              onChange={(e) => setTaskForm({ ...taskForm, duration_min: e.target.value })} title="phút" />
            <select value={taskForm.priority} onChange={(e) => setTaskForm({ ...taskForm, priority: e.target.value })}>
              <option value="1">Ưu tiên cao</option><option value="2">Thường</option><option value="3">Thấp</option>
            </select>
            <button disabled={!taskForm.title}>Thêm</button>
          </form>
          <table><tbody>
            {tasks.data?.map((t) => (
              <tr key={t.id}><td>{t.title}</td><td className="small muted">{t.duration_min} phút</td><td><StatusBadge status={t.status} /></td></tr>
            ))}
          </tbody></table>
          <button className="primary" disabled={suggest.isPending} onClick={() => suggest.mutate()}>
            Đề xuất xếp lịch 7 ngày tới
          </button>
        </div>
        {plan && (
          <div className="card stack">
            <h2>Kế hoạch #{plan.plan_id} (đề xuất — chưa tạo sự kiện)</h2>
            {plan.items.map((i) => (
              <div key={i.task_id} className="spread small">
                <span>{i.title}</span>
                <span className="mono">{new Date(i.start).toLocaleString("vi-VN", { weekday: "short", hour: "2-digit", minute: "2-digit", day: "2-digit", month: "2-digit" })}–{i.end.slice(11, 16)}</span>
              </div>
            ))}
            {plan.unscheduled.map((u) => <div key={u.task_id} className="warn-box small">{u.title}: {u.reason}</div>)}
            <div className="row">
              <button className="primary" disabled={!plan.items.length || apply.isPending} onClick={() => apply.mutate(plan.plan_id)}>
                Áp dụng kế hoạch
              </button>
              <button onClick={() => setPlan(null)}>Bỏ qua</button>
            </div>
          </div>
        )}
      </div>
    </>
  );
}
