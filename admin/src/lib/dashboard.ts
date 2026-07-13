import type {
  AdminJob,
  AdminProduct,
  ConnectionInfo,
  DeskData,
  ExternalMetrics,
  IntegrationSync,
  JobStatus,
  ProductStage,
} from "../types/admin";

export const CONNECTION_WAITING_LABEL = "연결 대기";

export const STAGE_LABELS: Record<ProductStage, string> = {
  sourced: "상품 확정",
  video_ready: "영상 준비",
  script_ready: "대본 완성",
  audio_ready: "더빙 합성",
  caption_ready: "검수 대기",
  published: "릴스 게시",
  linked: "링크 연결",
  ads_running: "광고 집행",
  analyzed: "분석 완료",
};

export const JOB_LABELS: Record<string, string> = {
  sync_pipeline: "관제 장부 동기화",
  sync_ga4: "GA4 성과 동기화",
  create_product: "로컬 관제 상품 생성",
  source_product: "쿠팡 상품 정보 수집",
  source_video: "원본 영상 수집",
  fetch_video: "영상 수집·가공",
  analyze_video: "영상 장면 분석",
  generate_script: "대본·콘텐츠 생성",
  generate_voice: "Typecast 음성 생성",
  dub: "Typecast 음성 재생성",
  compose_video: "영상·음성·자막 합성",
  generate_cover: "릴스 커버 생성",
  generate_caption: "Instagram 캡션 생성",
  publish_reel: "Instagram 릴스 게시",
  add_product: "링크 허브 상품 추가",
  export_products: "링크 허브 배포",
  cleanup_assets: "만료 산출물 정리",
};

export const JOB_STATUS_LABELS: Record<JobStatus, string> = {
  queued: "대기",
  claimed: "선점됨",
  running: "실행 중",
  waiting_input: "입력 필요",
  succeeded: "완료",
  failed: "실패",
  cancelled: "취소",
};

export const EMPTY_EXTERNAL_METRICS: ExternalMetrics = {
  linkClicks: null,
  orders: null,
  revenue: null,
  commission: null,
  adSpend: null,
  roas: null,
};

export function formatCurrency(value: number | null): string {
  return value === null ? "—" : `${value.toLocaleString("ko-KR")}원`;
}

export function formatNumber(value: number | null): string {
  return value === null ? "—" : value.toLocaleString("ko-KR");
}

export function formatPercent(value: number | null): string {
  return value === null ? "—" : `${value.toLocaleString("ko-KR", { maximumFractionDigits: 1 })}%`;
}

export function formatDateTime(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "기록 없음";
  return new Intl.DateTimeFormat("ko-KR", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(date);
}

export function relativeTime(value: string): string {
  const timestamp = new Date(value).getTime();
  if (Number.isNaN(timestamp)) return "기록 없음";
  const seconds = Math.max(0, Math.round((Date.now() - timestamp) / 1000));
  if (seconds < 60) return "방금 전";
  if (seconds < 3600) return `${Math.floor(seconds / 60)}분 전`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}시간 전`;
  return `${Math.floor(seconds / 86400)}일 전`;
}

export function conversionRate(metrics: ExternalMetrics): number | null {
  if (metrics.linkClicks === null || metrics.orders === null || metrics.linkClicks <= 0) return null;
  return (metrics.orders / metrics.linkClicks) * 100;
}

export function summarizeDesk(data: DeskData) {
  const summary = {
    activeProducts: 0,
    queuedJobs: 0,
    runningJobs: 0,
    failedJobs: 0,
    publishedProducts: 0,
  };
  for (const product of data.products) {
    if (product.active) summary.activeProducts += 1;
    if (["published", "linked", "ads_running", "analyzed"].includes(product.stage)) summary.publishedProducts += 1;
  }
  for (const job of data.jobs) {
    if (job.status === "queued") summary.queuedJobs += 1;
    if (job.status === "claimed" || job.status === "running") summary.runningJobs += 1;
    if (job.status === "failed") summary.failedJobs += 1;
  }
  return summary;
}

export function productNeedsAttention(product: AdminProduct, jobs: AdminJob[]): string | null {
  if (jobs.some((job) => job.productId === product.id && job.status === "failed")) return "실패한 작업 확인";
  if (jobs.some((job) => job.productId === product.id && job.status === "waiting_input")) return "Cloud 작업 입력 필요";
  if (!product.partnersLink && ["published", "linked", "ads_running", "analyzed"].includes(product.stage)) return "파트너스 링크 필요";
  if (product.stage === "caption_ready") return "콘텐츠 검수 필요";
  return null;
}

export function ga4ConnectionInfo(
  sync: IntegrationSync | undefined,
  live: boolean,
  now = Date.now(),
): ConnectionInfo {
  const base = { id: "ga4" as const, name: "Google Analytics 4" };
  if (!live || !sync || sync.status === "idle") {
    return {
      ...base,
      status: "waiting",
      label: CONNECTION_WAITING_LABEL,
      detail: live ? "첫 Data API 동기화를 실행하세요." : "Supabase 연결이 필요합니다.",
    };
  }
  if (sync.status === "queued" || sync.status === "running") {
    return { ...base, status: "waiting", label: "동기화 중", detail: "최근 삼십 일 데이터를 수집하고 있습니다." };
  }
  if (sync.status === "failed") {
    return { ...base, status: "error", label: "동기화 실패", detail: sync.errorSummary || "GA4 수집 로그를 확인하세요." };
  }
  const lastSuccess = sync.lastSuccessAt ? new Date(sync.lastSuccessAt).getTime() : Number.NaN;
  const stale = !Number.isFinite(lastSuccess) || now - lastSuccess > 48 * 60 * 60 * 1000;
  const range = sync.rangeStart && sync.rangeEnd ? `${sync.rangeStart}–${sync.rangeEnd}` : "최근 삼십 일";
  return {
    ...base,
    status: stale ? "stale" : "connected",
    label: stale ? "갱신 필요" : "수집 중",
    detail: `${range} · ${sync.rowCount.toLocaleString("ko-KR")}개 행`,
  };
}

export function buildConnections(data: DeskData, live: boolean): ConnectionInfo[] {
  const ga4Sync = data.integrationSyncs.find((sync) => sync.integration === "ga4");
  return [
    {
      id: "supabase",
      name: "Supabase",
      status: live ? "connected" : "waiting",
      label: live ? "연결됨" : CONNECTION_WAITING_LABEL,
      detail: live ? `최근 조회 ${relativeTime(data.loadedAt)}` : "관리자 환경 변수가 필요합니다.",
    },
    {
      id: "worker",
      name: "Cloud Run Worker",
      status: data.worker.online ? "connected" : "waiting",
      label: data.worker.online ? "실행 중" : "유휴",
      detail: data.worker.online ? data.worker.detail : "작업 요청 시 자동으로 실행됩니다.",
    },
    ga4ConnectionInfo(ga4Sync, live),
    {
      id: "coupang",
      name: "쿠팡 파트너스",
      status: "waiting",
      label: CONNECTION_WAITING_LABEL,
      detail: "최종 승인 후 Reporting API 키를 연결할 수 있습니다.",
    },
    {
      id: "meta",
      name: "Meta Marketing API",
      status: "waiting",
      label: CONNECTION_WAITING_LABEL,
      detail: "광고 계정과 지표 수집 저장소 연결이 필요합니다.",
    },
    {
      id: "typecast",
      name: "Typecast",
      status: data.worker.online ? "connected" : "waiting",
      label: data.worker.online ? "Cloud에서 사용 중" : "Secret 연결",
      detail: "비밀키는 Cloud Secret Manager에서만 사용합니다.",
    },
  ];
}
