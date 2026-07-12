import { CONNECTION_WAITING_LABEL } from "../lib/dashboard";
import { Icon } from "./Icon";

export function MetricCard({
  label,
  value,
  detail,
  tone = "default",
}: {
  label: string;
  value: string | null;
  detail: string;
  tone?: "default" | "success" | "warning" | "danger";
}) {
  const waiting = value === null;
  return (
    <article className={`metric-card metric-${tone}${waiting ? " metric-waiting" : ""}`}>
      <div className="metric-label"><span>{label}</span>{waiting ? <Icon name="link" size={15}/> : null}</div>
      <strong>{waiting ? CONNECTION_WAITING_LABEL : value}</strong>
      <p>{detail}</p>
    </article>
  );
}
