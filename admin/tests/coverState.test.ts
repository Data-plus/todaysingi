import assert from "node:assert/strict";
import test from "node:test";
import { findActiveCoverJob, getCoverDraft, isCoverDraftDirty } from "../src/lib/coverState.ts";

const finalCover = {
  metadata: { selectedFrame: 6, line1: "기존 한 줄", line2: "기존 두 줄" },
};

test("latest active cover job survives refresh as the editor draft", () => {
  const jobs = [
    { id: "old", type: "generate_cover", status: "queued", payload: { frame: 4 }, createdAt: "2026-07-14T10:00:00Z" },
    { id: "new", type: "generate_cover", status: "queued", payload: { frame: 5, line1: "새 한 줄", line2: "새 두 줄" }, createdAt: "2026-07-14T11:00:00Z" },
  ];
  assert.equal(findActiveCoverJob(jobs)?.id, "new");
  assert.deepEqual(getCoverDraft(finalCover, jobs, 6, 1), {
    frame: 5, line1: "새 한 줄", line2: "새 두 줄", pendingStatus: "queued",
  });
});

test("terminal cover jobs do not replace the saved final cover", () => {
  for (const status of ["succeeded", "failed", "cancelled"]) {
    const draft = getCoverDraft(finalCover, [
      { id: status, type: "generate_cover", status, payload: { frame: 5 }, createdAt: "2026-07-14T11:00:00Z" },
    ], 6, 1);
    assert.equal(draft.frame, 6);
    assert.equal(draft.pendingStatus, null);
  }
});

test("draft comparison detects an unsaved frame or copy change", () => {
  assert.equal(isCoverDraftDirty({ frame: 6, line1: "기존 한 줄", line2: "기존 두 줄" }, finalCover), false);
  assert.equal(isCoverDraftDirty({ frame: 5, line1: "기존 한 줄", line2: "기존 두 줄" }, finalCover), true);
});
