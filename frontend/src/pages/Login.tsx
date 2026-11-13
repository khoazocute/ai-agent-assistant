import { useState } from "react";
import { api } from "../api";
import { ErrorBox } from "../components";

export default function Login() {
  const [password, setPassword] = useState("");
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api("/api/auth/login", { method: "POST", json: { password } });
      window.location.assign("/");
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="card login stack" onSubmit={submit}>
      <h1>🤖 Trợ lý cá nhân</h1>
      <input type="password" placeholder="Mật khẩu" value={password} autoFocus
        onChange={(e) => setPassword(e.target.value)} style={{ width: "100%" }} />
      <button className="primary" disabled={busy || !password} style={{ width: "100%" }}>Đăng nhập</button>
      <ErrorBox error={error} />
    </form>
  );
}
