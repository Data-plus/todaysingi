import { useEffect } from "react";
import type { AdminAsset, AdminProduct } from "../types/admin";
import { Icon } from "./Icon";
import { StatusBadge } from "./StatusBadge";

function selectedFrame(asset: AdminAsset | undefined): number | null {
  const value = asset?.metadata.selectedFrame;
  const frame = typeof value === "number" ? value : Number(value || 0);
  return frame > 0 ? frame : null;
}

export function PublishApprovalDialog({
  open,
  product,
  assets,
  workerOnline,
  busy,
  onClose,
  onConfirm,
}: {
  open: boolean;
  product: AdminProduct;
  assets: AdminAsset[];
  workerOnline: boolean;
  busy: boolean;
  onClose: () => void;
  onConfirm: () => Promise<boolean>;
}) {
  useEffect(() => {
    if (!open) return;
    function closeOnEscape(event: KeyboardEvent) {
      if (event.key === "Escape" && !busy) onClose();
    }
    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [busy, onClose, open]);

  if (!open) return null;

  const finalCover = assets.find((asset) => asset.kind === "reel_cover");
  const coverUrl = finalCover?.signedUrl || product.imageUrl;
  const frame = selectedFrame(finalCover);

  async function confirm() {
    const accepted = await onConfirm();
    if (accepted) onClose();
  }

  return (
    <div className="dialog-backdrop publish-approval-backdrop" onMouseDown={() => !busy && onClose()}>
      <section className="publish-approval-dialog" role="dialog" aria-modal="true" aria-labelledby="publish-approval-title" aria-describedby="publish-approval-warning" onMouseDown={(event) => event.stopPropagation()}>
        <header>
          <div><p>FINAL APPROVAL</p><h2 id="publish-approval-title">Instagram에 게시할까요?</h2><span>승인 후에는 Worker가 실제 계정에 릴스를 게시합니다.</span></div>
          <button type="button" className="icon-button" aria-label="게시 승인 창 닫기" onClick={onClose} disabled={busy}><Icon name="close" size={20}/></button>
        </header>

        <div className="publish-approval-product">
          <div className="publish-cover-review">
            {coverUrl ? <img src={coverUrl} alt={`${product.title} 최종 릴스 커버`}/> : <span><Icon name="box" size={28}/></span>}
            {frame ? <small>선택 커버 {frame}번</small> : null}
          </div>
          <div className="publish-product-copy">
            <p>PRODUCT · {String(product.id).padStart(3, "0")}</p>
            <h3>{product.title}</h3>
            <StatusBadge status="waiting" label="최종 승인 대기"/>
            <dl>
              <div><dt>콘텐츠 단계</dt><dd>{product.stageLabel}</dd></div>
              <div><dt>Worker</dt><dd className={workerOnline ? "worker-ready" : "worker-waiting"}>{workerOnline ? "온라인 · 곧 처리" : "오프라인 · 대기열 저장"}</dd></div>
            </dl>
          </div>
        </div>

        <div className="publish-approval-checks" aria-label="게시 승인 확인 사항">
          <article><span><Icon name="check" size={16}/></span><div><strong>최종 커버</strong><p>{finalCover ? "관리자에 저장된 커버를 사용합니다." : "로컬 게시 영상의 커버 설정을 사용합니다."}</p></div></article>
          <article><span><Icon name="check" size={16}/></span><div><strong>캡션 준비</strong><p>caption_ready 단계의 검증된 캡션을 사용합니다.</p></div></article>
          <article><span><Icon name={workerOnline ? "cpu" : "alert"} size={16}/></span><div><strong>{workerOnline ? "Worker 연결됨" : "Worker 대기"}</strong><p>{workerOnline ? "승인 작업을 곧 가져갑니다." : "PC에서 Worker를 켜면 자동으로 게시됩니다."}</p></div></article>
        </div>

        <div className="publish-approval-warning" id="publish-approval-warning"><Icon name="alert" size={18}/><div><strong>이 작업은 실제 Instagram 계정에 공개됩니다.</strong><p>게시 후에는 관리자에서 자동으로 되돌리지 않습니다. 커버와 상품을 한 번 더 확인하세요.</p></div></div>

        <footer>
          <button type="button" className="secondary-button" onClick={onClose} disabled={busy} autoFocus>취소</button>
          <button type="button" className="primary-button publish-confirm-button" onClick={() => void confirm()} disabled={busy}><Icon name="send" size={16}/>{busy ? "승인 처리 중…" : "Instagram 게시 승인"}</button>
        </footer>
      </section>
    </div>
  );
}
