import { MetricCard } from "../components/MetricCard";
import { StatusBadge } from "../components/StatusBadge";
import {
  conversionRate,
  formatCurrency,
  formatDateTime,
  formatNumber,
  formatPercent,
  productNeedsAttention,
  summarizeDesk,
} from "../lib/dashboard";
import type { AdminProduct, AdminView, DeskData } from "../types/admin";
import { Icon } from "../components/Icon";

export function OverviewPage({
  data,
  products,
  onNavigate,
  onSelectProduct,
}: {
  data: DeskData;
  products: AdminProduct[];
  onNavigate: (view: AdminView) => void;
  onSelectProduct: (product: AdminProduct) => void;
}) {
  const summary = summarizeDesk(data);
  const recentJobs = data.jobs.slice(0, 6);
  const attentionItems = products
    .map((product) => ({ product, reason: productNeedsAttention(product, data.jobs) }))
    .filter((item): item is { product: AdminProduct; reason: string } => Boolean(item.reason));

  return (
    <div className="page-stack">
      <section className="metrics-grid operations-metrics" aria-label="운영 현황">
        <MetricCard label="활성 상품" value={String(summary.activeProducts)} detail={`게시 완료 ${summary.publishedProducts}개`}/>
        <MetricCard label="대기 작업" value={String(summary.queuedJobs)} detail="Worker가 켜지면 처리" tone={summary.queuedJobs ? "warning" : "default"}/>
        <MetricCard label="실행 중" value={String(summary.runningJobs)} detail={data.worker.online ? data.worker.label : "Worker 오프라인"} tone={summary.runningJobs ? "success" : "default"}/>
        <MetricCard label="실패 작업" value={String(summary.failedJobs)} detail={summary.failedJobs ? "확인이 필요합니다" : "현재 오류 없음"} tone={summary.failedJobs ? "danger" : "success"}/>
      </section>

      <section className="section-block">
        <div className="section-title-row">
          <div><p className="section-kicker">PERFORMANCE</p><h2>성과 요약</h2><p>클릭은 GA4, 주문·매출·수수료는 쿠팡 Reporting API에서 수집합니다.</p></div>
          <button type="button" className="text-button" onClick={() => onNavigate("performance")}>연동 상태 보기 <Icon name="arrow" size={16}/></button>
        </div>
        <div className="metrics-grid performance-metrics">
          <MetricCard label="링크 클릭" value={null} detail="GA4 Data API 필요"/>
          <MetricCard label="쿠팡 주문" value={null} detail="파트너스 최종 승인 필요"/>
          <MetricCard label="매출" value={null} detail="쿠팡 Reporting API 필요"/>
          <MetricCard label="수수료" value={null} detail="쿠팡 Reporting API 필요"/>
          <MetricCard label="광고비" value={null} detail="Meta 지표 수집 필요"/>
          <MetricCard label="ROAS" value={null} detail="매출·광고비 연결 후 계산"/>
        </div>
      </section>

      {attentionItems.length || !data.worker.online ? (
        <section className="attention-panel" aria-labelledby="attention-title">
          <div className="attention-heading"><Icon name="alert" size={20}/><div><h2 id="attention-title">확인이 필요한 항목</h2><p>운영이 멈추기 전에 처리하세요.</p></div></div>
          <div className="attention-list">
            {!data.worker.online ? <button type="button" onClick={() => onNavigate("settings")}><span>로컬 Worker</span><strong>현재 오프라인</strong><Icon name="chevron" size={17}/></button> : null}
            {attentionItems.slice(0, 4).map(({ product, reason }) => <button type="button" key={product.id} onClick={() => onSelectProduct(product)}><span>상품 {String(product.id).padStart(3, "0")}</span><strong>{reason}</strong><Icon name="chevron" size={17}/></button>)}
          </div>
        </section>
      ) : null}

      <section className="section-block">
        <div className="section-title-row compact">
          <div><p className="section-kicker">PRODUCTS</p><h2>상품 운영 현황</h2></div>
          <button type="button" className="text-button" onClick={() => onNavigate("products")}>전체 상품 <Icon name="arrow" size={16}/></button>
        </div>
        <div className="table-card">
          <table className="data-table product-performance-table">
            <thead><tr><th>상품</th><th>단계</th><th>클릭</th><th>주문</th><th>전환율</th><th>매출</th><th>광고비</th><th>ROAS</th><th>업데이트</th></tr></thead>
            <tbody>
              {products.length ? products.slice(0, 8).map((product) => (
                <tr key={product.id}>
                  <td data-label="상품"><button type="button" className="table-product" onClick={() => onSelectProduct(product)}><span>{String(product.id).padStart(3, "0")}</span><strong>{product.title}</strong></button></td>
                  <td data-label="단계"><StatusBadge status={product.stage} label={product.stageLabel}/></td>
                  <td data-label="클릭" className="pending-cell" title="GA4 연결 대기">{formatNumber(product.metrics.linkClicks)}</td>
                  <td data-label="주문" className="pending-cell" title="쿠팡 API 연결 대기">{formatNumber(product.metrics.orders)}</td>
                  <td data-label="전환율" className="pending-cell">{formatPercent(conversionRate(product.metrics))}</td>
                  <td data-label="매출" className="pending-cell">{formatCurrency(product.metrics.revenue)}</td>
                  <td data-label="광고비" className="pending-cell">{formatCurrency(product.metrics.adSpend)}</td>
                  <td data-label="ROAS" className="pending-cell">{formatPercent(product.metrics.roas)}</td>
                  <td data-label="업데이트">{formatDateTime(product.updatedAt)}</td>
                </tr>
              )) : <tr><td colSpan={9}><div className="empty-state compact-empty"><strong>등록된 상품이 없습니다.</strong><p>새 상품을 등록하면 이곳에서 진행 상황을 볼 수 있습니다.</p></div></td></tr>}
            </tbody>
          </table>
        </div>
      </section>

      <section className="section-block">
        <div className="section-title-row compact">
          <div><p className="section-kicker">RECENT JOBS</p><h2>최근 작업</h2></div>
          <button type="button" className="text-button" onClick={() => onNavigate("jobs")}>작업 큐 열기 <Icon name="arrow" size={16}/></button>
        </div>
        <div className="table-card">
          <table className="data-table jobs-preview-table">
            <thead><tr><th>작업</th><th>상품</th><th>상태</th><th>진행률</th><th>수정 시각</th><th>오류</th></tr></thead>
            <tbody>
              {recentJobs.length ? recentJobs.map((job) => <tr key={job.id}><td data-label="작업"><span className="job-name"><small>{job.displayId}</small><strong>{job.typeLabel}</strong></span></td><td data-label="상품">{job.productTitle}</td><td data-label="상태"><StatusBadge status={job.status} label={job.statusLabel}/></td><td data-label="진행률"><span className="progress-copy">{job.progress}%</span></td><td data-label="수정 시각">{formatDateTime(job.updatedAt)}</td><td data-label="오류" className={job.errorSummary ? "error-copy" : "muted-copy"}>{job.errorSummary || "—"}</td></tr>) : <tr><td colSpan={6}><div className="empty-state compact-empty"><strong>작업 기록이 없습니다.</strong></div></td></tr>}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
