import {
  EMPTY_EXTERNAL_METRICS,
  JOB_LABELS,
  JOB_STATUS_LABELS,
  STAGE_LABELS,
  relativeTime,
} from "./dashboard";
import { supabase } from "./supabase";
import type {
  AdminAsset,
  AdminJob,
  AdminProduct,
  AdminWorker,
  DeskData,
  JobStatus,
  ProductStage,
} from "../types/admin";

const SIDE_EFFECT_JOB_TYPES = new Set(["publish_reel", "ads_create", "ads_launch"]);

function requireSupabase() {
  if (!supabase) throw new Error("Supabase가 설정되지 않았습니다");
  return supabase;
}

export async function loadDeskData(): Promise<DeskData> {
  const client = requireSupabase();
  const [productsResult, jobsResult, workersResult, assetsResult] = await Promise.all([
    client.from("products").select("*").order("updated_at", { ascending: false }),
    client
      .from("jobs")
      .select("id,type,status,product_id,payload,result,priority,progress,attempts,max_attempts,claimed_by,error_summary,created_at,updated_at")
      .order("created_at", { ascending: false })
      .limit(100),
    client
      .from("workers")
      .select("id,name,status,current_job_id,version,last_seen_at")
      .order("last_seen_at", { ascending: false }),
    client
      .from("assets")
      .select("id,product_id,job_id,kind,storage_path,mime_type,bytes,duration_seconds,review_status,metadata,created_at")
      .order("created_at", { ascending: false })
      .limit(100),
  ]);
  const error = productsResult.error || jobsResult.error || workersResult.error || assetsResult.error;
  if (error) throw error;

  const products: AdminProduct[] = (productsResult.data || []).map((row) => {
    const stage = row.stage as ProductStage;
    return {
      id: Number(row.id),
      title: row.title,
      stage,
      stageLabel: STAGE_LABELS[stage] || row.stage,
      price: typeof row.price === "number" ? row.price : null,
      imageUrl: row.image_url || null,
      coupangUrl: row.coupang_url,
      aliUrl: row.ali_url || null,
      partnersLink: row.partners_link || null,
      reelUrl: row.reel_url || null,
      instagramMediaId: row.ig_media_id || null,
      siteProductId: row.site_product_id || null,
      note: row.note || "",
      active: typeof row.active === "boolean" ? row.active : true,
      createdAt: row.created_at,
      updatedAt: row.updated_at,
      metrics: { ...EMPTY_EXTERNAL_METRICS },
    };
  });
  const titleById = new Map(products.map((product) => [product.id, product.title]));
  const jobs: AdminJob[] = (jobsResult.data || []).map((row) => {
    const status = row.status as JobStatus;
    const productId = row.product_id === null ? null : Number(row.product_id);
    return {
      id: row.id,
      displayId: `JOB-${String(row.id).slice(0, 6).toUpperCase()}`,
      type: row.type,
      typeLabel: JOB_LABELS[row.type] || row.type,
      status,
      statusLabel: JOB_STATUS_LABELS[status] || row.status,
      productId,
      productTitle: productId ? titleById.get(productId) || `상품 ${productId}` : "전체 시스템",
      payload: row.payload || {},
      result: row.result || {},
      priority: Number(row.priority || 100),
      progress: Number(row.progress || 0),
      attempts: Number(row.attempts || 0),
      maxAttempts: Number(row.max_attempts || 3),
      claimedBy: row.claimed_by || null,
      errorSummary: row.error_summary || null,
      createdAt: row.created_at,
      updatedAt: row.updated_at,
    };
  });
  const workers: AdminWorker[] = (workersResult.data || []).map((row) => {
    const lastSeen = new Date(row.last_seen_at).getTime();
    const online = row.status !== "offline" && row.status !== "error" && Date.now() - lastSeen < 60_000;
    return {
      id: row.id,
      name: row.name,
      status: row.status,
      online,
      statusLabel: online ? (row.status === "busy" ? "작업 중" : "온라인") : "오프라인",
      currentJobId: row.current_job_id || null,
      version: row.version || null,
      lastSeenAt: row.last_seen_at,
    };
  });
  const assets: AdminAsset[] = (assetsResult.data || []).map((row) => ({
    id: row.id,
    productId: Number(row.product_id),
    jobId: row.job_id || null,
    kind: row.kind,
    storagePath: row.storage_path,
    mimeType: row.mime_type,
    bytes: typeof row.bytes === "number" ? row.bytes : null,
    durationSeconds: row.duration_seconds === null ? null : Number(row.duration_seconds),
    reviewStatus: row.review_status,
    metadata: row.metadata || {},
    signedUrl: null,
    createdAt: row.created_at,
  }));
  if (assets.length) {
    const { data: signedAssets } = await client.storage
      .from("completed-assets")
      .createSignedUrls(assets.map((asset) => asset.storagePath), 3600);
    const signedByPath = new Map(
      (signedAssets || []).filter((asset) => asset.signedUrl).map((asset) => [asset.path, asset.signedUrl]),
    );
    for (const asset of assets) asset.signedUrl = signedByPath.get(asset.storagePath) || null;
  }
  const latestWorker = workers[0];

  return {
    products,
    jobs,
    workers,
    assets,
    worker: {
      online: Boolean(latestWorker?.online),
      label: latestWorker?.statusLabel || "오프라인",
      detail: latestWorker ? `마지막 신호 ${relativeTime(latestWorker.lastSeenAt)}` : "Worker 연결 기록 없음",
      version: latestWorker?.version || null,
    },
    loadedAt: new Date().toISOString(),
  };
}

export async function enqueueDub(productId: number): Promise<void> {
  const client = requireSupabase();
  const { error } = await client.from("jobs").insert({
    product_id: productId,
    type: "dub",
    payload: { emotion: "toneup", intensity: 1, rate: "-5%" },
    idempotency_key: `dub:${productId}:${crypto.randomUUID()}`,
  });
  if (error) throw error;
}

export async function enqueuePipelineSync(): Promise<void> {
  const client = requireSupabase();
  const { error } = await client.from("jobs").insert({
    type: "sync_pipeline",
    payload: { requested_from: "admin" },
    idempotency_key: `sync_pipeline:${crypto.randomUUID()}`,
    priority: 20,
  });
  if (error) throw error;
}

export async function enqueueGenerateCover(
  productId: number,
  input: { frame?: number; line1?: string; line2?: string } = {},
): Promise<void> {
  const client = requireSupabase();
  const payload: Record<string, string | number> = {};
  if (input.frame !== undefined) payload.frame = input.frame;
  if (input.line1?.trim()) payload.line1 = input.line1.trim();
  if (input.line2?.trim()) payload.line2 = input.line2.trim();
  const { error } = await client.from("jobs").insert({
    product_id: productId,
    type: "generate_cover",
    payload,
    priority: 40,
    idempotency_key: `generate_cover:${productId}:${crypto.randomUUID()}`,
  });
  if (error) throw error;
}

export async function cancelJob(job: AdminJob): Promise<void> {
  const cancellable = job.status === "queued";
  if (!cancellable) throw new Error("대기 중인 작업만 취소할 수 있습니다");
  const client = requireSupabase();
  const { data, error } = await client
    .from("jobs")
    .update({ status: "cancelled", error_summary: "관리자 요청으로 취소" })
    .eq("id", job.id)
    .eq("status", "queued")
    .select("id")
    .maybeSingle();
  if (error) throw error;
  if (!data) throw new Error("작업 상태가 이미 변경되어 취소하지 못했습니다");
}

export async function retryJob(job: AdminJob): Promise<void> {
  const retryable = job.status === "failed" || job.status === "cancelled";
  if (!retryable) throw new Error("실패 또는 취소된 작업만 다시 요청할 수 있습니다");
  if (SIDE_EFFECT_JOB_TYPES.has(job.type) || job.type.startsWith("ads_")) {
    throw new Error("게시와 광고 작업은 검토 후 새로 승인해야 합니다");
  }
  const client = requireSupabase();
  const { error } = await client.from("jobs").insert({
    product_id: job.productId,
    type: job.type,
    payload: job.payload,
    priority: job.priority,
    max_attempts: job.maxAttempts,
    idempotency_key: `retry:${job.id}:${crypto.randomUUID()}`,
  });
  if (error) throw error;
}

export async function createProduct(input: { title: string; coupangUrl: string; aliUrl?: string }): Promise<void> {
  const client = requireSupabase();
  const { data: latest, error: readError } = await client
    .from("products")
    .select("id")
    .order("id", { ascending: false })
    .limit(1)
    .maybeSingle();
  if (readError) throw readError;
  const productId = Number(latest?.id || 0) + 1;
  const { error } = await client.from("products").insert({
    id: productId,
    title: input.title.trim(),
    coupang_url: input.coupangUrl,
    ali_url: input.aliUrl || null,
    stage: "sourced",
  });
  if (error) throw error;
  const { error: jobError } = await client.from("jobs").insert({
    product_id: productId,
    type: "create_product",
    payload: {
      title: input.title.trim(),
      coupang_url: input.coupangUrl,
      ali_url: input.aliUrl || null,
      note: "온라인 관리자에서 등록",
    },
    idempotency_key: `create_product:${productId}`,
    priority: 10,
  });
  if (jobError) throw jobError;
}
