type BadgeTone = "neutral" | "info" | "success" | "warning" | "danger";

const toneByStatus: Record<string, BadgeTone> = {
  queued: "warning",
  claimed: "info",
  running: "info",
  succeeded: "success",
  failed: "danger",
  cancelled: "neutral",
  connected: "success",
  waiting: "neutral",
  stale: "warning",
  error: "danger",
  online: "success",
  offline: "neutral",
};

export function StatusBadge({ status, label }: { status: string; label: string }) {
  const tone = toneByStatus[status] || "neutral";
  return <span className={`status-badge status-${tone}`}><i aria-hidden="true"/>{label}</span>;
}
