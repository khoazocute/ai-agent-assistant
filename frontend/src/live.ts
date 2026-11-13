import { useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";

/**
 * Cập nhật realtime qua Server-Sent Events (ADR-0016): backend phát sự kiện mỗi khi dữ liệu đổi
 * (kể cả do Telegram/agent ghi) → trang làm mới đúng phần dữ liệu liên quan. EventSource tự kết nối lại.
 */
const TOPIC_KEYS: Record<string, string[][]> = {
  finance: [["summary"], ["transactions"]],
  schedule: [["events"], ["tasks"]],
  email: [["emails"], ["drafts"]],
  approvals: [["approvals"]],
  runs: [["runs"], ["metrics"]],
};

export function useLiveUpdates() {
  const qc = useQueryClient();
  useEffect(() => {
    const source = new EventSource("/api/stream", { withCredentials: true });
    source.onmessage = (msg) => {
      try {
        const { topic } = JSON.parse(msg.data) as { topic: string };
        for (const key of TOPIC_KEYS[topic] ?? []) qc.invalidateQueries({ queryKey: key });
      } catch {
        /* bỏ qua sự kiện không hợp lệ */
      }
    };
    return () => source.close();
  }, [qc]);
}
