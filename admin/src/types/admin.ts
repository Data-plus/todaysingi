export type AdminView = "overview" | "products" | "jobs" | "performance" | "ads" | "settings";

export type ProductStage =
  | "sourced"
  | "video_ready"
  | "script_ready"
  | "audio_ready"
  | "caption_ready"
  | "published"
  | "linked"
  | "ads_running"
  | "analyzed";

export type JobStatus = "queued" | "claimed" | "running" | "succeeded" | "failed" | "cancelled";
export type ConnectionStatus = "connected" | "waiting" | "stale" | "error";

export type ExternalMetrics = {
  linkClicks: number | null;
  orders: number | null;
  revenue: number | null;
  commission: number | null;
  adSpend: number | null;
  roas: number | null;
};

export type AdminProduct = {
  id: number;
  title: string;
  stage: ProductStage;
  stageLabel: string;
  price: number | null;
  imageUrl: string | null;
  coupangUrl: string;
  aliUrl: string | null;
  partnersLink: string | null;
  reelUrl: string | null;
  instagramMediaId: string | null;
  siteProductId: string | null;
  note: string;
  active: boolean;
  createdAt: string;
  updatedAt: string;
  metrics: ExternalMetrics;
};

export type AdminJob = {
  id: string;
  displayId: string;
  type: string;
  typeLabel: string;
  status: JobStatus;
  statusLabel: string;
  productId: number | null;
  productTitle: string;
  payload: Record<string, unknown>;
  result: Record<string, unknown>;
  priority: number;
  progress: number;
  attempts: number;
  maxAttempts: number;
  claimedBy: string | null;
  errorSummary: string | null;
  createdAt: string;
  updatedAt: string;
};

export type AdminWorker = {
  id: string;
  name: string;
  status: string;
  online: boolean;
  statusLabel: string;
  currentJobId: string | null;
  version: string | null;
  lastSeenAt: string;
};

export type AdminAsset = {
  id: string;
  productId: number;
  jobId: string | null;
  kind: string;
  storagePath: string;
  mimeType: string;
  bytes: number | null;
  durationSeconds: number | null;
  reviewStatus: string;
  createdAt: string;
};

export type WorkerSignal = {
  online: boolean;
  label: string;
  detail: string;
  version: string | null;
};

export type DeskData = {
  products: AdminProduct[];
  jobs: AdminJob[];
  workers: AdminWorker[];
  assets: AdminAsset[];
  worker: WorkerSignal;
  loadedAt: string;
};

export type ConnectionInfo = {
  id: "supabase" | "worker" | "ga4" | "coupang" | "meta" | "typecast";
  name: string;
  status: ConnectionStatus;
  label: string;
  detail: string;
};
