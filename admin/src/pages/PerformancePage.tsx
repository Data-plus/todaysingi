import { Icon } from "../components/Icon";
import { StatusBadge } from "../components/StatusBadge";
import type { AdminProduct, ConnectionInfo } from "../types/admin";

export function PerformancePage({ products, connections, onOpenSettings }: { products: AdminProduct[]; connections: ConnectionInfo[]; onOpenSettings: () => void }) {
  const ga4 = connections.find((connection) => connection.id === "ga4");
  const coupang = connections.find((connection) => connection.id === "coupang");

  return (
    <div className="page-stack">
      <section className="connection-hero">
        <div><p className="section-kicker">DATA PIPELINE</p><h2>성과 데이터 연결부터 시작합니다.</h2><p>현재는 실제 판매 데이터를 가져올 자격 증명이 없어 모든 성과가 <strong>연결 대기</strong> 상태입니다. 숫자를 추정해 채우지 않습니다.</p></div>
        <button type="button" className="secondary-button" onClick={onOpenSettings}><Icon name="settings" size={17}/>연동 설정 보기</button>
      </section>

      <section className="source-grid" aria-label="성과 데이터 원천">
        <article className="source-card">
          <div className="source-card-top"><span className="source-icon source-google">G</span><div><h2>Google Analytics 4</h2><p>프로필 링크 클릭과 유입</p></div>{ga4 ? <StatusBadge status={ga4.status} label={ga4.label}/> : null}</div>
          <div className="source-data-list"><div><span>수집 지표</span><strong>상품 링크 클릭 · 유입 경로 · 날짜별 추이</strong></div><div><span>필요 정보</span><strong>GA4 Property ID · 서버 측 Data API 자격 증명</strong></div><div><span>현재 보유</span><strong>Measurement ID만 설정됨</strong></div></div>
          <p className="source-note"><Icon name="alert" size={15}/>Measurement ID는 웹 이벤트 전송용이며 관리자에서 조회할 Data API 권한을 대신하지 않습니다.</p>
        </article>
        <article className="source-card">
          <div className="source-card-top"><span className="source-icon source-coupang">C</span><div><h2>쿠팡 파트너스</h2><p>주문, 매출, 수수료</p></div>{coupang ? <StatusBadge status={coupang.status} label={coupang.label}/> : null}</div>
          <div className="source-data-list"><div><span>수집 지표</span><strong>클릭 · 주문 · 매출 · 구매액 · 수수료</strong></div><div><span>필요 정보</span><strong>Partners Access Key · Secret Key</strong></div><div><span>현재 상태</span><strong>파트너스 최종 승인 대기</strong></div></div>
          <p className="source-note"><Icon name="alert" size={15}/>최종 승인 후 Reporting API가 발급되면 연결할 수 있습니다. 구매 데이터의 진실 소스입니다.</p>
        </article>
      </section>

      <section className="section-block">
        <div className="section-title-row compact"><div><p className="section-kicker">FUNNEL</p><h2>상품별 클릭 → 주문 퍼널</h2><p>두 데이터 원천이 모두 연결되면 활성화됩니다.</p></div><span className="disabled-label"><Icon name="link" size={15}/>연결 대기</span></div>
        <div className="empty-chart" aria-label="성과 차트 연결 대기"><div className="chart-placeholder-bars" aria-hidden="true"><i/><i/><i/><i/><i/><i/></div><Icon name="chart" size={25}/><strong>표시할 실제 데이터가 아직 없습니다.</strong><p>GA4 클릭과 쿠팡 주문을 상품 번호 기준으로 연결해 전환율을 계산합니다.</p></div>
      </section>

      <section className="section-block">
        <div className="section-title-row compact"><div><p className="section-kicker">PRODUCT READINESS</p><h2>분석 준비 상태</h2></div></div>
        <div className="readiness-list">
          {products.length ? products.map((product) => <article key={product.id}><span className="readiness-number">{String(product.id).padStart(3, "0")}</span><div><strong>{product.title}</strong><p>{product.partnersLink ? "파트너스 링크 연결됨" : "파트너스 링크 미등록"}</p></div><StatusBadge status={product.partnersLink ? "connected" : "waiting"} label={product.partnersLink ? "링크 준비" : "링크 필요"}/><span className="readiness-metric">성과 연결 대기</span></article>) : <div className="empty-state"><strong>등록된 상품이 없습니다.</strong></div>}
        </div>
      </section>
    </div>
  );
}
