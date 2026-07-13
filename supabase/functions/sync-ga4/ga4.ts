export const ANALYTICS_SCOPE = "https://www.googleapis.com/auth/analytics.readonly";
export const DATA_API_ROOT = "https://analyticsdata.googleapis.com/v1beta";
export const LINK_HUB_LIST_ID = "todaysingi_link_hub";

export class Ga4SyncError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "Ga4SyncError";
  }
}

type DateRangeInput = {
  days?: number;
  rangeStart?: string;
  rangeEnd?: string;
};

type Ga4Value = { value?: unknown };
type Ga4Row = {
  dimensionValues?: Ga4Value[];
  metricValues?: Ga4Value[];
};
type Ga4Response = { rows?: Ga4Row[] };

export type ProductMetricRow = {
  metric_date: string;
  item_id: string;
  product_id: number | null;
  item_name: string;
  clicks: number;
};

export type TrafficMetricRow = {
  metric_date: string;
  source: string;
  medium: string;
  sessions: number;
  active_users: number;
};

export type ServiceAccountCredentials = {
  client_email: string;
  private_key: string;
};

type FetchLike = (
  input: string | URL | Request,
  init?: RequestInit,
) => Promise<Response>;

export function propertyId(value: unknown): string {
  const clean = String(value ?? "").trim();
  if (!/^\d+$/.test(clean)) {
    throw new Ga4SyncError("GA4 Property ID는 숫자여야 합니다");
  }
  return clean;
}

function isoDate(value: unknown): string {
  const clean = String(value ?? "").trim();
  if (!/^\d{4}-\d{2}-\d{2}$/.test(clean)) {
    throw new Ga4SyncError("GA4 날짜 형식이 올바르지 않습니다");
  }
  const parsed = new Date(`${clean}T00:00:00Z`);
  if (Number.isNaN(parsed.getTime()) || parsed.toISOString().slice(0, 10) !== clean) {
    throw new Ga4SyncError("GA4 날짜가 올바르지 않습니다");
  }
  return clean;
}

function addUtcDays(value: string, days: number): string {
  const parsed = new Date(`${value}T00:00:00Z`);
  parsed.setUTCDate(parsed.getUTCDate() + days);
  return parsed.toISOString().slice(0, 10);
}

function utcDayDistance(start: string, end: string): number {
  return Math.round(
    (new Date(`${end}T00:00:00Z`).getTime() - new Date(`${start}T00:00:00Z`).getTime()) / 86_400_000,
  );
}

export function resolveDateRange(
  input: DateRangeInput,
  now = new Date(),
): { start: string; end: string } {
  let start: string;
  let end: string;
  if (input.rangeStart !== undefined || input.rangeEnd !== undefined) {
    if (input.rangeStart === undefined || input.rangeEnd === undefined) {
      throw new Ga4SyncError("GA4 시작일과 종료일이 모두 필요합니다");
    }
    start = isoDate(input.rangeStart);
    end = isoDate(input.rangeEnd);
  } else {
    const days = input.days ?? 30;
    if (!Number.isInteger(days) || days < 1 || days > 90) {
      throw new Ga4SyncError("GA4 조회 기간은 일 일부터 구십 일까지 가능합니다");
    }
    end = new Date(now.getTime()).toISOString().slice(0, 10);
    start = addUtcDays(end, -(days - 1));
  }
  const distance = utcDayDistance(start, end);
  if (distance < 0 || distance > 89) {
    throw new Ga4SyncError("GA4 조회 기간은 최대 구십 일입니다");
  }
  return { start, end };
}

export function buildProductReport(id: string, start: string, end: string) {
  propertyId(id);
  return {
    dateRanges: [{ startDate: isoDate(start), endDate: isoDate(end) }],
    dimensions: [{ name: "date" }, { name: "itemId" }, { name: "itemName" }],
    metrics: [{ name: "itemsClickedInList" }],
    dimensionFilter: {
      filter: {
        fieldName: "itemListId",
        stringFilter: { matchType: "EXACT", value: LINK_HUB_LIST_ID },
      },
    },
    limit: "10000",
    keepEmptyRows: false,
  };
}

export function buildTrafficReport(id: string, start: string, end: string) {
  propertyId(id);
  return {
    dateRanges: [{ startDate: isoDate(start), endDate: isoDate(end) }],
    dimensions: [{ name: "date" }, { name: "sessionSource" }, { name: "sessionMedium" }],
    metrics: [{ name: "sessions" }, { name: "activeUsers" }],
    limit: "10000",
    keepEmptyRows: false,
  };
}

function valueAt(values: Ga4Value[] | undefined, index: number): string {
  if (!Array.isArray(values) || index < 0 || index >= values.length) {
    throw new Ga4SyncError("GA4 응답 행 형식이 올바르지 않습니다");
  }
  return String(values[index]?.value ?? "").trim();
}

function integerAt(values: Ga4Value[] | undefined, index: number): number {
  const raw = valueAt(values, index);
  if (!/^\d+$/.test(raw || "0")) {
    throw new Ga4SyncError("GA4 지표가 음이 아닌 정수가 아닙니다");
  }
  const parsed = Number(raw || "0");
  if (!Number.isSafeInteger(parsed) || parsed < 0) {
    throw new Ga4SyncError("GA4 지표가 안전한 정수 범위를 벗어났습니다");
  }
  return parsed;
}

function metricDate(raw: string): string {
  if (!/^\d{8}$/.test(raw)) {
    throw new Ga4SyncError("GA4 응답 날짜 형식이 올바르지 않습니다");
  }
  return isoDate(`${raw.slice(0, 4)}-${raw.slice(4, 6)}-${raw.slice(6, 8)}`);
}

export function parseProductRows(
  response: Ga4Response,
  knownProductIds: Set<number>,
): ProductMetricRow[] {
  const aggregate = new Map<string, ProductMetricRow>();
  for (const raw of response.rows ?? []) {
    const date = metricDate(valueAt(raw.dimensionValues, 0));
    const itemId = valueAt(raw.dimensionValues, 1);
    if (!itemId || itemId === "(not set)") continue;
    if (itemId.length > 128) throw new Ga4SyncError("GA4 상품 ID가 너무 깁니다");
    const itemName = valueAt(raw.dimensionValues, 2);
    const numericId = /^\d+$/.test(itemId) ? Number(itemId) : null;
    const productId = numericId !== null && knownProductIds.has(numericId) ? numericId : null;
    const key = `${date}\u0000${itemId}`;
    const current = aggregate.get(key) ?? {
      metric_date: date,
      item_id: itemId,
      product_id: productId,
      item_name: itemName,
      clicks: 0,
    };
    current.clicks += integerAt(raw.metricValues, 0);
    if (itemName) current.item_name = itemName;
    if (productId !== null) current.product_id = productId;
    aggregate.set(key, current);
  }
  return Array.from(aggregate.values()).sort(
    (a, b) => a.metric_date.localeCompare(b.metric_date) || a.item_id.localeCompare(b.item_id),
  );
}

export function parseTrafficRows(response: Ga4Response): TrafficMetricRow[] {
  const aggregate = new Map<string, TrafficMetricRow>();
  for (const raw of response.rows ?? []) {
    const date = metricDate(valueAt(raw.dimensionValues, 0));
    const source = valueAt(raw.dimensionValues, 1) || "(not set)";
    const medium = valueAt(raw.dimensionValues, 2) || "(not set)";
    if (source.length > 256 || medium.length > 128) {
      throw new Ga4SyncError("GA4 유입 경로 값이 너무 깁니다");
    }
    const key = `${date}\u0000${source}\u0000${medium}`;
    const current = aggregate.get(key) ?? {
      metric_date: date,
      source,
      medium,
      sessions: 0,
      active_users: 0,
    };
    current.sessions += integerAt(raw.metricValues, 0);
    current.active_users += integerAt(raw.metricValues, 1);
    aggregate.set(key, current);
  }
  return Array.from(aggregate.values()).sort(
    (a, b) => a.metric_date.localeCompare(b.metric_date)
      || a.source.localeCompare(b.source)
      || a.medium.localeCompare(b.medium),
  );
}

export function timingSafeEqual(left: string, right: string): boolean {
  const encoder = new TextEncoder();
  const a = encoder.encode(left);
  const b = encoder.encode(right);
  const maximum = Math.max(a.length, b.length, 1);
  let difference = a.length ^ b.length;
  for (let index = 0; index < maximum; index += 1) {
    difference |= (a[index] ?? 0) ^ (b[index] ?? 0);
  }
  return difference === 0;
}

function bytesToBase64(bytes: Uint8Array): string {
  let binary = "";
  const chunkSize = 0x8000;
  for (let offset = 0; offset < bytes.length; offset += chunkSize) {
    binary += String.fromCharCode(...bytes.subarray(offset, offset + chunkSize));
  }
  return btoa(binary);
}

function base64Url(bytes: Uint8Array): string {
  return bytesToBase64(bytes)
    .replace(/=/g, "")
    .replace(/\+/g, "-")
    .replace(/\//g, "_");
}

function encodeJson(value: unknown): string {
  return base64Url(new TextEncoder().encode(JSON.stringify(value)));
}

function pemToPkcs8(value: string): Uint8Array {
  const body = value
    .replace("-----BEGIN PRIVATE KEY-----", "")
    .replace("-----END PRIVATE KEY-----", "")
    .replace(/\s+/g, "");
  if (!body) throw new Ga4SyncError("GA4 서비스 계정 private key가 비어 있습니다");
  try {
    return Uint8Array.from(atob(body), (character) => character.charCodeAt(0));
  } catch {
    throw new Ga4SyncError("GA4 서비스 계정 private key 형식이 올바르지 않습니다");
  }
}

export async function createServiceAccountAssertion(
  credentials: ServiceAccountCredentials,
  nowSeconds = Math.floor(Date.now() / 1000),
): Promise<string> {
  const email = String(credentials?.client_email ?? "").trim();
  if (!email.endsWith(".iam.gserviceaccount.com") && !email.endsWith("@example.iam.gserviceaccount.com")) {
    throw new Ga4SyncError("GA4 서비스 계정 이메일이 올바르지 않습니다");
  }
  if (!Number.isInteger(nowSeconds) || nowSeconds <= 0) {
    throw new Ga4SyncError("GA4 인증 시각이 올바르지 않습니다");
  }
  const header = encodeJson({ alg: "RS256", typ: "JWT" });
  const payload = encodeJson({
    iss: email,
    scope: ANALYTICS_SCOPE,
    aud: "https://oauth2.googleapis.com/token",
    iat: nowSeconds,
    exp: nowSeconds + 3600,
  });
  let privateKey: CryptoKey;
  try {
    privateKey = await crypto.subtle.importKey(
      "pkcs8",
      pemToPkcs8(credentials.private_key),
      { name: "RSASSA-PKCS1-v1_5", hash: "SHA-256" },
      false,
      ["sign"],
    );
  } catch (error) {
    if (error instanceof Ga4SyncError) throw error;
    throw new Ga4SyncError("GA4 서비스 계정 private key를 읽지 못했습니다");
  }
  const signingInput = `${header}.${payload}`;
  const signature = await crypto.subtle.sign(
    { name: "RSASSA-PKCS1-v1_5" },
    privateKey,
    new TextEncoder().encode(signingInput),
  );
  return `${signingInput}.${base64Url(new Uint8Array(signature))}`;
}

export async function exchangeAccessToken(
  assertion: string,
  fetcher: FetchLike = fetch,
): Promise<string> {
  const body = new URLSearchParams({
    grant_type: "urn:ietf:params:oauth:grant-type:jwt-bearer",
    assertion,
  });
  const response = await fetcher("https://oauth2.googleapis.com/token", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body,
  });
  if (!response.ok) {
    throw new Ga4SyncError(`Google OAuth 인증 실패 (${response.status})`);
  }
  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    throw new Ga4SyncError("Google OAuth 응답이 JSON 형식이 아닙니다");
  }
  const token = typeof payload === "object" && payload !== null
    ? (payload as Record<string, unknown>).access_token
    : null;
  if (typeof token !== "string" || !token) {
    throw new Ga4SyncError("Google OAuth 액세스 토큰이 없습니다");
  }
  return token;
}

export async function runReport(
  id: string,
  report: Record<string, unknown>,
  accessToken: string,
  fetcher: FetchLike = fetch,
): Promise<Ga4Response> {
  if (!accessToken) throw new Ga4SyncError("GA4 액세스 토큰이 없습니다");
  const response = await fetcher(
    `${DATA_API_ROOT}/properties/${propertyId(id)}:runReport`,
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${accessToken}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify(report),
    },
  );
  if (!response.ok) {
    let detail = "";
    try {
      detail = (await response.text()).replace(/[\r\n]+/g, " ").slice(0, 300);
    } catch {
      detail = "";
    }
    throw new Ga4SyncError(`GA4 Data API 실패 (${response.status})${detail ? `: ${detail}` : ""}`);
  }
  try {
    return await response.json() as Ga4Response;
  } catch {
    throw new Ga4SyncError("GA4 Data API 응답이 JSON 형식이 아닙니다");
  }
}
