import { createClient } from "https://esm.sh/@supabase/supabase-js@2.52.1";

const ADMIN_EMAIL = "plusmg@gmail.com";
const ALLOWED_ORIGINS = new Set([
  "https://todaysingi.netlify.app",
  "http://localhost:5173",
]);

function cors(origin: string | null) {
  const allowed = origin && ALLOWED_ORIGINS.has(origin) ? origin : "https://todaysingi.netlify.app";
  return {
    "Access-Control-Allow-Origin": allowed,
    "Access-Control-Allow-Headers": "authorization, apikey, content-type, x-client-info",
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Vary": "Origin",
  };
}

function response(origin: string | null, status: number, body: Record<string, unknown>) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { ...cors(origin), "Content-Type": "application/json" },
  });
}

Deno.serve(async (request) => {
  const origin = request.headers.get("Origin");
  if (request.method === "OPTIONS") return new Response(null, { status: 204, headers: cors(origin) });
  if (request.method !== "POST") return response(origin, 405, { error: "method_not_allowed" });

  const authorization = request.headers.get("Authorization") || "";
  const [scheme, token] = authorization.split(" ", 2);
  if (scheme?.toLowerCase() !== "bearer" || !token) {
    return response(origin, 401, { error: "authentication_required" });
  }

  const supabaseUrl = Deno.env.get("SUPABASE_URL") || "";
  const anonKey = Deno.env.get("SUPABASE_ANON_KEY") || "";
  const dispatcherUrl = Deno.env.get("CLOUD_DISPATCHER_URL") || "";
  if (!supabaseUrl || !anonKey || !dispatcherUrl.startsWith("https://")) {
    return response(origin, 503, { error: "dispatch_not_configured" });
  }

  const supabase = createClient(supabaseUrl, anonKey, {
    auth: { persistSession: false, autoRefreshToken: false },
  });
  const { data, error } = await supabase.auth.getUser(token);
  if (error || !data.user || data.user.email?.toLowerCase() !== ADMIN_EMAIL) {
    return response(origin, 403, { error: "admin_only" });
  }

  let reason = "admin_queue";
  try {
    const body = await request.json();
    if (typeof body?.reason === "string" && /^[A-Za-z0-9_.:-]{1,128}$/.test(body.reason)) {
      reason = body.reason;
    }
  } catch {
    // 본문이 없으면 기본 reason으로 실행한다.
  }

  const dispatchResponse = await fetch(`${dispatcherUrl.replace(/\/$/, "")}/v1/dispatch`, {
    method: "POST",
    headers: {
      "Authorization": `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ reason }),
  });
  if (!dispatchResponse.ok) {
    return response(origin, 502, { error: "cloud_dispatch_failed" });
  }
  const result = await dispatchResponse.json();
  return response(origin, 202, { accepted: true, operation: result.operation || null });
});
