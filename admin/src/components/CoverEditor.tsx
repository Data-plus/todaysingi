import { useEffect, useMemo, useState } from "react";
import { findActiveCoverJob, getCoverDraft, isCoverDraftDirty } from "../lib/coverState";
import type { AdminAsset, AdminJob } from "../types/admin";
import { Icon } from "./Icon";
import { StatusBadge } from "./StatusBadge";

export type CoverGenerateInput = { frame?: number; line1?: string; line2?: string };

function frameNumber(asset: AdminAsset): number {
  const value = asset.metadata.frame;
  return typeof value === "number" ? value : Number(value || 0);
}

export function CoverEditor({
  productId,
  assets,
  jobs,
  workerOnline,
  live,
  busy,
  onGenerate,
}: {
  productId: number;
  assets: AdminAsset[];
  jobs: AdminJob[];
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
  const pendingJob = findActiveCoverJob(jobs);
  const initialDraft = getCoverDraft(
    finalCover,
    jobs,
    recommended ? frameNumber(recommended) : 0,
    candidates[0] ? frameNumber(candidates[0]) : 0,
  );
  const [selectedFrame, setSelectedFrame] = useState(initialDraft.frame);
  const [line1, setLine1] = useState(initialDraft.line1);
  const [line2, setLine2] = useState(initialDraft.line2);

  useEffect(() => {
    setSelectedFrame(initialDraft.frame);
    setLine1(initialDraft.line1);
    setLine2(initialDraft.line2);
  }, [
    productId,
    finalCover?.id,
    finalCover?.metadata.selectedFrame,
    finalCover?.metadata.line1,
    finalCover?.metadata.line2,
    pendingJob?.id,
    initialDraft.frame,
    initialDraft.line1,
    initialDraft.line2,
  ]);

  const selectedCandidate = candidates.find((asset) => frameNumber(asset) === selectedFrame) || recommended || candidates[0];
  const dirty = isCoverDraftDirty({ frame: selectedFrame, line1, line2 }, finalCover);
  const editReady = candidates.length > 0 && Boolean(line1.trim() && line2.trim());
  const canGenerate = live && !busy && !pendingJob && editReady && dirty;
  const canAutoGenerate = live && !busy && !pendingJob;
  const stateLabel = pendingJob?.status === "queued"
    ? "적용 대기"
    : pendingJob
      ? "적용 중"
      : dirty
        ? "저장되지 않은 변경"
        : "커버 적용됨";
  const helper = !live
    ? "Supabase 연결 후 사용할 수 있습니다"
    : pendingJob?.status === "queued"
      ? "선택한 커버가 대기열에 저장되었습니다."
      : pendingJob
        ? "Worker가 선택한 커버를 적용 중입니다."
        : busy
          ? "커버 적용 요청을 저장하는 중입니다."
          : !dirty
            ? "현재 최종 커버와 같습니다."
            : workerOnline
              ? "선택한 장면과 문구를 적용합니다."
              : "Worker가 켜지면 적용하도록 대기열에 저장합니다.";
  const actionLabel = pendingJob?.status === "queued"
    ? "적용 대기"
    : pendingJob
      ? "적용 중"
      : dirty
        ? "선택 커버 적용"
        : "적용됨";

  return (
    <section className="cover-editor" aria-labelledby={`cover-editor-${productId}`}>
      <div className="drawer-section-title cover-editor-title">
        <div><h3 id={`cover-editor-${productId}`}>릴스 커버</h3><p>한 장면과 두 줄 훅으로 계정의 인상을 통일합니다.</p></div>
        <StatusBadge status={pendingJob?.status || (dirty ? "waiting" : "connected")} label={stateLabel}/>
      </div>

      {!candidates.length ? (
        <div className="cover-empty">
          <span><Icon name="box" size={21}/></span>
          <strong>아직 커버 후보가 없습니다.</strong>
          <p>Worker가 여섯 프레임을 분석하고 첫 두 문장으로 기본 커버를 만듭니다.</p>
          <button type="button" className="secondary-button" onClick={() => onGenerate({})} disabled={!canAutoGenerate} title={!live ? "Supabase 연결 후 사용할 수 있습니다" : "자동 추천으로 커버 생성"}>
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
            <p>{helper}</p>
            <button type="button" className="primary-button" onClick={() => onGenerate({ frame: selectedFrame, line1, line2 })} disabled={!canGenerate} title={helper}>
              <Icon name="refresh" size={16}/>{actionLabel}
            </button>
          </div>
        </div>
      )}
    </section>
  );
}
