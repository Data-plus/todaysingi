type CoverJobLike = {
  id: string;
  type: string;
  status: string;
  payload: Record<string, unknown>;
  createdAt: string;
};

type CoverAssetLike = { metadata: Record<string, unknown> } | undefined;

export type CoverDraft = {
  frame: number;
  line1: string;
  line2: string;
  pendingStatus?: "queued" | "claimed" | "running" | null;
};

const ACTIVE = new Set(["queued", "claimed", "running"]);

function numberValue(value: unknown): number {
  const number = typeof value === "number" ? value : Number(value || 0);
  return Number.isFinite(number) && number > 0 ? number : 0;
}

function textValue(value: unknown): string {
  return typeof value === "string" ? value : "";
}

export function findActiveCoverJob<T extends CoverJobLike>(jobs: T[]): T | undefined {
  return [...jobs]
    .filter((job) => job.type === "generate_cover" && ACTIVE.has(job.status))
    .sort((a, b) => Date.parse(b.createdAt) - Date.parse(a.createdAt))[0];
}

export function getCoverDraft(finalCover: CoverAssetLike, jobs: CoverJobLike[], recommendedFrame: number, firstFrame: number): CoverDraft {
  const pending = findActiveCoverJob(jobs);
  const source = pending?.payload || finalCover?.metadata || {};
  return {
    frame: numberValue(source.frame ?? source.selectedFrame) || recommendedFrame || firstFrame,
    line1: textValue(source.line1 ?? finalCover?.metadata.line1),
    line2: textValue(source.line2 ?? finalCover?.metadata.line2),
    pendingStatus: pending ? pending.status as CoverDraft["pendingStatus"] : null,
  };
}

export function isCoverDraftDirty(draft: Pick<CoverDraft, "frame" | "line1" | "line2">, finalCover: CoverAssetLike): boolean {
  if (!finalCover) return true;
  return draft.frame !== numberValue(finalCover.metadata.selectedFrame)
    || draft.line1.trim() !== textValue(finalCover.metadata.line1).trim()
    || draft.line2.trim() !== textValue(finalCover.metadata.line2).trim();
}
