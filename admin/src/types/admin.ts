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

export type JobStatus = "queued" | "claimed" | "running" | "waiting_input" | "succeeded" | "failed" | "cancelled";
export type ConnectionStatus = "connected" | "waiting" | "stale" | "error";
export type IntegrationSyncStatus = "idle" | "queued" | "running" | "succeeded" | "failed";

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
  approvedAt: string | null;
  approvedBy: string | null;
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
  bucketId: string;
  storagePath: string;
  mimeType: string;
  bytes: number | null;
  durationSeconds: number | null;
  reviewStatus: string;
  retentionClass: string;
  expiresAt: string | null;
  cleanupStatus: string;
  deletedAt: string | null;
  metadata: Record<string, unknown>;
  signedUrl: string | null;
  createdAt: string;
};

export type WorkerSignal = {
  online: boolean;
  label: string;
  detail: string;
  version: string | null;
};

export type Ga4ProductDaily = {
  metricDate: string;
  itemId: string;
  productId: number | null;
  itemName: string;
  clicks: number;
};

export type Ga4TrafficDaily = {
  metricDate: string;
  source: string;
  medium: string;
  sessions: number;
  activeUsers: number;
};

export type IntegrationSync = {
  integration: "ga4" | "coupang" | "meta";
  status: IntegrationSyncStatus;
  lastAttemptAt: string | null;
  lastSuccessAt: string | null;
  rangeStart: string | null;
  rangeEnd: string | null;
  rowCount: number;
  errorSummary: string | null;
  updatedAt: string;
};

export type PerformanceSummary = {
  totalClicks: number;
  sessions: number;
  activeUsers: number;
  dailyTrend: Array<{ date: string; clicks: number; sessions: number; activeUsers: number }>;
  products: Array<{
    productId: number | null;
    itemId: string;
    itemName: string;
    clicks: number;
    share: number;
  }>;
  sources: Array<{ source: string; medium: string; sessions: number; activeUsers: number; share: number }>;
};

export type DeskData = {
  products: AdminProduct[];
  jobs: AdminJob[];
  workers: AdminWorker[];
  assets: AdminAsset[];
  ga4ProductDaily: Ga4ProductDaily[];
  ga4TrafficDaily: Ga4TrafficDaily[];
  integrationSyncs: IntegrationSync[];
  performance: PerformanceSummary;
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
