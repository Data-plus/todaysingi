import { Icon } from "../components/Icon";
import { MetricCard } from "../components/MetricCard";
import { StatusBadge } from "../components/StatusBadge";
import { formatDateTime, formatNumber } from "../lib/dashboard";
import type {
  AdminProduct,
  ConnectionInfo,
  IntegrationSync,
  PerformanceSummary,
} from "../types/admin";

function shortDate(value: string) {
  const [, month, day] = value.split("-");
  return `${month}.${day}`;
}

function TrendChart({ rows }: { rows: PerformanceSummary["dailyTrend"] }) {
  if (!rows.length) {
    return (
      <div className="performance-empty" role="status">
        <Icon name="chart" size={24}/>
        <strong>아직 수집된 GA4 데이터가 없습니다.</strong>
        <p>첫 동기화를 실행하면 최근 삼십 일 추이가 표시됩니다.</p>
      </div>
    );
  }

  const width = 760;
  const height = 244;
  const paddingX = 28;
  const paddingY = 24;
  const maximum = Math.max(1, ...rows.flatMap((row) => [row.clicks, row.sessions]));
  const x = (index: number) => rows.length === 1
    ? width / 2
    : paddingX + (index / (rows.length - 1)) * (width - paddingX * 2);
  const y = (value: number) => height - paddingY - (value / maximum) * (height - paddingY * 2);
  const clicks = rows.map((row, index) => `${x(index)},${y(row.clicks)}`).join(" ");
  const sessions = rows.map((row, index) => `${x(index)},${y(row.sessions)}`).join(" ");
  const labelIndexes = new Set([0, Math.floor((rows.length - 1) / 2), rows.length - 1]);

  return (
    <>
      <figure className="performance-chart" aria-labelledby="traffic-chart-title traffic-chart-caption">
        <figcaption id="traffic-chart-caption" className="chart-legend">
          <span><i className="legend-clicks"/>상품 클릭</span>
          <span><i className="legend-sessions"/>세션</span>
        </figcaption>
        <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label="날짜별 상품 클릭과 세션 선 그래프">
          {[0, 0.5, 1].map((ratio) => (
            <line
              key={ratio}
              className="chart-gridline"
              x1={paddingX}
              x2={width - paddingX}
              y1={paddingY + ratio * (height - paddingY * 2)}
              y2={paddingY + ratio * (height - paddingY * 2)}
            />
          ))}
          <polyline className="chart-line chart-line-sessions" points={sessions}/>
          <polyline className="chart-line chart-line-clicks" points={clicks}/>
          {rows.map((row, index) => labelIndexes.has(index) ? (
            <text key={row.date} className="chart-axis-label" x={x(index)} y={height - 3} textAnchor="middle">
              {shortDate(row.date)}
            </text>
          ) : null)}
        </svg>
      </figure>
      <details className="chart-data-table">
        <summary>차트 수치 표로 보기</summary>
        <div className="table-card">
          <table className="data-table">
            <thead><tr><th>날짜</th><th>상품 클릭</th><th>세션</th><th>활성 사용자 접점</th></tr></thead>
            <tbody>{rows.map((row) => (
              <tr key={row.date}>
                <td data-label="날짜">{row.date}</td>
                <td data-label="상품 클릭">{formatNumber(row.clicks)}</td>
                <td data-label="세션">{formatNumber(row.sessions)}</td>
                <td data-label="활성 사용자 접점">{formatNumber(row.activeUsers)}</td>
              </tr>
            ))}</tbody>
          </table>
        </div>
      </details>
    </>
  );
}

type Props = {
  products: AdminProduct[];
  connections: ConnectionInfo[];
  performance: PerformanceSummary;
  sync?: IntegrationSync;
  syncing: boolean;
  live: boolean;
  onSync: () => void;
  onOpenSettings: () => void;
};

export function PerformancePage({
  products,
  connections,
  performance,
  sync,
  syncing,
  live,
  onSync,
  onOpenSettings,
}: Props) {
  const ga4 = connections.find((connection) => connection.id === "ga4");
  const coupang = connections.find((connection) => connection.id === "coupang");
  const productById = new Map(products.map((product) => [product.id, product]));
  const syncRunning = sync?.status === "queued" || sync?.status === "running";
  const lastSync = sync?.lastSuccessAt ? formatDateTime(sync.lastSuccessAt) : "성공 기록 없음";
  const productRows = performance.products.filter((row) => row.productId === null || productById.has(row.productId));

  return (
    <div className="page-stack performance-page">
      <section className="performance-hero">
        <div>
          <p className="section-kicker">PERFORMANCE · LAST 30 DAYS</p>
          <h2>{ga4?.status === "connected" ? "링크 허브의 반응이 보이기 시작했습니다." : "성과 수집을 준비하고 있습니다."}</h2>
          <p>GA4의 실제 클릭과 유입만 표시합니다. 주문·매출은 쿠팡 Reporting API 승인 전까지 비워 둡니다.</p>
          <div className="performance-sync-meta" aria-live="polite">
            <span className={`sync-dot sync-${ga4?.status || "waiting"}`} aria-hidden="true"/>
            <strong>{ga4?.label || "연결 대기"}</strong>
            <span>마지막 성공 {lastSync}</span>
            {sync?.rangeStart && sync.rangeEnd ? <span>{sync.rangeStart}–{sync.rangeEnd}</span> : null}
          </div>
        </div>
        <div className="performance-hero-actions">
          <button type="button" className="primary-button" disabled={!live || syncing || syncRunning} onClick={onSync}>
            <Icon name="refresh" size={17}/>{syncing || syncRunning ? "동기화 중…" : "GA4 새로고침"}
          </button>
          <button type="button" className="secondary-button" onClick={onOpenSettings}>
            <Icon name="settings" size={17}/>연동 설정
          </button>
        </div>
      </section>

      <section className="metrics-grid performance-live-metrics" aria-label="최근 삼십 일 GA4 성과">
        <MetricCard label="상품 링크 클릭" value={formatNumber(performance.totalClicks)} detail="select_item 이벤트 기준" tone={performance.totalClicks ? "success" : "default"}/>
        <MetricCard label="세션" value={formatNumber(performance.sessions)} detail="유입 경로별 세션 합계"/>
        <MetricCard label="활성 사용자 접점" value={formatNumber(performance.activeUsers)} detail="일자·유입 경로별 활성 사용자 합계"/>
        <MetricCard label="쿠팡 주문" value={null} detail="파트너스 최종 승인 후 연결"/>
      </section>

      <section className="section-block">
        <div className="section-title-row compact">
          <div><p className="section-kicker">DAILY TREND</p><h2 id="traffic-chart-title">클릭과 방문 추이</h2><p>상품 클릭과 사이트 세션을 같은 날짜 축에서 비교합니다.</p></div>
          <span className="data-period"><Icon name="calendar" size={15}/>최근 삼십 일</span>
        </div>
        <TrendChart rows={performance.dailyTrend}/>
      </section>

      <section className="performance-split-grid">
        <article className="section-block performance-table-section">
          <div className="section-title-row compact"><div><p className="section-kicker">PRODUCTS</p><h2>상품별 클릭</h2><p>링크 허브에서 선택된 상품 기준</p></div></div>
          <div className="table-card">
            <table className="data-table performance-rank-table">
              <thead><tr><th>상품</th><th>클릭</th><th>비중</th></tr></thead>
              <tbody>{productRows.length ? productRows.map((row) => {
                const product = row.productId === null ? undefined : productById.get(row.productId);
                return (
                  <tr key={row.itemId}>
                    <td data-label="상품"><span className="rank-product"><b>{row.itemId.padStart(3, "0")}</b><strong>{product?.title || row.itemName || "미등록 상품"}</strong></span></td>
                    <td data-label="클릭"><strong>{formatNumber(row.clicks)}</strong></td>
                    <td data-label="비중"><span className="share-cell"><i style={{ width: `${Math.min(100, row.share)}%` }}/><em>{row.share.toLocaleString("ko-KR", { maximumFractionDigits: 1 })}%</em></span></td>
                  </tr>
                );
              }) : <tr><td colSpan={3}><div className="empty-state compact-empty"><strong>상품 클릭 데이터가 없습니다.</strong></div></td></tr>}</tbody>
            </table>
          </div>
        </article>

        <article className="section-block performance-table-section">
          <div className="section-title-row compact"><div><p className="section-kicker">ACQUISITION</p><h2>유입 경로</h2><p>세션 source / medium 기준</p></div></div>
          <div className="table-card">
            <table className="data-table source-performance-table">
              <thead><tr><th>경로</th><th>세션</th><th>비중</th></tr></thead>
              <tbody>{performance.sources.length ? performance.sources.slice(0, 10).map((row) => (
                <tr key={`${row.source}/${row.medium}`}>
                  <td data-label="경로"><span className="source-name"><strong>{row.source}</strong><small>{row.medium}</small></span></td>
                  <td data-label="세션"><strong>{formatNumber(row.sessions)}</strong></td>
                  <td data-label="비중">{row.share.toLocaleString("ko-KR", { maximumFractionDigits: 1 })}%</td>
                </tr>
              )) : <tr><td colSpan={3}><div className="empty-state compact-empty"><strong>유입 경로 데이터가 없습니다.</strong></div></td></tr>}</tbody>
            </table>
          </div>
        </article>
      </section>

      <section className="source-grid performance-sources" aria-label="성과 연동 상태">
        <article className="source-card">
          <div className="source-card-top"><span className="source-icon source-google">G</span><div><h2>Google Analytics 4</h2><p>클릭 · 세션 · 유입</p></div>{ga4 ? <StatusBadge status={ga4.status} label={ga4.label}/> : null}</div>
          <div className="source-data-list"><div><span>마지막 성공</span><strong>{lastSync}</strong></div><div><span>저장 행</span><strong>{sync ? `${formatNumber(sync.rowCount)}개` : "—"}</strong></div><div><span>오류</span><strong>{sync?.errorSummary || "없음"}</strong></div></div>
        </article>
        <article className="source-card">
          <div className="source-card-top"><span className="source-icon source-coupang">C</span><div><h2>쿠팡 파트너스</h2><p>주문 · 매출 · 수수료</p></div>{coupang ? <StatusBadge status={coupang.status} label={coupang.label}/> : null}</div>
          <div className="source-data-list"><div><span>현재 상태</span><strong>파트너스 최종 승인 대기</strong></div><div><span>연결 후</span><strong>상품별 주문 · 전환율 · 매출 · 수수료</strong></div></div>
          <p className="source-note"><Icon name="alert" size={15}/>API가 발급될 때까지 판매 수치는 추정하지 않습니다.</p>
        </article>
      </section>
    </div>
  );
}
