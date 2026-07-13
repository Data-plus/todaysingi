import type { Ga4ProductDaily, Ga4TrafficDaily, PerformanceSummary } from "../types/admin";

export function summarizeGa4(
  productRows: Ga4ProductDaily[],
  trafficRows: Ga4TrafficDaily[],
): PerformanceSummary {
  const daily = new Map<string, PerformanceSummary["dailyTrend"][number]>();
  const products = new Map<string, PerformanceSummary["products"][number]>();
  const sources = new Map<string, PerformanceSummary["sources"][number]>();

  let totalClicks = 0;
  for (const row of productRows) {
    const clicks = Math.max(0, Number(row.clicks) || 0);
    totalClicks += clicks;
    const day = daily.get(row.metricDate) || {
      date: row.metricDate,
      clicks: 0,
      sessions: 0,
      activeUsers: 0,
    };
    day.clicks += clicks;
    daily.set(row.metricDate, day);

    const current = products.get(row.itemId) || {
      productId: row.productId,
      itemId: row.itemId,
      itemName: row.itemName,
      clicks: 0,
      share: 0,
    };
    current.clicks += clicks;
    if (row.itemName) current.itemName = row.itemName;
    if (row.productId !== null) current.productId = row.productId;
    products.set(row.itemId, current);
  }

  let sessions = 0;
  let activeUsers = 0;
  for (const row of trafficRows) {
    const rowSessions = Math.max(0, Number(row.sessions) || 0);
    const rowUsers = Math.max(0, Number(row.activeUsers) || 0);
    sessions += rowSessions;
    activeUsers += rowUsers;
    const day = daily.get(row.metricDate) || {
      date: row.metricDate,
      clicks: 0,
      sessions: 0,
      activeUsers: 0,
    };
    day.sessions += rowSessions;
    day.activeUsers += rowUsers;
    daily.set(row.metricDate, day);

    const key = `${row.source}\u0000${row.medium}`;
    const current = sources.get(key) || {
      source: row.source,
      medium: row.medium,
      sessions: 0,
      activeUsers: 0,
      share: 0,
    };
    current.sessions += rowSessions;
    current.activeUsers += rowUsers;
    sources.set(key, current);
  }

  const productSummary = Array.from(products.values())
    .map((row) => ({
      ...row,
      share: totalClicks ? (row.clicks / totalClicks) * 100 : 0,
    }))
    .sort((a, b) => b.clicks - a.clicks || a.itemId.localeCompare(b.itemId));
  const sourceSummary = Array.from(sources.values())
    .map((row) => ({
      ...row,
      share: sessions ? (row.sessions / sessions) * 100 : 0,
    }))
    .sort((a, b) => b.sessions - a.sessions || a.source.localeCompare(b.source));

  return {
    totalClicks,
    sessions,
    activeUsers,
    dailyTrend: Array.from(daily.values()).sort((a, b) => a.date.localeCompare(b.date)),
    products: productSummary,
    sources: sourceSummary,
  };
}
