import { useQuery } from "@tanstack/react-query";
import { NavLink, Navigate, Route, Routes, useLocation } from "react-router-dom";
import { api, type Approval } from "./api";
import { useLiveUpdates } from "./live";
import Calendar from "./pages/Calendar";
import Chat from "./pages/Chat";
import Dashboard from "./pages/Dashboard";
import Finance from "./pages/Finance";
import Inbox from "./pages/Inbox";
import Login from "./pages/Login";
import Ops from "./pages/Ops";
import RunDetail from "./pages/RunDetail";
import Runs from "./pages/Runs";

const NAV = [
  ["/", "Tổng quan"],
  ["/chat", "Chat"],
  ["/finance", "Chi tiêu"],
  ["/calendar", "Lịch"],
  ["/inbox", "Email & Duyệt"],
  ["/runs", "Agent Runs"],
  ["/ops", "AgentOps"],
] as const;

export default function App() {
  const location = useLocation();
  const me = useQuery({ queryKey: ["me"], queryFn: () => api<{ user: string }>("/api/auth/me"), retry: false,
    enabled: location.pathname !== "/login" });
  if (location.pathname === "/login") return <Login />;
  if (me.isLoading) return null;
  if (me.isError) return <Navigate to="/login" replace />;
  return <Shell />;
}

function Shell() {
  useLiveUpdates(); // SSE: Telegram ghi dữ liệu → trang tự cập nhật
  const pending = useQuery({ queryKey: ["approvals", "pending"], queryFn: () => api<Approval[]>("/api/approvals") });
  return (
    <div className="layout">
      <aside className="sidebar">
        <div className="brand">🤖 Trợ lý cá nhân</div>
        <nav className="nav">
          {NAV.map(([to, label]) => (
            <NavLink key={to} to={to} end={to === "/"}>
              {label}
              {to === "/inbox" && pending.data?.length ? <span className="badge warn">{pending.data.length}</span> : null}
            </NavLink>
          ))}
        </nav>
      </aside>
      <main className="main">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/chat" element={<Chat />} />
          <Route path="/finance" element={<Finance />} />
          <Route path="/calendar" element={<Calendar />} />
          <Route path="/inbox" element={<Inbox />} />
          <Route path="/runs" element={<Runs />} />
          <Route path="/runs/:runId" element={<RunDetail />} />
          <Route path="/ops" element={<Ops />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
    </div>
  );
}
