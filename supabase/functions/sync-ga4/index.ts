import { createClient } from "npm:@supabase/supabase-js@2.52.1";
import {
  Ga4SyncError,
  buildProductReport,
  buildTrafficReport,
  createServiceAccountAssertion,
  exchangeAccessToken,
  parseProductRows,
  parseTrafficRows,
  propertyId,
  resolveDateRange,
  runReport,
  timingSafeEqual,
  type ServiceAccountCredentials,
} from "./ga4.ts";

const DEFAULT_ALLOWED_ORIGINS = [
  "https://todaysingi.netlify.app",
  "http://localhost:5173",
  "http://127.0.0.1:5173",
];

class HttpError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
    this.name = "HttpError";
  }
}

function requiredEnv(name: string): string {
  const value = Deno.env.get(name)?.trim();
  if (!value) throw new Ga4SyncError(`${name} 설정이 필요합니다`);
  return value;
}

function allowedOrigins(): Set<string> {
  const configured = Deno.env.get("GA4_ALLOWED_ORIGINS")
    ?.split(",")
    .map((value) => value.trim())
    .filter(Boolean);
  return new Set(configured?.length ? configured : DEFAULT_ALLOWED_ORIGINS);
}

function corsHeaders(request: Request): Record<string, string> {
  const origin = request.headers.get("origin")?.trim() ?? "";
  if (!origin) return { "Content-Type": "application/json" };
  if (!allowedOrigins().has(origin)) throw new HttpError(403, "허용되지 않은 요청 출처입니다");
  return {
    "Access-Control-Allow-Origin": origin,
    "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Access-Control-Max-Age": "86400",
    "Content-Type": "application/json",
    Vary: "Origin",
  };
}

function responseJson(
  request: Request,
  value: Record<string, unknown>,
  status = 200,
): Response {
  return new Response(JSON.stringify(value), {
    status,
    headers: corsHeaders(request),
  });
}

function bearerToken(request: Request): string {
  const authorization = request.headers.get("authorization") ?? "";
  const [scheme, token, ...rest] = authorization.trim().split(/\s+/);
  if (scheme?.toLowerCase() !== "bearer" || !token || rest.length) {
    throw new HttpError(401, "관리자 로그인이 필요합니다");
  }
  return token;
}

async function authorize(
  request: Request,
  serviceClient: ReturnType<typeof createClient>,
): Promise<"admin" | "cron"> {
  const providedCronSecret = request.headers.get("x-ga4-cron-secret") ?? "";
  const expectedCronSecret = Deno.env.get("GA4_CRON_SECRET") ?? "";
  if (providedCronSecret && expectedCronSecret
      && timingSafeEqual(providedCronSecret, expectedCronSecret)) {
    return "cron";
  }

  const token = bearerToken(request);
  const { data, error } = await serviceClient.auth.getUser(token);
  if (error || !data.user) throw new HttpError(401, "관리자 로그인이 만료되었습니다");
  const adminEmail = Deno.env.get("ADMIN_EMAIL")?.trim().toLowerCase();
  if (!adminEmail) throw new Ga4SyncError("ADMIN_EMAIL 설정이 필요합니다");
  if ((data.user.email ?? "").toLowerCase() !== adminEmail) {
    throw new HttpError(403, "GA4 동기화 권한이 없습니다");
  }
  return "admin";
}

async function requestInput(request: Request): Promise<{ days?: number }> {
  if (!request.headers.get("content-type")?.toLowerCase().includes("application/json")) {
    return {};
  }
  try {
    const value = await request.json();
    if (!value || typeof value !== "object" || Array.isArray(value)) {
      throw new Error("invalid body");
    }
    const days = (value as Record<string, unknown>).days;
    if (days === undefined) return {};
    if (!Number.isInteger(days) || Number(days) < 1 || Number(days) > 90) {
      throw new HttpError(400, "GA4 조회 기간은 일 일부터 구십 일까지 가능합니다");
    }
    return { days: Number(days) };
  } catch (error) {
    if (error instanceof HttpError) throw error;
    throw new HttpError(400, "요청 JSON 형식이 올바르지 않습니다");
  }
}

function credentialsFromEnv(): ServiceAccountCredentials {
  const raw = Deno.env.get("GA4_SERVICE_ACCOUNT_JSON")?.trim();
  if (!raw) throw new Ga4SyncError("GA4 서비스 계정 설정이 필요합니다");
  try {
    const value = JSON.parse(raw);
    if (!value || typeof value !== "object" || Array.isArray(value)) {
      throw new Error("invalid credentials");
    }
    return value as ServiceAccountCredentials;
  } catch {
    throw new Ga4SyncError("GA4 서비스 계정 JSON 형식이 올바르지 않습니다");
  }
}

function safeError(error: unknown): string {
  if (error instanceof Ga4SyncError || error instanceof HttpError) return error.message.slice(0, 1000);
  if (error && typeof error === "object" && "code" in error) {
    return `Supabase 저장 오류 (${String((error as Record<string, unknown>).code).slice(0, 32)})`;
  }
  return "GA4 동기화 중 알 수 없는 오류가 발생했습니다";
}

Deno.serve(async (request: Request) => {
  let serviceClient: ReturnType<typeof createClient> | null = null;
  let authorized = false;
  try {
    const headers = corsHeaders(request);
    if (request.method === "OPTIONS") return new Response(null, { status: 204, headers });
    if (request.method !== "POST") throw new HttpError(405, "POST 요청만 허용됩니다");

    const supabaseUrl = requiredEnv("SUPABASE_URL");
    const serviceRoleKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")?.trim();
    if (!serviceRoleKey) throw new Ga4SyncError("Supabase service role 설정이 필요합니다");
    serviceClient = createClient(supabaseUrl, serviceRoleKey, {
      auth: { persistSession: false, autoRefreshToken: false },
    });
    const actor = await authorize(request, serviceClient);
    authorized = true;
    const input = await requestInput(request);
    const range = resolveDateRange(input);
    const ga4PropertyId = propertyId(Deno.env.get("GA4_PROPERTY_ID") ?? "");

    const { error: runningError } = await serviceClient
      .from("integration_syncs")
      .update({
        status: "running",
        last_attempt_at: new Date().toISOString(),
        range_start: range.start,
        range_end: range.end,
        error_summary: null,
      })
      .eq("integration", "ga4");
    if (runningError) throw runningError;

    const assertion = await createServiceAccountAssertion(credentialsFromEnv());
    const accessToken = await exchangeAccessToken(assertion);
    const [productResponse, trafficResponse, productsResult] = await Promise.all([
      runReport(
        ga4PropertyId,
        buildProductReport(ga4PropertyId, range.start, range.end),
        accessToken,
      ),
      runReport(
        ga4PropertyId,
        buildTrafficReport(ga4PropertyId, range.start, range.end),
        accessToken,
      ),
      serviceClient.from("products").select("id"),
    ]);
    if (productsResult.error) throw productsResult.error;
    const knownProductIds = new Set(
      (productsResult.data ?? []).map((row) => Number(row.id)).filter(Number.isSafeInteger),
    );
    const productRows = parseProductRows(productResponse, knownProductIds);
    const trafficRows = parseTrafficRows(trafficResponse);
    const { data: storedRows, error: replaceError } = await serviceClient.rpc("replace_ga4_metrics", {
      p_range_start: range.start,
      p_range_end: range.end,
      p_product_rows: productRows,
      p_traffic_rows: trafficRows,
    });
    if (replaceError) throw replaceError;

    return responseJson(request, {
      ok: true,
      actor,
      rangeStart: range.start,
      rangeEnd: range.end,
      productRows: productRows.length,
      trafficRows: trafficRows.length,
      storedRows: Number(storedRows ?? 0),
    });
  } catch (error) {
    const message = safeError(error);
    if (authorized && serviceClient) {
      await serviceClient
        .from("integration_syncs")
        .update({ status: "failed", error_summary: message })
        .eq("integration", "ga4");
    }
    const status = error instanceof HttpError ? error.status : 500;
    try {
      return responseJson(request, { ok: false, error: message }, status);
    } catch {
      return new Response(JSON.stringify({ ok: false, error: message }), {
        status,
        headers: { "Content-Type": "application/json" },
      });
    }
  }
});
