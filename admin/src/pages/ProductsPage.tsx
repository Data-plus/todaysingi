import { useMemo, useState } from "react";
import { StatusBadge } from "../components/StatusBadge";
import { conversionRate, formatCurrency, formatDateTime, formatNumber, formatPercent, STAGE_LABELS } from "../lib/dashboard";
import type { AdminProduct, ProductStage } from "../types/admin";
import { Icon } from "../components/Icon";

export function ProductsPage({ products, search, onSelectProduct }: { products: AdminProduct[]; search: string; onSelectProduct: (product: AdminProduct) => void }) {
  const [stage, setStage] = useState<"all" | ProductStage>("all");
  const [activity, setActivity] = useState<"all" | "active" | "inactive">("all");
  const filtered = useMemo(() => products.filter((product) => {
    const matchesSearch = product.title.toLocaleLowerCase("ko-KR").includes(search.toLocaleLowerCase("ko-KR")) || String(product.id).includes(search);
    const matchesStage = stage === "all" || product.stage === stage;
    const matchesActivity = activity === "all" || (activity === "active" ? product.active : !product.active);
    return matchesSearch && matchesStage && matchesActivity;
  }), [activity, products, search, stage]);

  return (
    <div className="page-stack">
      <section className="filter-bar" aria-label="상품 필터">
        <div><strong>{filtered.length}</strong><span>개 상품</span></div>
        <label><span>콘텐츠 단계</span><select value={stage} onChange={(event) => setStage(event.target.value as "all" | ProductStage)}><option value="all">전체 단계</option>{Object.entries(STAGE_LABELS).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
        <label><span>운영 상태</span><select value={activity} onChange={(event) => setActivity(event.target.value as typeof activity)}><option value="all">전체 상태</option><option value="active">활성</option><option value="inactive">비활성</option></select></label>
        {search ? <p className="filter-result">“{search}” 검색 결과</p> : null}
      </section>

      <section className="section-block no-gap">
        <div className="table-card products-table-card">
          <table className="data-table products-table">
            <thead><tr><th>상품</th><th>단계</th><th>판매가</th><th>파트너스 링크</th><th>클릭</th><th>주문</th><th>전환율</th><th>매출</th><th>광고비</th><th>ROAS</th><th>상태</th><th aria-label="상세"/></tr></thead>
            <tbody>
              {filtered.length ? filtered.map((product) => (
                <tr key={product.id}>
                  <td data-label="상품"><button type="button" className="product-identity" onClick={() => onSelectProduct(product)}>{product.imageUrl ? <img src={product.imageUrl} alt="" loading="lazy"/> : <span className="product-placeholder">{String(product.id).padStart(3, "0")}</span>}<span><small>NO. {String(product.id).padStart(3, "0")}</small><strong>{product.title}</strong><em>{formatDateTime(product.updatedAt)} 수정</em></span></button></td>
                  <td data-label="단계"><StatusBadge status={product.stage} label={product.stageLabel}/></td>
                  <td data-label="판매가">{formatCurrency(product.price)}</td>
                  <td data-label="파트너스 링크">{product.partnersLink ? <span className="link-ready"><Icon name="check" size={14}/>연결됨</span> : <span className="link-missing">미등록</span>}</td>
                  <td data-label="클릭" className="pending-cell">{formatNumber(product.metrics.linkClicks)}</td>
                  <td data-label="주문" className="pending-cell">{formatNumber(product.metrics.orders)}</td>
                  <td data-label="전환율" className="pending-cell">{formatPercent(conversionRate(product.metrics))}</td>
                  <td data-label="매출" className="pending-cell">{formatCurrency(product.metrics.revenue)}</td>
                  <td data-label="광고비" className="pending-cell">{formatCurrency(product.metrics.adSpend)}</td>
                  <td data-label="ROAS" className="pending-cell">{formatPercent(product.metrics.roas)}</td>
                  <td data-label="상태"><StatusBadge status={product.active ? "connected" : "waiting"} label={product.active ? "활성" : "비활성"}/></td>
                  <td><button type="button" className="icon-button row-open-button" aria-label={`${product.title} 상세 열기`} onClick={() => onSelectProduct(product)}><Icon name="chevron" size={17}/></button></td>
                </tr>
              )) : <tr><td colSpan={12}><div className="empty-state"><Icon name="search" size={24}/><strong>조건에 맞는 상품이 없습니다.</strong><p>검색어나 필터를 바꿔보세요.</p></div></td></tr>}
            </tbody>
          </table>
        </div>
        <p className="table-footnote"><Icon name="link" size={14}/> 클릭·주문·매출·광고 지표는 외부 API 연결 전까지 `—`로 표시됩니다.</p>
      </section>
    </div>
  );
}
