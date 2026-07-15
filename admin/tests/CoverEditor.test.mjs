import assert from "node:assert/strict";
import { after, before, test } from "node:test";
import { fileURLToPath } from "node:url";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { createServer } from "vite";

const adminRoot = fileURLToPath(new URL("..", import.meta.url));

let CoverEditor;
let vite;

before(async () => {
  vite = await createServer({
    root: adminRoot,
    configFile: false,
    optimizeDeps: { noDiscovery: true },
    server: { middlewareMode: true, hmr: false },
    appType: "custom",
    logLevel: "error",
  });
  ({ CoverEditor } = await vite.ssrLoadModule("/src/components/CoverEditor.tsx"));
});

after(async () => {
  await vite?.close();
});

function renderEditor(assets) {
  return renderToStaticMarkup(createElement(CoverEditor, {
    productId: 1,
    assets,
    jobs: [],
    workerOnline: false,
    live: true,
    busy: false,
    onGenerate() {},
  }));
}

function assertAutoGenerateEnabled(markup) {
  const button = markup.match(/<button\b([^>]*)>[^]*?자동 커버 생성<\/button>/);
  assert.ok(button, "자동 커버 생성 버튼이 렌더링되어야 합니다");
  assert.doesNotMatch(button[1], /\bdisabled(?:=|$)/, "Worker가 오프라인이어도 버튼이 활성화되어야 합니다");
}

test("후보가 없으면 오프라인에서도 자동 커버 생성 버튼을 활성화한다", () => {
  assertAutoGenerateEnabled(renderEditor([]));
});

test("최종 커버만 있어도 자동 커버 생성 빈 상태를 렌더링한다", () => {
  const finalCover = {
    id: "cover-final",
    productId: 1,
    jobId: null,
    kind: "reel_cover",
    storagePath: "products/1/cover.jpg",
    mimeType: "image/jpeg",
    bytes: 1024,
    durationSeconds: null,
    reviewStatus: "approved",
    metadata: { selectedFrame: 6, line1: "첫 줄", line2: "둘째 줄" },
    signedUrl: "https://example.test/cover.jpg",
    createdAt: "2026-07-14T00:00:00.000Z",
  };

  assertAutoGenerateEnabled(renderEditor([finalCover]));
});
