import assert from "node:assert/strict";
import test from "node:test";
import { getPublishButtonState } from "../src/lib/publishState.ts";

function state(overrides: Record<string, unknown> = {}) {
  return getPublishButtonState({
    stage: "caption_ready",
    reelUrl: null,
    jobs: [],
    workerOnline: false,
    busy: false,
    ...overrides,
  });
}

test("caption-ready product can be approved before Cloud Worker starts", () => {
  const result = state();

  assert.equal(result.kind, "ready");
  assert.equal(result.disabled, false);
  assert.equal(result.label, "릴스 게시 승인");
  assert.match(result.hint, /대기열/);
});

test("queued publish waits for Cloud Run dispatch", () => {
  const result = state({
    jobs: [{ type: "publish_reel", status: "queued" }],
  });

  assert.equal(result.kind, "queued");
  assert.equal(result.disabled, true);
  assert.equal(result.label, "게시 대기 · Cloud 실행 준비");
  assert.match(result.hint, /Cloud Run/);
});

test("claimed and running publish jobs show publishing state", () => {
  for (const status of ["claimed", "running"]) {
    const result = state({
      workerOnline: true,
      jobs: [{ type: "publish_reel", status }],
    });
    assert.equal(result.kind, "running");
    assert.equal(result.disabled, true);
    assert.equal(result.label, "게시 중");
  }
});

test("published product cannot create another publish job", () => {
  for (const overrides of [
    { reelUrl: "https://www.instagram.com/reel/example/" },
    { stage: "published" },
    { stage: "linked" },
  ]) {
    const result = state(overrides);
    assert.equal(result.kind, "published");
    assert.equal(result.disabled, true);
    assert.equal(result.label, "게시 완료");
  }
});

test("product before caption-ready stays blocked", () => {
  const result = state({ stage: "audio_ready" });

  assert.equal(result.kind, "blocked");
  assert.equal(result.disabled, true);
  assert.equal(result.label, "캡션 완성 후 게시 가능");
});

test("failed or cancelled jobs do not block a fresh approval", () => {
  const result = state({
    jobs: [
      { type: "publish_reel", status: "failed" },
      { type: "publish_reel", status: "cancelled" },
    ],
  });

  assert.equal(result.kind, "ready");
  assert.equal(result.disabled, false);
});

test("submitting approval has its own busy copy", () => {
  const result = state({ busy: true });

  assert.equal(result.kind, "busy");
  assert.equal(result.disabled, true);
  assert.equal(result.label, "승인 처리 중…");
});
