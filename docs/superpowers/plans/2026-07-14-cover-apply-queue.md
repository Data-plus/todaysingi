# 관리자 릴스 커버 적용 대기열 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 커버 후보 선택을 명시적으로 대기열에 저장하고, 적용 완료 전 Instagram 게시를 UI와 DB 양쪽에서 차단한다.

**Architecture:** 커버 편집의 최종값·임시값·활성 작업값 계산을 순수 TypeScript 모듈로 분리한다. 관리자 UI는 Worker 온라인 여부와 무관하게 `generate_cover` 작업을 만들며, Worker 완료 후 기존 자산 동기화 경로가 최종 JPG와 게시 영상을 갱신한다. 게시 버튼과 Supabase 승인 RPC는 활성 커버 작업을 같은 기준으로 차단한다.

**Tech Stack:** React 19, TypeScript 5.8, Supabase Postgres/RLS/RPC, Python pytest, Node 내장 test runner, Vite, Netlify

## Global Constraints

- 후보 클릭은 미리보기만 바꾸고 `선택 커버 적용`을 눌렀을 때만 작업을 만든다.
- Worker가 오프라인이어도 Supabase 대기열 저장을 허용한다.
- 활성 커버 작업 상태는 `queued`, `claimed`, `running` 세 가지다.
- 활성 커버 작업이 끝날 때까지 추가 커버 적용과 Instagram 게시 승인을 막는다.
- 실패·취소·완료된 커버 작업은 게시를 막지 않는다.
- 브라우저에서 JPG 또는 MP4를 렌더링하지 않고 기존 로컬 `make_cover.py`를 재사용한다.
- Instagram 게시 승인은 자동으로 실행하지 않는다.
- 비밀키와 로컬 운영 자산을 커밋하지 않는다.

---

## File Structure

- Create `admin/src/lib/coverState.ts`: 최종 커버와 활성 작업에서 편집 기준값·대기 상태·변경 여부를 계산하는 순수 함수.
- Create `admin/tests/coverState.test.ts`: 커버 상태 계산의 Node 단위 테스트.
- Modify `admin/package.json`: 새 단위 테스트를 기본 관리자 테스트 명령에 포함.
- Modify `admin/src/components/CoverEditor.tsx`: 미저장·대기·처리·적용 완료 상태와 오프라인 대기열 버튼 구현.
- Modify `admin/src/components/ProductDrawer.tsx`: 상품의 관련 작업을 `CoverEditor`에 전달하고 게시 상태와 같은 작업 집합을 사용.
- Modify `admin/src/lib/publishState.ts`: 활성 커버 작업 중 게시 버튼 차단.
- Modify `admin/tests/publishState.test.ts`: 커버 대기·실행·종료 상태별 게시 버튼 회귀 테스트.
- Modify `admin/src/lib/controlDesk.ts`: DB 커버 경합 오류를 관리자용 문구로 변환.
- Create `supabase/migrations/202607140001_cover_apply_publish_guard.sql`: 게시 승인 RPC에 활성 커버 작업 검사 추가.
- Create `tests/test_cover_apply_publish_guard.py`: 새 SQL 안전장치 계약 테스트.
- Modify `tests/test_admin_dashboard.py`: 오프라인 적용 버튼과 UI 문구의 소스 계약 테스트.

---

### Task 1: 커버 편집 상태를 순수 로직으로 분리

**Files:**
- Create: `admin/src/lib/coverState.ts`
- Create: `admin/tests/coverState.test.ts`
- Modify: `admin/package.json`

**Interfaces:**
- Consumes: `AdminAsset.metadata`, `AdminJob.type`, `AdminJob.status`, `AdminJob.payload`, `AdminJob.createdAt`.
- Produces: `findActiveCoverJob(jobs)`, `getCoverDraft(finalCover, jobs, recommendedFrame, firstFrame)`, `isCoverDraftDirty(draft, finalCover)`.

- [ ] **Step 1: Write the failing cover-state tests**

Create `admin/tests/coverState.test.ts` with real inputs that prove active job precedence and terminal-state exclusion:

```ts
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
```

Add `tests/coverState.test.ts` to `admin/package.json`'s `test` script.

- [ ] **Step 2: Run the tests and verify RED**

Run: `npm --prefix admin test`

Expected: FAIL because `admin/src/lib/coverState.ts` does not exist.

- [ ] **Step 3: Implement the minimal state module**

Create `admin/src/lib/coverState.ts` with structural input types so tests do not need full dashboard objects:

```ts
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
```

- [ ] **Step 4: Run the tests and verify GREEN**

Run: `npm --prefix admin test`

Expected: all administrator Node tests PASS.

- [ ] **Step 5: Commit the state module**

```bash
git add admin/package.json admin/src/lib/coverState.ts admin/tests/coverState.test.ts
git commit -m "feat: 커버 적용 상태 계산 추가"
```

---

### Task 2: Worker 오프라인 커버 적용 UX

**Files:**
- Modify: `admin/src/components/CoverEditor.tsx`
- Modify: `admin/src/components/ProductDrawer.tsx`
- Modify: `tests/test_admin_dashboard.py`

**Interfaces:**
- Consumes: Task 1의 `getCoverDraft`, `findActiveCoverJob`, `isCoverDraftDirty`; `ProductDrawer.jobs`.
- Produces: Worker 오프라인에서도 호출되는 `onGenerate({ frame, line1, line2 })`와 명확한 미저장·대기 UI.

- [ ] **Step 1: Add a failing source-contract test**

Append to `tests/test_admin_dashboard.py`:

```python
def test_cover_editor_can_queue_offline_and_marks_unsaved_changes():
    editor = source("admin/src/components/CoverEditor.tsx")
    drawer = source("admin/src/components/ProductDrawer.tsx")

    assert "선택 커버 적용" in editor
    assert "저장되지 않은 변경" in editor
    assert "Worker가 켜지면 적용하도록 대기열에 저장합니다" in editor
    assert "live && workerOnline" not in editor
    assert "jobs={jobs}" in drawer
```

- [ ] **Step 2: Run the contract test and verify RED**

Run: `python -m pytest tests/test_admin_dashboard.py::test_cover_editor_can_queue_offline_and_marks_unsaved_changes -q`

Expected: FAIL because the new copy and offline behavior are absent.

- [ ] **Step 3: Integrate job-backed editor state**

Change `CoverEditor` to accept `jobs: AdminJob[]`, derive `initialDraft` through `getCoverDraft`, and reset local input when `productId`, final metadata, or the active job ID changes. Compute:

```ts
const pendingJob = findActiveCoverJob(jobs);
const initialDraft = getCoverDraft(finalCover, jobs, recommendedFrame, firstFrame);
const dirty = isCoverDraftDirty({ frame: selectedFrame, line1, line2 }, finalCover);
const editReady = candidates.length > 0 && Boolean(line1.trim() && line2.trim());
const canGenerate = live && !busy && !pendingJob && editReady && dirty;
```

Use these exact states:

```ts
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
```

The action label is `적용 대기`, `적용 중`, `선택 커버 적용`, or `적용됨` according to the same state. For the no-candidate state, remove `workerOnline` from the disabled condition so `자동 커버 생성` can also queue offline.

- [ ] **Step 4: Pass jobs from the drawer**

Change the `ProductDrawer` call to:

```tsx
<CoverEditor
  productId={product.id}
  assets={assets}
  jobs={jobs}
  workerOnline={workerOnline}
  live={live}
  busy={coverBusy}
  onGenerate={onGenerateCover}
/>
```

- [ ] **Step 5: Run focused tests and build**

Run:

```text
python -m pytest tests/test_admin_dashboard.py -q
npm --prefix admin test
npm --prefix admin run build
```

Expected: all commands PASS with no TypeScript errors.

- [ ] **Step 6: Commit the offline UX**

```bash
git add admin/src/components/CoverEditor.tsx admin/src/components/ProductDrawer.tsx tests/test_admin_dashboard.py
git commit -m "fix: 오프라인 커버 적용 대기열 허용"
```

---

### Task 3: 커버 적용 중 게시 안전장치

**Files:**
- Modify: `admin/tests/publishState.test.ts`
- Modify: `admin/src/lib/publishState.ts`
- Modify: `admin/src/lib/controlDesk.ts`
- Create: `tests/test_cover_apply_publish_guard.py`
- Create: `supabase/migrations/202607140001_cover_apply_publish_guard.sql`

**Interfaces:**
- Consumes: `AdminJob`의 type/status, 기존 `approve_publish_reel(bigint)` 계약.
- Produces: 활성 커버 작업을 차단하는 게시 버튼 상태와 DB RPC 오류 `55000`.

- [ ] **Step 1: Add failing client guard tests**

Append to `admin/tests/publishState.test.ts`:

```ts
test("queued cover apply blocks publishing until the Worker finishes", () => {
  const result = state({ jobs: [{ type: "generate_cover", status: "queued" }] });
  assert.equal(result.disabled, true);
  assert.equal(result.label, "커버 적용 후 게시 가능");
});

test("running cover apply shows processing state", () => {
  for (const status of ["claimed", "running"]) {
    const result = state({ jobs: [{ type: "generate_cover", status }] });
    assert.equal(result.disabled, true);
    assert.equal(result.label, "커버 적용 중");
  }
});

test("terminal cover jobs do not block publishing", () => {
  for (const status of ["succeeded", "failed", "cancelled"]) {
    assert.equal(state({ jobs: [{ type: "generate_cover", status }] }).disabled, false);
  }
});
```

- [ ] **Step 2: Run the client tests and verify RED**

Run: `npm --prefix admin test`

Expected: FAIL because `getPublishButtonState` ignores `generate_cover`.

- [ ] **Step 3: Implement the client guard**

After existing active publish-job handling and before the `caption_ready` check, add:

```ts
const activeCover = jobs.find((job) => (
  job.type === "generate_cover"
  && (job.status === "queued" || job.status === "claimed" || job.status === "running")
));

if (activeCover?.status === "claimed" || activeCover?.status === "running") {
  return { kind: "running", disabled: true, label: "커버 적용 중", hint: "Worker가 최종 커버와 게시 영상을 갱신하고 있습니다." };
}
if (activeCover?.status === "queued") {
  return {
    kind: "queued",
    disabled: true,
    label: "커버 적용 후 게시 가능",
    hint: workerOnline ? "커버 적용 작업이 처리 대기 중입니다." : "PC에서 Worker를 켜면 커버를 적용한 뒤 게시할 수 있습니다.",
  };
}
```

- [ ] **Step 4: Write the failing SQL contract test**

Create `tests/test_cover_apply_publish_guard.py`:

```python
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MIGRATION = ROOT / "supabase" / "migrations" / "202607140001_cover_apply_publish_guard.sql"


def sql_source():
    return MIGRATION.read_text(encoding="utf-8").lower()


def test_publish_rpc_rejects_active_cover_jobs():
    sql = sql_source()
    assert "create or replace function public.approve_publish_reel" in sql
    assert "type = 'generate_cover'" in sql
    for status in ("queued", "claimed", "running"):
        assert f"'{status}'" in sql
    assert "errcode = '55000'" in sql
    assert "커버 적용 작업이 완료된 후 게시할 수 있습니다" in sql


def test_publish_rpc_keeps_admin_and_readiness_guards():
    sql = sql_source()
    assert "public.is_todaysingi_admin()" in sql
    assert "product_stage <> 'caption_ready'" in sql
    assert "product_reel_url is not null" in sql
    assert "grant execute on function public.approve_publish_reel(bigint) to authenticated" in sql
```

- [ ] **Step 5: Run the SQL test and verify RED**

Run: `python -m pytest tests/test_cover_apply_publish_guard.py -q`

Expected: FAIL because the migration file does not exist.

- [ ] **Step 6: Add the RPC replacement migration**

Create `supabase/migrations/202607140001_cover_apply_publish_guard.sql` with the complete replacement below:

```sql
-- 커버 적용이 끝나기 전에 Instagram 게시 승인이 앞서지 않도록 보장한다.

create or replace function public.approve_publish_reel(p_product_id bigint)
returns uuid
language plpgsql
security definer
set search_path = ''
as $$
declare
  existing_job_id uuid;
  active_cover_job_id uuid;
  created_job_id uuid;
  product_stage text;
  product_reel_url text;
begin
  if auth.uid() is null or not public.is_todaysingi_admin() then
    raise exception 'Instagram 게시 승인 권한이 없습니다'
      using errcode = '42501';
  end if;

  select stage, reel_url
    into product_stage, product_reel_url
  from public.products
  where id = p_product_id;

  if not found then
    raise exception '상품을 찾을 수 없습니다'
      using errcode = 'P0002';
  end if;

  if product_stage <> 'caption_ready' or product_reel_url is not null then
    raise exception '캡션이 완성되고 아직 게시되지 않은 상품만 승인할 수 있습니다'
      using errcode = '22023';
  end if;

  select id
    into active_cover_job_id
  from public.jobs
  where product_id = p_product_id
    and type = 'generate_cover'
    and status in ('queued', 'claimed', 'running')
  order by created_at desc
  limit 1;

  if active_cover_job_id is not null then
    raise exception '커버 적용 작업이 완료된 후 게시할 수 있습니다'
      using errcode = '55000';
  end if;

  select id
    into existing_job_id
  from public.jobs
  where product_id = p_product_id
    and type = 'publish_reel'
    and status in ('queued', 'claimed', 'running')
  order by created_at desc
  limit 1;

  if existing_job_id is not null then
    return existing_job_id;
  end if;

  begin
    insert into public.jobs (
      product_id,
      type,
      payload,
      idempotency_key,
      priority,
      max_attempts,
      approved_at,
      approved_by
    ) values (
      p_product_id,
      'publish_reel',
      jsonb_build_object('requested_from', 'admin'),
      'publish_reel:' || p_product_id::text || ':' || gen_random_uuid()::text,
      30,
      1,
      now(),
      auth.uid()
    )
    returning id into created_job_id;
  exception
    when unique_violation then
      select id
        into existing_job_id
      from public.jobs
      where product_id = p_product_id
        and type = 'publish_reel'
        and status in ('queued', 'claimed', 'running')
      order by created_at desc
      limit 1;

      if existing_job_id is null then
        raise;
      end if;
      return existing_job_id;
  end;

  insert into public.activity_logs (
    product_id,
    job_id,
    actor,
    action,
    detail
  ) values (
    p_product_id,
    created_job_id,
    'admin',
    'publish_reel_approved',
    jsonb_build_object(
      'approved_by', auth.uid(),
      'requested_from', 'admin'
    )
  );

  return created_job_id;
end;
$$;

revoke all on function public.approve_publish_reel(bigint) from public, anon;
grant execute on function public.approve_publish_reel(bigint) to authenticated;
```

- [ ] **Step 7: Map the race error for the administrator**

In `approvePublishReel`, before the generic throw, add:

```ts
if (error.code === "55000") {
  throw new Error("커버 적용 작업이 끝난 후 게시를 승인할 수 있습니다.");
}
```

- [ ] **Step 8: Run focused tests and verify GREEN**

Run:

```text
npm --prefix admin test
python -m pytest tests/test_cover_apply_publish_guard.py tests/test_admin_publish_approval.py tests/test_admin_dashboard.py -q
```

Expected: all tests PASS.

- [ ] **Step 9: Commit the publication guard**

```bash
git add admin/src/lib/publishState.ts admin/src/lib/controlDesk.ts admin/tests/publishState.test.ts tests/test_cover_apply_publish_guard.py supabase/migrations/202607140001_cover_apply_publish_guard.sql
git commit -m "fix: 커버 적용 중 릴스 게시 차단"
```

---

### Task 4: 전체 검증, Supabase 적용, Netlify 배포

**Files:**
- Verify: all files committed by Tasks 1-3.
- Deploy: `supabase/migrations/202607140001_cover_apply_publish_guard.sql`, built `site/admin/` through Netlify.

**Interfaces:**
- Consumes: completed code and migration from Tasks 1-3.
- Produces: live administrator behavior and a verified migration on project `davyotbbhgnfxpgaglki`.

- [ ] **Step 1: Run the full local verification suite**

Run:

```text
python -m pytest tests/ -q
npm --prefix admin test
npm --prefix admin run build
git diff --check
```

Expected: all tests PASS, Vite build exits 0, and `git diff --check` produces no errors.

- [ ] **Step 2: Inspect scope and secrets**

Run `git status --short` and `git diff --stat HEAD~3..HEAD`. Confirm only planned admin, test, migration, and documentation files are tracked. Search the built output for `SUPABASE_SERVICE_ROLE_KEY`, `INSTAGRAM_ACCESS_TOKEN`, and `TYPECAST_API_KEY`; expected result is no matches.

- [ ] **Step 3: Apply the migration**

Run:

```text
supabase migration list --linked
supabase db push --linked
```

Expected: the linked project is `davyotbbhgnfxpgaglki` and migration `202607140001` is applied once.

- [ ] **Step 4: Verify the remote function contract**

Use a service-role read-only query to confirm no active `generate_cover` job exists for product 004 and its final `reel_cover.metadata.selectedFrame` remains 5. Do not call `approve_publish_reel` during verification.

- [ ] **Step 5: Merge and deploy**

Push the feature branch, merge it into `main`, and push `main`. Netlify should rebuild `site/admin/` automatically. Do not add `ops/pipeline.json`, `.env`, `.venv`, or `ops/assets/` to a commit.

- [ ] **Step 6: Verify the live administrator**

On `https://todaysingi.netlify.app/admin/#overview`:

1. Open product 004 and confirm saved frame 5 remains selected.
2. Select another frame and confirm `저장되지 않은 변경` plus active `선택 커버 적용` while Worker is offline.
3. Do not press the apply button during this smoke test, so no test job is left in production.
4. Confirm `릴스 게시 승인` remains available because there is no active cover job.
5. Confirm existing final JPG link still opens and no Instagram publish job was created.

- [ ] **Step 7: Record completion**

Report test counts, build result, migration status, Netlify deployment URL, and live UI checks. Explicitly state that no Instagram publication was triggered.
