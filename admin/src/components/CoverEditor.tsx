import { useEffect, useMemo, useState } from "react";
import type { AdminAsset } from "../types/admin";
import { Icon } from "./Icon";
import { StatusBadge } from "./StatusBadge";

export type CoverGenerateInput = { frame?: number; line1?: string; line2?: string };

function frameNumber(asset: AdminAsset): number {
  const value = asset.metadata.frame;
  return typeof value === "number" ? value : Number(value || 0);
}

function metadataText(asset: AdminAsset | undefined, key: string): string {
  const value = asset?.metadata[key];
  return typeof value === "string" ? value : "";
}

function metadataNumber(asset: AdminAsset | undefined, key: string): number {
  const value = asset?.metadata[key];
  return typeof value === "number" ? value : Number(value || 0);
}

export function CoverEditor({
  productId,
  assets,
  workerOnline,
  live,
  busy,
  onGenerate,
}: {
  productId: number;
  assets: AdminAsset[];
  workerOnline: boolean;
  live: boolean;
  busy: boolean;
  onGenerate: (input: CoverGenerateInput) => void;
}) {
  const candidates = useMemo(
    () => assets.filter((asset) => asset.kind === "cover_candidate").sort((a, b) => frameNumber(a) - frameNumber(b)),
    [assets],
  );
  const finalCover = assets.find((asset) => asset.kind === "reel_cover");
  const recommended = candidates.find((asset) => asset.metadata.recommended === true);
  const initialFrame = metadataNumber(finalCover, "selectedFrame") || (recommended ? frameNumber(recommended) : frameNumber(candidates[0]));
  const initialLine1 = metadataText(finalCover, "line1");
  const initialLine2 = metadataText(finalCover, "line2");
  const [selectedFrame, setSelectedFrame] = useState(initialFrame);
  const [line1, setLine1] = useState(initialLine1);
  const [line2, setLine2] = useState(initialLine2);

  useEffect(() => {
    setSelectedFrame(initialFrame);
    setLine1(initialLine1);
    setLine2(initialLine2);
  }, [productId, finalCover?.id, initialFrame, initialLine1, initialLine2]);

  const selectedCandidate = candidates.find((asset) => frameNumber(asset) === selectedFrame) || recommended || candidates[0];
  const canGenerate = live && workerOnline && !busy;
  const editReady = candidates.length > 0 && Boolean(line1.trim() && line2.trim());
  const disabledReason = !live
    ? "Supabase 연결 후 사용할 수 있습니다"
    : !workerOnline
      ? "로컬 Worker를 먼저 실행하세요"
      : busy
        ? "커버 생성 작업을 요청하는 중입니다"
        : "";

  return (
    <section className="cover-editor" aria-labelledby={`cover-editor-${productId}`}>
      <div className="drawer-section-title cover-editor-title">
        <div><h3 id={`cover-editor-${productId}`}>릴스 커버</h3><p>한 장면과 두 줄 훅으로 계정의 인상을 통일합니다.</p></div>
        {finalCover ? <StatusBadge status="connected" label="커버 생성됨"/> : <StatusBadge status="waiting" label="생성 전"/>}
      </div>

      {!candidates.length ? (
        <div className="cover-empty">
          <span><Icon name="box" size={21}/></span>
          <strong>아직 커버 후보가 없습니다.</strong>
          <p>Worker가 여섯 프레임을 분석하고 첫 두 문장으로 기본 커버를 만듭니다.</p>
          <button type="button" className="secondary-button" onClick={() => onGenerate({})} disabled={!canGenerate} title={disabledReason || "자동 추천으로 커버 생성"}>
            <Icon name="plus" size={16}/>{busy ? "요청 중…" : "자동 커버 생성"}
          </button>
        </div>
      ) : (
        <div className="cover-editor-body">
          <div className="cover-candidate-panel">
            <span className="cover-field-label">배경 장면</span>
            <div className="cover-candidates" role="radiogroup" aria-label="커버 배경 프레임">
              {candidates.map((asset) => {
                const frame = frameNumber(asset);
                const isRecommended = asset.metadata.recommended === true;
                return <button type="button" role="radio" aria-checked={selectedFrame === frame} className={selectedFrame === frame ? "selected" : ""} onClick={() => setSelectedFrame(frame)} key={asset.id}>
                  {asset.signedUrl ? <img src={asset.signedUrl} alt={`${frame}번 커버 후보`}/> : <span className="cover-image-missing"><Icon name="box" size={18}/></span>}
                  <small>{frame}번</small>
                  {isRecommended ? <em>추천</em> : null}
                </button>;
              })}
            </div>
            <label className="cover-copy-field" htmlFor={`cover-line1-${productId}`}><span>첫 번째 줄 <b>{line1.length}/60</b></span><input id={`cover-line1-${productId}`} maxLength={60} value={line1} onChange={(event) => setLine1(event.target.value)} placeholder="예: 열쇠고리인 줄 알았죠?"/></label>
            <label className="cover-copy-field" htmlFor={`cover-line2-${productId}`}><span>두 번째 줄 <b>{line2.length}/60</b></span><input id={`cover-line2-${productId}`} maxLength={60} value={line2} onChange={(event) => setLine2(event.target.value)} placeholder="예: 진짜 찍히는 카메라예요."/></label>
          </div>

          <div className="cover-preview-panel">
            <span className="cover-field-label">미리보기</span>
            <div className="cover-live-preview" style={selectedCandidate?.signedUrl ? { backgroundImage: `url(${selectedCandidate.signedUrl})` } : undefined}>
              {!selectedCandidate?.signedUrl ? <Icon name="box" size={25}/> : null}
              <div className="cover-preview-gradient" aria-hidden="true"/>
              <div className="cover-preview-copy"><strong>{line1 || "첫 번째 훅 문구"}</strong><b>{line2 || "두 번째 훅 문구"}</b></div>
            </div>
            {finalCover?.signedUrl ? <a className="cover-final-link" href={finalCover.signedUrl} target="_blank" rel="noreferrer">최종 JPG 열기 <Icon name="external" size={14}/></a> : null}
          </div>

          <div className="cover-editor-actions">
            <p>{disabledReason || (editReady ? "선택한 장면과 문구로 새 커버를 생성합니다." : "문구 두 줄을 입력하세요.")}</p>
            <button type="button" className="primary-button" onClick={() => onGenerate({ frame: selectedFrame, line1, line2 })} disabled={!canGenerate || !editReady} title={disabledReason || "선택 내용으로 커버 생성"}>
              <Icon name="refresh" size={16}/>{busy ? "요청 중…" : "커버 생성"}
            </button>
          </div>
        </div>
      )}
    </section>
  );
}
