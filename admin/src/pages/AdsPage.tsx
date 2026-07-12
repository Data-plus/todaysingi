import { Icon } from "../components/Icon";
import { StatusBadge } from "../components/StatusBadge";
import type { ConnectionInfo } from "../types/admin";

export function AdsPage({ connections, onOpenSettings }: { connections: ConnectionInfo[]; onOpenSettings: () => void }) {
  const meta = connections.find((connection) => connection.id === "meta");
  return (
    <div className="page-stack">
      <section className="ads-summary">
        <div><span className="source-icon source-meta">M</span><div><p className="section-kicker">META MARKETING API</p><h2>광고 A/B 운영</h2><p>소재 두 종을 같은 조건으로 집행하고 결과를 상품별 학습 데이터로 남깁니다.</p></div></div>
        <div className="ads-summary-actions">{meta ? <StatusBadge status={meta.status} label={meta.label}/> : null}<button type="button" className="secondary-button" onClick={onOpenSettings}>연동 상태 확인</button><button type="button" className="primary-button" disabled title="Meta 광고 데이터 모델과 승인 흐름 구현 후 사용할 수 있습니다"><Icon name="plus" size={17}/>새 A/B 광고</button></div>
      </section>

      <section className="metrics-grid performance-metrics">
        <article className="metric-card metric-waiting"><div className="metric-label"><span>운영 캠페인</span></div><strong>연결 대기</strong><p>Meta 캠페인 동기화 필요</p></article>
        <article className="metric-card metric-waiting"><div className="metric-label"><span>광고비</span></div><strong>연결 대기</strong><p>Meta Insights API 필요</p></article>
        <article className="metric-card metric-waiting"><div className="metric-label"><span>광고 클릭</span></div><strong>연결 대기</strong><p>Meta Insights API 필요</p></article>
        <article className="metric-card metric-waiting"><div className="metric-label"><span>평균 CPC</span></div><strong>연결 대기</strong><p>지출·클릭 연결 후 계산</p></article>
        <article className="metric-card metric-waiting"><div className="metric-label"><span>구매 매출</span></div><strong>연결 대기</strong><p>쿠팡 Reporting API 필요</p></article>
        <article className="metric-card metric-waiting"><div className="metric-label"><span>ROAS</span></div><strong>연결 대기</strong><p>매출·광고비 연결 후 계산</p></article>
      </section>

      <section className="section-block">
        <div className="section-title-row compact"><div><p className="section-kicker">EXPERIMENTS</p><h2>광고 실험</h2><p>연결 후 소재 A/B, 예산, 결과와 승자를 이곳에서 관리합니다.</p></div></div>
        <div className="table-card"><table className="data-table"><thead><tr><th>상품</th><th>광고안</th><th>상태</th><th>예산</th><th>광고비</th><th>클릭</th><th>CPC</th><th>ROAS</th><th>결과</th></tr></thead><tbody><tr><td colSpan={9}><div className="empty-state large-empty"><Icon name="send" size={26}/><strong>아직 생성된 광고 실험이 없습니다.</strong><p>Meta 연결과 광고 승인 흐름이 준비되면 생성할 수 있습니다.</p><button type="button" className="secondary-button" disabled title="Meta 연동 후 사용">연결 후 사용</button></div></td></tr></tbody></table></div>
      </section>

      <section className="safety-note"><Icon name="alert" size={20}/><div><strong>광고 집행은 자동으로 시작되지 않습니다.</strong><p>연결 후에도 광고안 검토와 예산 확인을 거쳐 명시적으로 승인해야 하며, 실행 이력은 모두 기록됩니다.</p></div></section>
    </div>
  );
}
