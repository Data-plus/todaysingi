import assert from "node:assert/strict";
import test from "node:test";
import {
  buildProductReport,
  buildTrafficReport,
  createServiceAccountAssertion,
  exchangeAccessToken,
  parseProductRows,
  parseTrafficRows,
  resolveDateRange,
  runReport,
  timingSafeEqual,
} from "./ga4.ts";

test("reports use the todaysingi ecommerce contract", () => {
  const product = buildProductReport("545183806", "2026-06-14", "2026-07-13");
  assert.deepEqual(product.dimensions, [{ name: "date" }, { name: "itemId" }, { name: "itemName" }]);
  assert.deepEqual(product.metrics, [{ name: "itemsClickedInList" }]);
  assert.equal(product.dimensionFilter.filter.fieldName, "itemListId");
  assert.equal(product.dimensionFilter.filter.stringFilter.value, "todaysingi_link_hub");

  const traffic = buildTrafficReport("545183806", "2026-06-14", "2026-07-13");
  assert.deepEqual(traffic.metrics, [{ name: "sessions" }, { name: "activeUsers" }]);
});

test("date range defaults to thirty days and rejects more than ninety", () => {
  assert.deepEqual(resolveDateRange({}, new Date("2026-07-13T00:00:00Z")), {
    start: "2026-06-14",
    end: "2026-07-13",
  });
  assert.throws(() => resolveDateRange({ days: 91 }, new Date("2026-07-13T00:00:00Z")));
});

test("GA rows are validated, aggregated, and mapped to known products", () => {
  const products = parseProductRows({ rows: [
    { dimensionValues: [{ value: "20260713" }, { value: "001" }, { value: "마법지팡이" }], metricValues: [{ value: "2" }] },
    { dimensionValues: [{ value: "20260713" }, { value: "001" }, { value: "마법지팡이" }], metricValues: [{ value: "3" }] },
    { dimensionValues: [{ value: "20260713" }, { value: "(not set)" }, { value: "" }], metricValues: [{ value: "9" }] },
  ] }, new Set([1]));
  assert.deepEqual(products, [{ metric_date: "2026-07-13", item_id: "001", product_id: 1, item_name: "마법지팡이", clicks: 5 }]);

  const traffic = parseTrafficRows({ rows: [
    { dimensionValues: [{ value: "20260713" }, { value: "instagram.com" }, { value: "referral" }], metricValues: [{ value: "4" }, { value: "3" }] },
  ] });
  assert.deepEqual(traffic, [{ metric_date: "2026-07-13", source: "instagram.com", medium: "referral", sessions: 4, active_users: 3 }]);
  assert.throws(() => parseTrafficRows({ rows: [
    { dimensionValues: [{ value: "bad" }, { value: "x" }, { value: "y" }], metricValues: [{ value: "1" }, { value: "1" }] },
  ] }));
});

test("service account assertion is RS256, scoped, and short lived", async () => {
  const keys = await crypto.subtle.generateKey(
    { name: "RSASSA-PKCS1-v1_5", modulusLength: 2048, publicExponent: new Uint8Array([1, 0, 1]), hash: "SHA-256" },
    true,
    ["sign", "verify"],
  );
  const pkcs8 = new Uint8Array(await crypto.subtle.exportKey("pkcs8", keys.privateKey));
  const pemBody = Buffer.from(pkcs8).toString("base64").match(/.{1,64}/g)?.join("\n") ?? "";
  const assertion = await createServiceAccountAssertion({
    client_email: "reader@example.iam.gserviceaccount.com",
    private_key: `-----BEGIN PRIVATE KEY-----\n${pemBody}\n-----END PRIVATE KEY-----\n`,
  }, 1_700_000_000);
  const [encodedHeader, encodedPayload, encodedSignature] = assertion.split(".");
  const decode = (value: string) => JSON.parse(Buffer.from(value, "base64url").toString("utf8"));
  assert.deepEqual(decode(encodedHeader), { alg: "RS256", typ: "JWT" });
  const payload = decode(encodedPayload);
  assert.equal(payload.iss, "reader@example.iam.gserviceaccount.com");
  assert.equal(payload.scope, "https://www.googleapis.com/auth/analytics.readonly");
  assert.equal(payload.iat, 1_700_000_000);
  assert.equal(payload.exp, 1_700_003_600);
  assert.equal(await crypto.subtle.verify(
    { name: "RSASSA-PKCS1-v1_5" },
    keys.publicKey,
    Buffer.from(encodedSignature, "base64url"),
    new TextEncoder().encode(`${encodedHeader}.${encodedPayload}`),
  ), true);
});

test("OAuth exchange and Data API calls never include credentials in errors", async () => {
  let oauthBody = "";
  const token = await exchangeAccessToken("signed.assertion.value", async (_input, init) => {
    oauthBody = String(init?.body ?? "");
    return new Response(JSON.stringify({ access_token: "short-lived-token", expires_in: 3600 }), { status: 200 });
  });
  assert.equal(token, "short-lived-token");
  assert.match(oauthBody, /grant_type=/);
  assert.match(oauthBody, /assertion=signed.assertion.value/);

  await assert.rejects(
    runReport("545183806", {}, "short-lived-token", async () => new Response("permission denied", { status: 403 })),
    (error: Error) => error.message.includes("403") && !error.message.includes("short-lived-token"),
  );
});

test("cron secret comparison handles length and content safely", () => {
  assert.equal(timingSafeEqual("same-value", "same-value"), true);
  assert.equal(timingSafeEqual("same-value", "other-value"), false);
  assert.equal(timingSafeEqual("short", "much-longer"), false);
});
