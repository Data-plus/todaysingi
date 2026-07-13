import {
  EMPTY_EXTERNAL_METRICS,
  JOB_LABELS,
  JOB_STATUS_LABELS,
  STAGE_LABELS,
  relativeTime,
} from "./dashboard";
import { summarizeGa4 } from "./performance";
import { supabase } from "./supabase";
import type {
  AdminAsset,
  AdminJob,
  AdminProduct,
  AdminWorker,
  DeskData,
  Ga4ProductDaily,
  Ga4TrafficDaily,
  IntegrationSync,
  JobStatus,
  ProductStage,
} from "../types/admin";

const SIDE_EFFECT_JOB_TYPES = new Set(["publish_reel", "ads_create", "ads_launch"]);

function requireSupabase() {
  if (!supabase) throw new Error("Supabase가 설정되지 않았습니다");
  return supabase;
}

async function dispatchCloudWorker(reason: string): Promise<boolean> {
  const client = requireSupabase();
  const { error } = await client.functions.invoke("dispatch-worker", { body: { reason } });
  if (error) {
    console.warn("Cloud Worker dispatch failed; queued work remains safe.", error.message);
    return false;
  }
  return true;
}

export async function loadDeskData(): Promise<DeskData> {
  const client = requireSupabase();
  const [
    productsResult,
    jobsResult,
    workersResult,
    assetsResult,
    ga4ProductsResult,
    ga4TrafficResult,
    integrationsResult,
  ] = await Promise.all([
    client.from("products").select("*").order("updated_at", { ascending: false }),
    client
      .from("jobs")
      .select("id,type,status,product_id,payload,result,priority,progress,attempts,max_attempts,claimed_by,error_summary,approved_at,approved_by,created_at,updated_at")
      .order("created_at", { ascending: false })
      .limit(100),
    client
      .from("workers")
      .select("id,name,status,current_job_id,version,last_seen_at")
      .order("last_seen_at", { ascending: false }),
    client
      .from("assets")
      .select("id,product_id,job_id,kind,bucket_id,storage_path,mime_type,bytes,duration_seconds,review_status,retention_class,expires_at,cleanup_status,deleted_at,metadata,created_at")
      .is("deleted_at", null)
      .order("created_at", { ascending: false })
      .limit(100),
    client
      .from("ga4_product_daily")
      .select("metric_date,item_id,product_id,item_name,clicks,synced_at")
      .order("metric_date", { ascending: true })
      .limit(5000),
    client
      .from("ga4_traffic_daily")
      .select("metric_date,source,medium,sessions,active_users,synced_at")
      .order("metric_date", { ascending: true })
      .limit(5000),
    client
      .from("integration_syncs")
      .select("integration,status,last_attempt_at,last_success_at,range_start,range_end,row_count,error_summary,updated_at")
      .order("integration", { ascending: true }),
  ]);
  const error = productsResult.error || jobsResult.error || workersResult.error || assetsResult.error
    || ga4ProductsResult.error || ga4TrafficResult.error || integrationsResult.error;
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
      approvedAt: row.approved_at || null,
      approvedBy: row.approved_by || null,
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
    bucketId: row.bucket_id || "completed-assets",
    storagePath: row.storage_path,
    mimeType: row.mime_type,
    bytes: typeof row.bytes === "number" ? row.bytes : null,
    durationSeconds: row.duration_seconds === null ? null : Number(row.duration_seconds),
    reviewStatus: row.review_status,
    retentionClass: row.retention_class || "review",
    expiresAt: row.expires_at || null,
    cleanupStatus: row.cleanup_status || "active",
    deletedAt: row.deleted_at || null,
    metadata: row.metadata || {},
    signedUrl: null,
    createdAt: row.created_at,
  }));
  const ga4ProductDaily: Ga4ProductDaily[] = (ga4ProductsResult.data || []).map((row) => ({
    metricDate: row.metric_date,
    itemId: row.item_id,
    productId: row.product_id === null ? null : Number(row.product_id),
    itemName: row.item_name || "",
    clicks: Number(row.clicks || 0),
  }));
  const ga4TrafficDaily: Ga4TrafficDaily[] = (ga4TrafficResult.data || []).map((row) => ({
    metricDate: row.metric_date,
    source: row.source,
    medium: row.medium,
    sessions: Number(row.sessions || 0),
    activeUsers: Number(row.active_users || 0),
  }));
  const integrationSyncs: IntegrationSync[] = (integrationsResult.data || []).map((row) => ({
    integration: row.integration,
    status: row.status,
    lastAttemptAt: row.last_attempt_at || null,
    lastSuccessAt: row.last_success_at || null,
    rangeStart: row.range_start || null,
    rangeEnd: row.range_end || null,
    rowCount: Number(row.row_count || 0),
    errorSummary: row.error_summary || null,
    updatedAt: row.updated_at,
  }));
  const performance = summarizeGa4(ga4ProductDaily, ga4TrafficDaily);
  const clicksByProduct = new Map<number, number>();
  for (const row of performance.products) {
    if (row.productId !== null) clicksByProduct.set(row.productId, row.clicks);
  }
  for (const product of products) {
    product.metrics.linkClicks = clicksByProduct.get(product.id) ?? 0;
  }
  if (assets.length) {
    const assetsByBucket = new Map<string, AdminAsset[]>();
    for (const asset of assets) {
      const grouped = assetsByBucket.get(asset.bucketId) || [];
      grouped.push(asset);
      assetsByBucket.set(asset.bucketId, grouped);
    }
    await Promise.all(Array.from(assetsByBucket, async ([bucketId, bucketAssets]) => {
      const { data: signedAssets } = await client.storage
        .from(bucketId)
        .createSignedUrls(bucketAssets.map((asset) => asset.storagePath), 3600);
      const signedByPath = new Map(
        (signedAssets || []).filter((asset) => asset.signedUrl).map((asset) => [asset.path, asset.signedUrl]),
      );
      for (const asset of bucketAssets) asset.signedUrl = signedByPath.get(asset.storagePath) || null;
    }));
  }
  const latestWorker = workers[0];

  return {
    products,
    jobs,
    workers,
    assets,
    ga4ProductDaily,
    ga4TrafficDaily,
    integrationSyncs,
    performance,
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
    type: "generate_voice",
    payload: { emotion: "toneup", intensity: 1, rate: "-5%", orchestrated: false },
    idempotency_key: `generate_voice:${productId}:${crypto.randomUUID()}`,
  });
  if (error) throw error;
  await dispatchCloudWorker(`dub:${productId}`);
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
  await dispatchCloudWorker("sync_pipeline");
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
  await dispatchCloudWorker(`cover:${productId}`);
}

export async function requestGa4Sync(days = 30): Promise<string> {
  const client = requireSupabase();
  const { data, error } = await client.rpc("request_ga4_sync", { p_days: days });
  if (error) throw error;
  if (typeof data !== "string" || !data) {
    throw new Error("GA4 동기화 작업 ID를 받지 못했습니다.");
  }
  await dispatchCloudWorker("sync_ga4");
  return data;
}

export async function resumePipelineJob(
  jobId: string,
  input: Record<string, string | number>,
): Promise<void> {
  const client = requireSupabase();
  const { error } = await client.rpc("resume_pipeline_job", {
    p_job_id: jobId,
    p_input: input,
  });
  if (error) throw error;
  await dispatchCloudWorker(`resume:${jobId}`);
}

export async function uploadManualVideo(
  productId: number,
  jobId: string,
  file: File,
): Promise<void> {
  if (file.type !== "video/mp4" || file.size < 1 || file.size > 500 * 1024 * 1024) {
    throw new Error("오백 MB 이하 MP4 파일만 업로드할 수 있습니다.");
  }
  const client = requireSupabase();
  const storagePath = `manual-inputs/${productId}/${crypto.randomUUID()}.mp4`;
  const { error: uploadError } = await client.storage
    .from("pipeline-assets")
    .upload(storagePath, file, { contentType: "video/mp4", upsert: false });
  if (uploadError) throw uploadError;
  const { error: registerError } = await client.rpc("register_manual_video", {
    p_product_id: productId,
    p_job_id: jobId,
    p_storage_path: storagePath,
    p_bytes: file.size,
    p_mime_type: "video/mp4",
  });
  if (registerError) {
    await client.storage.from("pipeline-assets").remove([storagePath]);
    throw registerError;
  }
  await dispatchCloudWorker(`manual_video:${productId}`);
}

export async function approvePublishReel(productId: number): Promise<string> {
  const client = requireSupabase();
  const { data, error } = await client.rpc("approve_publish_reel", {
    p_product_id: productId,
  });
  if (error) {
    if (error.code === "22023") {
      throw new Error("캡션이 완성되고 아직 게시되지 않은 상품만 승인할 수 있습니다.");
    }
    if (error.code === "42501") {
      throw new Error("Instagram 게시 승인 권한이 없습니다.");
    }
    throw error;
  }
  if (typeof data !== "string" || !data) {
    throw new Error("게시 승인 작업 ID를 받지 못했습니다.");
  }
  await dispatchCloudWorker(`publish:${productId}`);
  return data;
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
  await dispatchCloudWorker(`retry:${job.id}`);
}

export async function createProduct(input: { title?: string; coupangUrl: string; aliUrl?: string }): Promise<void> {
  const client = requireSupabase();
  const { data: latest, error: readError } = await client
    .from("products")
    .select("id")
    .order("id", { ascending: false })
    .limit(1)
    .maybeSingle();
  if (readError) throw readError;
  const productId = Number(latest?.id || 0) + 1;
  const title = input.title?.trim() || "상품 정보 수집 대기";
  const { error } = await client.from("products").insert({
    id: productId,
    title,
    coupang_url: input.coupangUrl,
    ali_url: input.aliUrl || null,
    stage: "sourced",
  });
  if (error) throw error;
  const { error: jobError } = await client.from("jobs").insert({
    product_id: productId,
    type: "source_product",
    payload: {
      coupang_url: input.coupangUrl,
      ali_url: input.aliUrl || null,
      orchestrated: true,
    },
    idempotency_key: `pipeline:${productId}:source_product:v1`,
    priority: 10,
  });
  if (jobError) throw jobError;
  await dispatchCloudWorker(`source_product:${productId}`);
}
