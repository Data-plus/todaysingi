import assert from "node:assert/strict";
import test from "node:test";
import { ga4ConnectionInfo } from "../src/lib/dashboard.ts";
import { summarizeGa4 } from "../src/lib/performance.ts";

test("GA4 summary combines daily clicks and traffic without inventing sales", () => {
  const summary = summarizeGa4(
    [
      { metricDate: "2026-07-12", itemId: "001", productId: 1, itemName: "마법지팡이", clicks: 3 },
      { metricDate: "2026-07-13", itemId: "001", productId: 1, itemName: "마법지팡이", clicks: 2 },
      { metricDate: "2026-07-13", itemId: "004", productId: 4, itemName: "회전 선반", clicks: 5 },
    ],
    [
      { metricDate: "2026-07-12", source: "instagram.com", medium: "referral", sessions: 4, activeUsers: 3 },
      { metricDate: "2026-07-13", source: "instagram.com", medium: "referral", sessions: 6, activeUsers: 5 },
      { metricDate: "2026-07-13", source: "(direct)", medium: "(none)", sessions: 2, activeUsers: 2 },
    ],
  );

  assert.equal(summary.totalClicks, 10);
  assert.equal(summary.sessions, 12);
  assert.equal(summary.activeUsers, 10);
  assert.deepEqual(summary.dailyTrend, [
    { date: "2026-07-12", clicks: 3, sessions: 4, activeUsers: 3 },
    { date: "2026-07-13", clicks: 7, sessions: 8, activeUsers: 7 },
  ]);
  assert.deepEqual(summary.products.map((row) => [row.productId, row.clicks, row.share]), [
    [1, 5, 50],
    [4, 5, 50],
  ]);
  assert.deepEqual(summary.sources.map((row) => [row.source, row.medium, row.sessions]), [
    ["instagram.com", "referral", 10],
    ["(direct)", "(none)", 2],
  ]);
});

test("empty GA4 rows produce explicit zeros and empty series", () => {
  assert.deepEqual(summarizeGa4([], []), {
    totalClicks: 0,
    sessions: 0,
    activeUsers: 0,
    dailyTrend: [],
    products: [],
    sources: [],
  });
});

test("GA4 connection reflects a successful or failed server sync", () => {
  const sync = {
    integration: "ga4",
    status: "succeeded" as const,
    lastAttemptAt: "2026-07-13T00:00:00Z",
    lastSuccessAt: "2026-07-13T00:00:00Z",
    rangeStart: "2026-06-14",
    rangeEnd: "2026-07-13",
    rowCount: 42,
    errorSummary: null,
    updatedAt: "2026-07-13T00:00:00Z",
  };
  const connected = ga4ConnectionInfo(sync, true, new Date("2026-07-13T01:00:00Z").getTime());
  assert.equal(connected.status, "connected");
  assert.equal(connected.label, "수집 중");
  assert.match(connected.detail, /42개/);

  const failed = ga4ConnectionInfo({ ...sync, status: "failed", errorSummary: "권한 없음" }, true);
  assert.equal(failed.status, "error");
  assert.equal(failed.label, "동기화 실패");
});
