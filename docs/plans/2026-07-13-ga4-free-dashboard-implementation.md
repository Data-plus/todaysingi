# GA4 무결제 대시보드 구현 계획

> 승인 설계: `docs/plans/2026-07-13-ga4-free-dashboard-design.md`
>
> 구현 원칙: 테스트를 먼저 실패시키고 최소 코드로 통과시킨다. 원격 영상 파이프라인과
> 생성형 AI는 구현하지 않는다.

## 1. 기준 브랜치와 기존 상태 고정

**대상**

- 브랜치 `feature/ga4-free-dashboard`
- `admin/`
- `site/app.js`
- `supabase/`

**절차**

1. `origin/main` 기준의 현재 관리자 테스트와 Python 테스트를 실행한다.
2. 공개 사이트의 GA 측정 ID와 기존 상품 클릭 이벤트를 확인한다.
3. 현재 브랜치에 Cloud Run, Dispatcher, Docker 배포 workflow가 없음을 확인한다.
4. 실서버에는 앞선 실험 중 GA4 스키마와 GCP 비용 스키마가 수동 적용됐음을 기록한다.

## 2. GA4 데이터베이스 계약 추가

**파일**

- 추가: `supabase/migrations/202607130002_ga4_metrics.sql`
- 추가: `tests/test_ga4_schema.py`
- 추가: `tests/test_migration_replay.py`

**테스트 먼저**

1. 최근 삼십 일 상품 클릭과 유입 일별 테이블이 날짜·차원 조합으로 유일함을 검사한다.
2. 관리자 조회는 authenticated 한 명에게만 허용되고 쓰기는 service role만 가능함을 검사한다.
3. `replace_ga4_metrics`가 기간을 원자적으로 교체하고 실패 시 기존 행을 보존하는지 검사한다.
4. `get_ga4_performance`와 `integration_syncs` 반환 계약을 검사한다.
5. 마이그레이션 재실행 시 중복 정책·제약 오류가 나지 않는지 검사한다.

**구현**

Cloud 기능 커밋에서 GA4 전용 마이그레이션만 가져와 현재 main 스키마에 맞게 줄인다.
`sync_ga4` queue나 Cloud Worker claim은 추가하지 않는다.

## 3. Edge Function 순수 로직과 인증 구현

**파일**

- 추가: `supabase/functions/sync-ga4/index.ts`
- 추가: `supabase/functions/sync-ga4/ga4.ts`
- 추가: `supabase/functions/sync-ga4/ga4.test.ts`
- 추가: `tests/test_ga4_edge_contract.py`

**테스트 먼저**

1. Property ID, 날짜 범위, 최대 구십 일 제한을 검사한다.
2. 상품 보고서가 `itemListId=todaysingi_link_hub`와 `itemsClickedInList`를 사용하는지 검사한다.
3. 유입 보고서의 dimensions와 metrics 계약을 검사한다.
4. GA 응답의 날짜·정수·상품 ID를 검증하고 중복 차원을 합산하는지 검사한다.
5. 서비스 계정 JSON 누락, 잘못된 private key, Google 4xx/5xx를 안전한 오류로 바꾸는지 검사한다.
6. 관리자 JWT 또는 올바른 Cron secret만 허용하는지 검사한다.
7. 오류 응답과 로그에 private key, 액세스 토큰, service role이 포함되지 않는지 검사한다.

**구현**

1. WebCrypto RS256으로 서비스 계정 assertion을 서명한다.
2. Google OAuth token endpoint에서 읽기 전용 토큰을 받는다.
3. Data API 보고서 두 개를 병렬 요청한다.
4. service role Supabase client로 `replace_ga4_metrics` RPC를 한 번 호출한다.
5. 성공·실패 integration 상태를 기록한다.
6. `--no-verify-jwt` 배포를 전제로 함수 내부에서 관리자와 Cron 호출을 직접 검증한다.
7. CORS origin은 운영 관리자 URL과 명시한 로컬 미리보기만 허용한다.

## 4. Supabase Cron과 실험 스키마 정리

**파일**

- 추가: `supabase/migrations/202607130003_ga4_cron.sql`
- 추가: `supabase/migrations/202607130008_remove_gcp_cost_monitoring.sql`
- 추가: `tests/test_ga4_cron_schema.py`
- 추가: `tests/test_gcp_cost_cleanup_schema.py`

**테스트 먼저**

1. Cron 이름이 `todaysingi-ga4-daily`이고 UTC `15 19 * * *`인지 검사한다.
2. URL과 cron secret을 SQL이나 Git에 평문으로 넣지 않는지 검사한다.
3. 예약 재적용이 중복 작업을 만들지 않는지 검사한다.
4. 비용 테이블·RPC·integration·대기 작업만 제거하고 GA4 및 로컬 관리자 데이터는 보존하는지 검사한다.

**구현**

1. `pg_cron`, `pg_net`, Vault의 명명된 secret을 사용하는 예약 SQL을 추가한다.
2. 기존 같은 이름의 Cron이 있으면 안전하게 교체한다.
3. 이미 실서버에 적용된 GCP 비용 실험 객체를 제거하는 전용 정리 migration을 추가한다.

## 5. 관리자 PERFORMANCE를 실제 GA4 대시보드로 교체

**파일**

- 수정: `admin/src/types/admin.ts`
- 수정: `admin/src/lib/controlDesk.ts`
- 수정: `admin/src/lib/dashboard.ts`
- 추가: `admin/src/lib/performance.ts`
- 수정: `admin/src/App.tsx`
- 수정: `admin/src/pages/PerformancePage.tsx`
- 수정: `admin/src/pages/SettingsPage.tsx`
- 수정: `admin/src/styles.css`
- 추가: `admin/tests/performance.test.ts`

**테스트 먼저**

1. 일별 상품 클릭과 유입 행을 삼십 일 요약으로 집계한다.
2. 상품별·유입별 비중과 빈 데이터 처리를 검사한다.
3. 마지막 성공, stale, running, failed 연결 상태를 검사한다.
4. 수동 새로고침 중 버튼이 비활성화되고 성공 뒤 데이터를 다시 읽는지 검사한다.
5. GCP 비용, Cloud Worker, LLM API 문구가 PERFORMANCE에 남지 않는지 검사한다.
6. 쿠팡 주문·매출은 승인 대기로 유지되는지 검사한다.

**구현**

1. `loadDeskData`가 GA4 일별 행과 integration 상태를 함께 읽는다.
2. `invokeGa4Sync`가 로그인 세션 JWT로 `sync-ga4` 함수를 호출한다.
3. PERFORMANCE를 클릭·세션·사용자 카드, 일별 추이, 상품별 클릭, 유입 경로, 연동 상태로 구성한다.
4. Overview는 기존 상품·로컬 작업 중심을 유지한다.
5. Settings의 GA4 항목에는 실제 마지막 성공과 오류만 표시한다.

## 6. 공개 사이트 클릭 이벤트 검증

**파일**

- 수정: `site/app.js`
- 추가: `tests/test_ga4_tracking.py`

**테스트 먼저**

1. 상품 클릭 시 `select_item`이 한 번 발생하는지 검사한다.
2. `item_list_id`, `item_id`, `item_name`이 GA4 전자상거래 계약과 일치하는지 검사한다.
3. 검색이나 UI 상호작용이 가짜 상품 클릭으로 집계되지 않는지 검사한다.

**구현**

기존 `product_click` 이벤트가 있으면 보조 이벤트로 유지할 수 있지만 성과 집계의 진실 소스는
`select_item`으로 통일한다.

## 7. Google Cloud를 무결제 GA 전용 프로젝트로 축소

**외부 변경 순서**

1. `todaysingi-ga4-reader` 서비스 계정을 만들고 GCP 프로젝트 역할은 부여하지 않는다.
2. Analytics 속성 `545183806`에 해당 이메일을 Viewer로 추가한다.
3. 사용자 관리 키를 한 개 생성해 Supabase Function Secret으로 전송한다.
4. 로컬 임시 키 파일을 즉시 삭제하고 키가 한 개뿐인지 확인한다.
5. Cloud Run Job/Service, Scheduler, Artifact Registry, BigQuery dataset, Secret Manager 비밀을 삭제한다.
6. 기존 Worker/Dispatcher/Scheduler/GitHub 서비스 계정과 WIF 리소스가 있으면 삭제한다.
7. `todaysingi monthly safety budget`을 삭제한다.
8. 프로젝트에서 결제 계정 연결을 해제한다.
9. Analytics Data API 외 선택 API를 비활성화한다.
10. `billingEnabled=false`, Cloud Run 0개, Artifact 저장소 0개, BigQuery 업무 dataset 0개,
    Secret 0개를 확인한다.

결제 해제 뒤 Analytics Data API가 동작하지 않더라도 결제를 다시 연결하지 않는다. 원인을
보고하고 무결제 범위 안에서만 대안을 찾는다.

## 8. Supabase 실배포와 예약 등록

**외부 변경**

1. `GA4_PROPERTY_ID`, `ADMIN_EMAIL`, `GA4_SERVICE_ACCOUNT_JSON`, `GA4_CRON_SECRET`,
   `GA4_ALLOWED_ORIGINS`를 Function Secrets에 저장한다.
2. `sync-ga4`를 배포한다.
3. Vault에 project URL과 cron secret을 저장한다.
4. GA4 schema, Cron, GCP 비용 정리 migration을 적용한다.
5. 수동 함수 호출을 한 번 실행한다.
6. GA4 저장 행과 integration 성공 상태를 확인한다.
7. Cron 작업을 `Run now` 또는 같은 요청으로 한 번 검증하고 실행 기록을 확인한다.

비밀 값은 CLI 인자, 브라우저 콘솔, Git diff, 로그에 출력하지 않는다.

## 9. 전체 검증과 배포

**명령**

~~~powershell
python -m pytest tests/ -q
npm --prefix admin test -- --run
npm --prefix admin run build
git diff --check
~~~

**실서버 검증**

1. 기능 브랜치를 push하고 검증한다.
2. main에 병합해 Netlify 자동 배포를 기다린다.
3. GitHub 로그인, PERFORMANCE 진입, 수동 GA4 새로고침을 실제 브라우저에서 확인한다.
4. 클릭·세션·유입 수치와 빈 상태·오류 상태를 확인한다.
5. 상품·로컬 작업·게시 승인 기능의 회귀가 없는지 확인한다.
6. 라이브 관리자에 GCP 비용·Cloud Worker·LLM 비용 문구가 없는지 확인한다.
7. GCP 결제 비활성 상태를 마지막으로 다시 확인한다.
