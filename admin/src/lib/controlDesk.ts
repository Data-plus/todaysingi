import type { Product } from "../data/demo";
import { supabase } from "./supabase";

export type DeskJob = {
  id: string;
  name: string;
  product: string;
  status: string;
  time: string;
};

export type WorkerSignal = {
  online: boolean;
  label: string;
  detail: string;
};

export type DeskData = {
  products: Product[];
  jobs: DeskJob[];
  worker: WorkerSignal;
  queueCount: number;
  reviewCount: number;
  publishedCount: number;
};

const stageLabels: Record<string, string> = {
  sourced: "상품 확정", video_ready: "영상 준비", script_ready: "대본 완성",
  audio_ready: "더빙 합성", caption_ready: "검수 대기", published: "릴스 게시",
  linked: "링크 연결", ads_running: "광고 집행", analyzed: "분석 완료",
};

const jobLabels: Record<string, string> = {
  sync_pipeline: "관제 장부 동기화", create_product: "로컬 관제 상품 생성", fetch_video: "영상 수집·가공",
  dub: "Typecast 음성 재생성", publish_reel: "Instagram 릴스 게시",
  add_product: "링크 허브 상품 추가",
};

const statusLabels: Record<string, string> = {
  queued: "대기 중", claimed: "선점됨", running: "처리 중", succeeded: "완료",
  failed: "실패", cancelled: "취소됨",
};

function relativeTime(value: string): string {
  const seconds = Math.max(0, Math.round((Date.now() - new Date(value).getTime()) / 1000));
  if (seconds < 60) return "방금 전";
  if (seconds < 3600) return `${Math.floor(seconds / 60)}분 전`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}시간 전`;
  return `${Math.floor(seconds / 86400)}일 전`;
}

function formatUpdated(value: string): string {
  const date = new Date(value);
  return new Intl.DateTimeFormat("ko-KR", {
    year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit",
    hour12: false,
  }).format(date).replace(/\. /g, ".");
}

export async function loadDeskData(): Promise<DeskData> {
  if (!supabase) throw new Error("Supabase가 설정되지 않았습니다");
  const [productsResult, jobsResult, workersResult] = await Promise.all([
    supabase.from("products").select("*").order("updated_at", { ascending: false }),
    supabase.from("jobs").select("id,type,status,product_id,created_at").order("created_at", { ascending: false }).limit(20),
    supabase.from("workers").select("id,status,last_seen_at").order("last_seen_at", { ascending: false }).limit(1),
  ]);
  const error = productsResult.error || jobsResult.error || workersResult.error;
  if (error) throw error;

  const products: Product[] = (productsResult.data || []).map((row) => ({
    id: row.id,
    title: row.title,
    stage: row.stage,
    stageLabel: stageLabels[row.stage] || row.stage,
    updatedAt: formatUpdated(row.updated_at),
    image: row.image_url || `/admin/images/${String(row.id).padStart(3, "0")}.jpg`,
    price: typeof row.price === "number" ? `${row.price.toLocaleString("ko-KR")}원` : "가격 미등록",
    caption: row.note || "다음 작업을 선택해 콘텐츠 제작을 이어가세요.",
  }));
  const titleById = new Map(products.map((product) => [product.id, product.title]));
  const jobs: DeskJob[] = (jobsResult.data || []).map((row) => ({
    id: `JOB-${String(row.id).slice(0, 6).toUpperCase()}`,
    name: jobLabels[row.type] || row.type,
    product: row.product_id ? titleById.get(row.product_id) || `OBJECT ${String(row.product_id).padStart(3, "0")}` : "CONTROL DESK",
    status: statusLabels[row.status] || row.status,
    time: relativeTime(row.created_at),
  }));
  const latestWorker = workersResult.data?.[0];
  const lastSeen = latestWorker ? new Date(latestWorker.last_seen_at).getTime() : 0;
  const online = Boolean(latestWorker && latestWorker.status !== "offline" && Date.now() - lastSeen < 45_000);

  return {
    products,
    jobs,
    worker: {
      online,
      label: online ? latestWorker.status === "busy" ? "BUSY" : "ONLINE" : "OFFLINE",
      detail: latestWorker ? `마지막 신호 ${relativeTime(latestWorker.last_seen_at)}` : "Worker 연결 기록 없음",
    },
    queueCount: (jobsResult.data || []).filter((job) => job.status === "queued").length,
    reviewCount: products.filter((product) => product.stage === "caption_ready").length,
    publishedCount: products.filter((product) => ["published", "linked", "ads_running", "analyzed"].includes(product.stage)).length,
  };
}

export async function enqueueDub(productId: number): Promise<void> {
  if (!supabase) throw new Error("Supabase가 설정되지 않았습니다");
  const { error } = await supabase.from("jobs").insert({
    product_id: productId,
    type: "dub",
    payload: { emotion: "toneup", intensity: 1, rate: "-5%" },
    idempotency_key: `dub:${productId}:${crypto.randomUUID()}`,
  });
  if (error) throw error;
}

export async function createProduct(input: { title: string; coupangUrl: string; aliUrl?: string }): Promise<void> {
  if (!supabase) throw new Error("Supabase가 설정되지 않았습니다");
  const { data: latest, error: readError } = await supabase
    .from("products").select("id").order("id", { ascending: false }).limit(1).maybeSingle();
  if (readError) throw readError;
  const productId = (latest?.id || 0) + 1;
  const { error } = await supabase.from("products").insert({
    id: productId,
    title: input.title.trim(),
    coupang_url: input.coupangUrl,
    ali_url: input.aliUrl || null,
    stage: "sourced",
  });
  if (error) throw error;
  const { error: jobError } = await supabase.from("jobs").insert({
    product_id: productId,
    type: "create_product",
    payload: {
      title: input.title.trim(), coupang_url: input.coupangUrl,
      ali_url: input.aliUrl || null, note: "온라인 관리자에서 등록",
    },
    idempotency_key: `create_product:${productId}`,
    priority: 10,
  });
  if (jobError) throw jobError;
}
