import { useMemo, useState } from "react";
import { Icon } from "../components/Icon";
import { StatusBadge } from "../components/StatusBadge";
import { formatDateTime } from "../lib/dashboard";
import type { AdminJob, JobStatus } from "../types/admin";

const FILTERS: Array<{ value: "all" | JobStatus; label: string }> = [
  { value: "all", label: "전체" },
  { value: "queued", label: "대기" },
  { value: "running", label: "실행 중" },
  { value: "failed", label: "실패" },
  { value: "succeeded", label: "완료" },
  { value: "cancelled", label: "취소" },
];

function retryBlocked(job: AdminJob) {
  return job.type === "publish_reel" || job.type.startsWith("ads_");
}

export function JobsPage({ jobs, busyJobId, syncing, live, onCancel, onRetry, onSync }: { jobs: AdminJob[]; busyJobId: string | null; syncing: boolean; live: boolean; onCancel: (job: AdminJob) => void; onRetry: (job: AdminJob) => void; onSync: () => void }) {
  const [filter, setFilter] = useState<"all" | JobStatus>("all");
  const visibleJobs = useMemo(() => jobs.filter((job) => filter === "all" || (filter === "running" ? job.status === "running" || job.status === "claimed" : job.status === filter)), [filter, jobs]);

  return (
    <div className="page-stack">
      <section className="queue-toolbar">
        <div className="segmented-control" aria-label="작업 상태 필터">{FILTERS.map((item) => <button type="button" className={filter === item.value ? "active" : ""} aria-pressed={filter === item.value} key={item.value} onClick={() => setFilter(item.value)}>{item.label}<span>{item.value === "all" ? jobs.length : jobs.filter((job) => item.value === "running" ? ["running", "claimed"].includes(job.status) : job.status === item.value).length}</span></button>)}</div>
        <button type="button" className="secondary-button" onClick={onSync} disabled={syncing || !live} title={live ? "로컬 파이프라인 동기화 요청" : "Supabase 연결 후 사용할 수 있습니다"}><Icon name="refresh" size={17}/>{syncing ? "요청 중…" : "파이프라인 동기화"}</button>
      </section>

      <section className="jobs-list" aria-label="작업 목록">
        {visibleJobs.length ? visibleJobs.map((job) => {
          const busy = busyJobId === job.id;
          const canCancel = job.status === "queued";
          const canRetry = (job.status === "failed" || job.status === "cancelled") && !retryBlocked(job);
          return (
            <article className={`job-card job-${job.status}`} key={job.id}>
              <div className="job-card-main">
                <div className="job-card-icon"><Icon name={job.status === "failed" ? "alert" : job.status === "succeeded" ? "check" : "activity"} size={20}/></div>
                <div className="job-card-copy"><span>{job.displayId}</span><h2>{job.typeLabel}</h2><p>{job.productTitle}</p></div>
                <StatusBadge status={job.status} label={job.statusLabel}/>
                <div className="job-progress"><span><b>{job.progress}%</b><small>{job.attempts}/{job.maxAttempts}회 시도</small></span><div><i style={{ width: `${job.progress}%` }}/></div></div>
                <div className="job-meta"><span>수정 {formatDateTime(job.updatedAt)}</span><span>Worker {job.claimedBy || "미배정"}</span></div>
                <div className="job-actions">
                  <button type="button" className="ghost-button danger-action" onClick={() => onCancel(job)} disabled={!live || !canCancel || busy} title={!live ? "Supabase 연결 후 사용할 수 있습니다" : canCancel ? "대기 작업 취소" : "대기 중인 작업만 취소할 수 있습니다"}><Icon name="cancel" size={16}/>취소</button>
                  <button type="button" className="ghost-button" onClick={() => onRetry(job)} disabled={!live || !canRetry || busy} title={!live ? "Supabase 연결 후 사용할 수 있습니다" : retryBlocked(job) ? "게시·광고는 새 승인이 필요합니다" : canRetry ? "새 작업으로 다시 요청" : "실패·취소 작업만 재시도할 수 있습니다"}><Icon name="rotate" size={16}/>{busy ? "처리 중…" : "재시도"}</button>
                </div>
              </div>
              {job.errorSummary ? <p className="job-error"><Icon name="alert" size={15}/>{job.errorSummary}</p> : null}
              <details className="job-details"><summary>요청·결과 상세 보기</summary><div><section><h3>요청 payload</h3><pre>{JSON.stringify(job.payload, null, 2)}</pre></section><section><h3>실행 result</h3><pre>{JSON.stringify(job.result, null, 2)}</pre></section></div></details>
            </article>
          );
        }) : <div className="empty-state large-empty"><Icon name="check" size={26}/><strong>이 상태의 작업이 없습니다.</strong><p>필터를 바꾸거나 새 작업을 요청하세요.</p></div>}
      </section>
    </div>
  );
}
