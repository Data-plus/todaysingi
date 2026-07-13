# Cloud Run 원격 파이프라인과 GA4 연동 구현 계획

날짜: 2026-07-13  
기준 설계: `docs/plans/2026-07-13-cloud-worker-ga4-design.md`

## 목표

GA4 실제 데이터를 관리자에 표시하는 기능을 먼저 독립 배포한 뒤, 로컬 파일 기반
Worker를 Supabase Storage와 Cloud Run Job 기반 원격 파이프라인으로 단계적으로
전환한다. 모든 코드 변경은 테스트를 먼저 추가하고, 각 단계에서 기존 로컬 Worker의
회귀를 막는다.

## 작업 원칙

- 기능 브랜치와 별도 worktree에서 작업한다.
- 기존 main worktree의 미커밋 `ops/pipeline.json`, Worker, 테스트 변경은 건드리지 않는다.
- DB migration은 additive하게 작성하고 기존 데이터에 안전해야 한다.
- Instagram 게시·Netlify 공개·Cloud 비용 발생 E2E는 dry-run 후 수행한다.
- 실제 `[003]` 릴스는 다시 게시하지 않는다.
- 게시·광고 작업은 자동 재시도하지 않는다.
- 비밀 값은 테스트 fixture, Git, 빌드 산출물, 로그에 넣지 않는다.

## Phase 1: GA4 실제 성과 연결

### 작업 1: GA4 클릭 이벤트 계약

파일:

- 수정 `site/app.js`
- 새 테스트 `tests/test_ga4_tracking.py`

순서:

1. `select_item`, `item_list_id`, `items`, `item_id`, `item_name`을 요구하는 실패 테스트를 쓴다.
2. 기존 `product_click` 전송을 GA4 권장 `select_item` payload로 변경한다.
3. 상품 ID는 세 자리 문자열로 정규화하고 상품명·가격 외 민감 정보는 전송하지 않는다.
4. 사이트 초기화와 링크 이동이 GA 차단기 환경에서도 동작하는지 테스트한다.

검증:

```text
python -m pytest tests/test_ga4_tracking.py -q
```

### 작업 2: GA4 집계 DB 계약

파일:

- 새 migration `supabase/migrations/202607130002_ga4_metrics.sql`
- 새 테스트 `tests/test_ga4_schema.py`

순서:

1. `ga4_product_daily`, `ga4_traffic_daily`, `integration_syncs` 계약 테스트를 쓴다.
2. 날짜·상품과 날짜·source/medium unique key, 음수 방지 check, 필요한 index를 만든다.
3. 관리자 select RLS와 service role write 경계를 만든다.
4. `sync_ga4` job type과 관리자 전용 `request_ga4_sync()` RPC를 추가한다.
5. 활성 `sync_ga4` 작업을 하나만 허용하는 partial unique index를 추가한다.

### 작업 3: GA4 Data API 수집기

파일:

- 새 파일 `worker/ga4_sync.py`
- 수정 `scripts/requirements.txt`
- 새 테스트 `tests/test_ga4_sync.py`

순서:

1. Data API 응답을 날짜·상품·유입 행으로 변환하는 순수 함수 테스트를 쓴다.
2. 누락·합계 행, 알 수 없는 상품 ID, 숫자 형식 오류 테스트를 추가한다.
3. Application Default Credentials와 `analytics.readonly` scope를 사용하는 client를 구현한다.
4. 상품 보고서와 유입 보고서를 별도 `runReport` 요청으로 조회한다.
5. Supabase upsert payload와 `integration_syncs` 성공·실패 기록을 만든다.
6. 오류 메시지에서 bearer token과 자격 증명 내용을 마스킹한다.

### 작업 4: Worker 작업 연결

파일:

- 수정 `worker/control_plane.py`
- 수정 `worker/main.py`
- 수정 `admin/src/lib/dashboard.ts`
- 수정 `tests/test_control_plane.py`

순서:

1. 승인된 `sync_ga4` 작업 명령·handler 테스트를 쓴다.
2. `sync_ga4`는 subprocess 문자열이 아닌 전용 handler로 실행한다.
3. 성공 시 행 수와 조회 범위를 job result에 기록한다.
4. 실패 시 기존 집계를 삭제하지 않고 sync 상태만 error로 기록한다.
5. 마지막 성공 시각 기준 connected/stale/error/waiting 계산을 순수 함수로 만든다.

### 작업 5: 관리자 성과 데이터 조회

파일:

- 수정 `admin/src/types/admin.ts`
- 수정 `admin/src/lib/controlDesk.ts`
- 수정 `admin/src/lib/dashboard.ts`
- 새 테스트 또는 수정 `admin/tests/*`
- 수정 `tests/test_admin_dashboard.py`

순서:

1. 최근 30일 날짜 범위와 상품별 합계 계산 테스트를 쓴다.
2. GA 일별 행과 integration sync 상태를 Supabase에서 읽는다.
3. 상품별 `linkClicks`, 전체 active users·sessions·clicks, 유입 source/medium을 계산한다.
4. 주문·매출·수수료·광고비는 연결 전까지 `null`을 유지한다.
5. GA4 connection을 하드코딩 waiting이 아닌 sync 상태로 만든다.

### 작업 6: 관리자 성과 UI

파일:

- 수정 `admin/src/pages/PerformancePage.tsx`
- 수정 `admin/src/App.tsx`
- 수정 `admin/src/styles.css`
- 필요 시 새 순수 chart component

순서:

1. 실제 지표 카드, 날짜별 추이, 상품별 클릭, 유입 경로, 마지막 동기화 표시 계약을 쓴다.
2. 데이터가 0인 상태와 연결 대기를 구분한다.
3. `GA4 새로고침` 버튼이 `request_ga4_sync()`를 호출하게 한다.
4. queued/running 동안 중복 요청을 막고 현재 상태를 표시한다.
5. 모바일 표·차트, 키보드 focus, reduced motion을 확인한다.

### 작업 7: GA4 적용과 E2E

순서:

1. 전체 Python·관리자 테스트와 build를 실행한다.
2. Supabase migration을 적용하고 테이블·RLS·RPC를 확인한다.
3. Google Analytics Data API를 활성화한다.
4. 숫자형 Property ID를 설정한다.
5. 실행 서비스 계정을 GA4 Property Viewer로 추가한다.
6. 최소 보고서 dry-run 후 실제 sync를 한 번 실행한다.
7. 공개 사이트 클릭 이벤트를 DebugView 또는 네트워크 요청으로 확인한다.
8. 관리자 성과 화면에서 실제 0 또는 수집된 값을 확인한다.

## Phase 2: 원격 산출물과 보관 정책

### 작업 8: Storage·asset lifecycle schema

파일:

- 새 migration `supabase/migrations/202607130003_pipeline_assets.sql`
- 새 테스트 `tests/test_pipeline_assets_schema.py`

순서:

1. `pipeline-assets` private bucket과 허용 MIME type 계약을 쓴다.
2. asset kind를 raw, muted, frame, script, voice, subtitle, final, cover, caption으로 확장한다.
3. `retention_class`, `expires_at`, `cleanup_status`, `deleted_at`을 추가한다.
4. job status `waiting_input`과 필요한 원격 job type을 추가한다.
5. 관리자 signed read와 server write 권한을 분리한다.

### 작업 9: Storage workspace abstraction

파일:

- 새 파일 `worker/storage_workspace.py`
- 새 테스트 `tests/test_storage_workspace.py`

순서:

1. 상품 ID와 허용 filename으로만 Storage path를 생성하는 테스트를 쓴다.
2. path traversal, 절대 경로, 허용되지 않은 확장자를 거부한다.
3. 작업별 임시 디렉터리에 필요한 입력만 내려받는다.
4. checksum 검증 후 산출물과 asset metadata를 원자적으로 등록한다.
5. 컨테이너 종료 시 임시 파일을 정리한다.

### 작업 10: 게시 URL과 성공 후 정리

파일:

- 수정 `scripts/publish_reel.py`
- 새 파일 또는 수정 `worker/asset_cleanup.py`
- 수정 `worker/control_plane.py`
- 새 테스트 `tests/test_publish_storage.py`
- 새 테스트 `tests/test_asset_cleanup.py`

순서:

1. Git/Netlify 호스팅 없이 signed URL을 사용하는 실패 테스트를 쓴다.
2. Meta 처리·media publish·DB 저장 전에는 삭제가 호출되지 않는 테스트를 쓴다.
3. 성공 후 raw/muted/voice/final만 삭제하고 cover/text는 유지한다.
4. 정리 실패를 `cleanup_pending`으로 남기고 게시 성공을 유지한다.
5. 실패·취소 asset에 7일 expiry를 부여한다.
6. `cleanup_assets`를 반복 실행해도 안전한 idempotent cleanup을 구현한다.

## Phase 3: 전체 원격 콘텐츠 파이프라인

### 작업 11: DB 기반 pipeline orchestrator

파일:

- 새 파일 `worker/orchestrator.py`
- 수정 `worker/control_plane.py`
- 새 테스트 `tests/test_orchestrator.py`

순서:

1. 각 성공 단계가 다음 작업 하나만 생성하는 상태 전이 테스트를 쓴다.
2. sourced부터 caption_ready까지 happy path를 구현한다.
3. 사용자 입력이나 승인 경계에서는 새 작업을 만들지 않고 종료한다.
4. 재실행 시 이미 존재하는 성공 산출물을 재사용한다.
5. `pipeline.json`은 명시적 export에서만 생성한다.

### 작업 12: 수집·LLM·Typecast handler

파일:

- 기존 `scripts/fetch_video.py`, `scripts/dub.py`, `scripts/tts.py`, `scripts/make_cover.py` refactor
- 새 `worker/source_product.py`
- 새 `worker/source_video.py`
- 새 `worker/llm.py`
- 관련 단위 테스트

순서:

1. 기존 순수 로직을 유지하면서 입력·출력 path를 명시적으로 받게 만든다.
2. Coupang 상품 정보 수집과 Ali 영상 후보 수집을 Playwright handler로 분리한다.
3. 자동 수집 실패는 봇 차단을 우회하지 않고 `waiting_input`으로 전환한다.
4. LLM provider adapter와 script/caption schema 검증을 구현한다.
5. Typecast만 게시용 경로에서 허용한다.
6. 모든 생성물이 Storage와 DB에 기록되도록 한다.

### 작업 13: 관리자 검수·입력 폴백

파일:

- 수정 `admin/src/components/ProductDrawer.tsx`
- 필요 시 새 preview/editor/upload components
- 수정 `admin/src/lib/controlDesk.ts`
- 수정 `admin/src/types/admin.ts`
- 관련 테스트와 스타일

순서:

1. `waiting_input` 상태와 필요한 입력 종류를 표시한다.
2. Ali URL 직접 입력과 원본 영상 direct-to-Storage upload를 구현한다.
3. 대본·캡션 수정과 커버 선택을 승인 이력과 함께 저장한다.
4. 최종 영상 preview 후 기존 Instagram 승인 dialog를 사용한다.
5. Cloud Worker 오프라인 문구를 Cloud Run 실행 상태로 교체한다.

### 작업 14: 공개 링크 허브 export

파일:

- 새 파일 `scripts/export_products.py`
- 수정 `netlify.toml`
- 새 테스트 `tests/test_export_products.py`

순서:

1. Supabase 공개 상품 행에서 기존 products.json schema를 만드는 테스트를 쓴다.
2. active linked 상품만 내보내고 파트너스 고지문을 유지한다.
3. Netlify build에서 JSON을 생성하되 service key를 번들에 포함하지 않는다.
4. Worker는 링크 완료 후 build hook만 호출하고 Git 쓰기 권한을 갖지 않는다.

## Phase 4: Cloud Run과 배포 자동화

### 작업 15: Worker container

파일:

- 새 `Dockerfile`
- 새 `.dockerignore`
- 새 `worker/cloud_main.py`
- 새 container smoke tests

순서:

1. multi-stage 또는 최소 runtime image를 구성한다.
2. Python dependency, FFmpeg와 Playwright Chromium을 설치한다.
3. non-root 실행과 read-only code filesystem을 사용한다.
4. `/tmp` 또는 전용 ephemeral workspace만 writable하게 사용한다.
5. `--drain`, `--once`, `--sync-ga4`, `--cleanup` entrypoint를 검증한다.

### 작업 16: 인증 dispatcher와 Supabase Edge Function

파일:

- 새 `dispatcher/` 서비스
- 새 `supabase/functions/enqueue-and-dispatch/`
- 인증·권한 테스트

순서:

1. 잘못된 issuer/audience/sub/email JWT 거부 테스트를 쓴다.
2. Edge Function이 관리자 확인 후 작업을 생성하게 한다.
3. dispatcher가 Supabase JWT를 다시 검증하고 Cloud Run Job만 실행하게 한다.
4. dispatcher 서비스 계정에 해당 Job invoker만 부여한다.
5. 실행 실패 시 작업은 queued로 유지하고 관리자 재호출을 제공한다.

### 작업 17: CI/CD와 스케줄

파일:

- 새 `.github/workflows/test.yml`
- 새 `.github/workflows/deploy-cloud-worker.yml`
- 인프라 설정 문서 또는 `infra/` 선언

순서:

1. test workflow는 비밀 없이 실행한다.
2. deploy workflow는 main과 수동 dispatch만 허용한다.
3. GitHub OIDC와 GCP Workload Identity Federation을 연결한다.
4. action은 full commit SHA로 고정한다.
5. Artifact Registry와 Cloud Run 배포 후 smoke check를 한다.
6. Cloud Scheduler로 하루 한 번 GA4 sync와 asset cleanup을 설정한다.

## Phase 5: 전체 검증과 전환

### 작업 18: 회귀·보안 검증

명령:

```text
python -m pytest tests/ -q
npm --prefix admin test
npm --prefix admin run build
docker build .
git diff --check
```

추가 점검:

- 번들·Docker layer·Git history에 secret 값이 없는지 검사
- service account별 IAM 권한 검토
- Storage bucket public=false 확인
- Cloud Run retries=0 확인
- GA4 Viewer 외 권한이 없는지 확인
- Instagram side effect job max_attempts=1 확인

### 작업 19: 안전한 상품 E2E

1. 새 테스트 상품 하나를 관리자에서 등록한다.
2. Worker가 PC 없이 실행되는지 확인한다.
3. 자동 수집 실패 시 관리자 업로드 폴백을 확인한다.
4. 검수 전 Instagram 호출이 없는지 확인한다.
5. 최종 승인 후 한 번만 게시되는지 확인한다.
6. 게시 DB 저장 후 미디어 삭제를 확인한다.
7. 링크 허브 배포와 구매 클릭 `select_item`을 확인한다.
8. GA4 sync 후 관리자 실제 지표를 확인한다.

### 작업 20: 전환과 복구 문서

파일:

- 수정 `docs/PLAYBOOK.md`
- 수정 `AGENTS.md`
- 필요 시 `docs/CLOUD_RUN_RUNBOOK.md`

내용:

- Cloud Run 수동 실행·로그·중단·재배포
- secret rotation
- Instagram 토큰 갱신
- 실패 asset 7일 복구
- GA4 stale/error 복구
- 로컬 Worker 비상 폴백과 DB export/import
- 비용 알림과 Cloud Run 예산 한도

## 외부 상태로 인해 멈출 수 있는 지점

- Google Cloud 결제 프로젝트가 없으면 실제 Cloud Run 배포 전에 사용자 확인이 필요하다.
- GA4 숫자형 Property ID와 Property Viewer 추가가 안 되면 수집기 구현·테스트까지만 가능하다.
- 게시용 LLM API 키가 없으면 LLM adapter 구현 후 `waiting_input` 폴백까지만 검증한다.
- 쿠팡 Reporting API 승인 전에는 주문·매출·수수료를 연결하지 않는다.

이 경우에도 나머지 구현·단위 테스트·dry-run을 계속 진행하고, 막힌 외부 단계만 명확히
분리한다.
