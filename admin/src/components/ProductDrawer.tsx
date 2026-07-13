import { useEffect, useState } from "react";
import { Icon } from "./Icon";
import { StatusBadge } from "./StatusBadge";
import { conversionRate, formatCurrency, formatDateTime, formatNumber, formatPercent } from "../lib/dashboard";
import type { AdminAsset, AdminJob, AdminProduct } from "../types/admin";
import { CoverEditor, type CoverGenerateInput } from "./CoverEditor";
import { PublishApprovalDialog } from "./PublishApprovalDialog";
import { getPublishButtonState } from "../lib/publishState";

function ExternalLink({ href, label }: { href: string | null; label: string }) {
  return href ? <a href={href} target="_blank" rel="noreferrer">{label}<Icon name="external" size={14}/></a> : <span className="missing-link">{label} 미등록</span>;
}

export function ProductDrawer({ product, jobs, assets, busy, coverBusy, publishBusy, workerOnline, live, onClose, onDub, onGenerateCover, onPublish }: { product: AdminProduct; jobs: AdminJob[]; assets: AdminAsset[]; busy: boolean; coverBusy: boolean; publishBusy: boolean; workerOnline: boolean; live: boolean; onClose: () => void; onDub: () => void; onGenerateCover: (input: CoverGenerateInput) => void; onPublish: () => Promise<boolean> }) {
  const [publishOpen, setPublishOpen] = useState(false);
  const publishState = getPublishButtonState({
    stage: product.stage,
    reelUrl: product.reelUrl,
    jobs,
    workerOnline,
    busy: publishBusy,
  });

  useEffect(() => {
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    function closeOnEscape(event: KeyboardEvent) {
      if (event.key === "Escape" && !publishOpen) onClose();
    }
    window.addEventListener("keydown", closeOnEscape);
    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener("keydown", closeOnEscape);
    };
  }, [onClose, publishOpen]);

  useEffect(() => setPublishOpen(false), [product.id]);

  return (
    <>
      <div className="drawer-backdrop" onMouseDown={onClose}>
        <section className="product-drawer" role="dialog" aria-modal="true" aria-labelledby="product-drawer-title" onMouseDown={(event) => event.stopPropagation()}>
        <header className="drawer-header"><div><p>PRODUCT · {String(product.id).padStart(3, "0")}</p><h2 id="product-drawer-title">{product.title}</h2></div><button type="button" className="icon-button" aria-label="상품 상세 닫기" onClick={onClose}><Icon name="close" size={20}/></button></header>
        <div className="drawer-scroll">
          <section className="drawer-summary">
            <div className="drawer-product-visual">{product.imageUrl ? <img src={product.imageUrl} alt={`${product.title} 상품`}/> : <span>{String(product.id).padStart(3, "0")}</span>}</div>
            <div><StatusBadge status={product.stage} label={product.stageLabel}/><dl><div><dt>판매가</dt><dd>{formatCurrency(product.price)}</dd></div><div><dt>업데이트</dt><dd>{formatDateTime(product.updatedAt)}</dd></div><div><dt>운영 상태</dt><dd>{product.active ? "활성" : "비활성"}</dd></div></dl></div>
          </section>

          <section className="drawer-section"><div className="drawer-section-title"><h3>상품 링크</h3></div><div className="link-list"><ExternalLink href={product.coupangUrl} label="쿠팡 원본"/><ExternalLink href={product.aliUrl} label="AliExpress"/><ExternalLink href={product.partnersLink} label="파트너스 링크"/><ExternalLink href={product.reelUrl} label="Instagram 릴스"/></div></section>

          <section className="drawer-section"><div className="drawer-section-title"><h3>상품 성과</h3><span>외부 API 연결 전</span></div><div className="drawer-metrics"><div><span>클릭</span><strong>{formatNumber(product.metrics.linkClicks)}</strong></div><div><span>주문</span><strong>{formatNumber(product.metrics.orders)}</strong></div><div><span>전환율</span><strong>{formatPercent(conversionRate(product.metrics))}</strong></div><div><span>매출</span><strong>{formatCurrency(product.metrics.revenue)}</strong></div><div><span>광고비</span><strong>{formatCurrency(product.metrics.adSpend)}</strong></div><div><span>ROAS</span><strong>{formatPercent(product.metrics.roas)}</strong></div></div><p className="drawer-help"><Icon name="link" size={14}/>성과 데이터 연결 후 실제 값으로 바뀝니다.</p></section>

          <CoverEditor productId={product.id} assets={assets} workerOnline={workerOnline} live={live} busy={coverBusy} onGenerate={onGenerateCover}/>

          <section className="drawer-section"><div className="drawer-section-title"><h3>콘텐츠 자산</h3><span>{assets.length}개</span></div>{assets.length ? <div className="asset-list">{assets.map((asset) => <article key={asset.id}><span className="asset-icon"><Icon name={asset.kind === "final_video" ? "play" : "box"} size={17}/></span><div><strong>{asset.kind === "final_video" ? "완성 영상" : "썸네일"}</strong><p>{asset.mimeType} · {asset.bytes ? `${Math.round(asset.bytes / 1024 / 1024)}MB` : "크기 미기록"}</p></div><StatusBadge status={asset.reviewStatus === "approved" ? "connected" : "waiting"} label={asset.reviewStatus === "approved" ? "승인" : "검수 대기"}/></article>)}</div> : <div className="inline-empty">등록된 완성 자산이 없습니다.</div>}</section>

          <section className="drawer-section"><div className="drawer-section-title"><h3>관련 작업</h3><span>{jobs.length}개</span></div>{jobs.length ? <div className="drawer-job-list">{jobs.slice(0, 6).map((job) => <article key={job.id}><div><small>{job.displayId}</small><strong>{job.typeLabel}</strong></div><StatusBadge status={job.status} label={job.statusLabel}/><time>{formatDateTime(job.updatedAt)}</time></article>)}</div> : <div className="inline-empty">이 상품의 작업 기록이 없습니다.</div>}</section>

          {product.note ? <section className="drawer-section"><div className="drawer-section-title"><h3>운영 메모</h3></div><p className="product-note">{product.note}</p></section> : null}
        </div>
          <footer className="drawer-footer"><button type="button" className="secondary-button" onClick={onDub} disabled={busy || !live} title={live ? "Typecast 재더빙 작업 요청" : "Supabase 연결 후 사용할 수 있습니다"}><Icon name="rotate" size={16}/>{busy ? "요청 중…" : "Typecast 재더빙"}</button><button type="button" className={`primary-button publish-action-button publish-action-${publishState.kind}`} disabled={!live || publishState.disabled} title={live ? publishState.hint : "Supabase 연결 후 사용할 수 있습니다"} aria-label={publishState.label} onClick={() => setPublishOpen(true)}><Icon name={publishState.kind === "published" ? "check" : "send"} size={16}/>{publishState.label}</button></footer>
        </section>
      </div>
      <PublishApprovalDialog open={publishOpen} product={product} assets={assets} workerOnline={workerOnline} busy={publishBusy} onClose={() => setPublishOpen(false)} onConfirm={onPublish}/>
    </>
  );
}
