# GA4 무결제 대시보드 설계

## 배경

오늘의신기템의 영상 수집·가공·더빙·게시 작업은 소유자가 로컬 PC에서 계속 실행한다.
관리자 페이지는 원격 미디어 파이프라인이 아니라 상품 현황과 실제 성과를 읽는 대시보드에
집중한다. 기존에 준비한 Cloud Run, BigQuery Billing Export, Artifact Registry와 LLM API
구성은 운영 비용과 복잡성에 비해 현재 월간 처리량에 필요하지 않다.

Google Analytics Data API 호출에는 Google Cloud 프로젝트가 필요하다. 다만 프로젝트에
결제 계정을 연결하거나 유료 실행 자원을 둘 필요는 없다. 따라서 전용 프로젝트는 결제를
해제하고 Analytics Data API와 읽기 전용 서비스 계정만 남긴다.

## 목표

- 관리자 PERFORMANCE 화면에 최근 삼십 일의 실제 GA4 데이터를 표시한다.
- 상품 링크 클릭, 세션, 활성 사용자, 상품별 클릭, 유입 경로를 제공한다.
- 매일 오전 네 시 십오 분 자동 동기화와 관리자 수동 새로고침을 모두 지원한다.
- Google Cloud 결제 연결과 모든 유료 가능 리소스를 제거한다.
- 관리자에서 Cloud Worker, GCP 비용, LLM 상태를 제거한다.
- 기존 로컬 영상 제작·검수·릴스 게시 흐름은 변경하지 않는다.

## 비목표

- Cloud Run 또는 GitHub Actions에서 영상 파이프라인을 실행하지 않는다.
- LLM API로 영상 분석, 대본, 캡션을 생성하지 않는다.
- BigQuery Export를 사용하지 않는다.
- 쿠팡 Reporting API 승인 전 주문·매출·수수료를 추정하지 않는다.
- 광고 성과나 ROAS를 임의 데이터로 채우지 않는다.

## 선택한 구조

### Google Cloud

`todaysingi-prod-20260713` 프로젝트의 결제 연결을 해제한다. 다음 항목을 삭제한다.

- Cloud Run Job과 Service
- Artifact Registry 저장소와 컨테이너 이미지
- BigQuery `billing_export` dataset
- Cloud Scheduler 작업
- Secret Manager의 파이프라인 비밀
- Cloud Billing Budget
- Worker, Dispatcher, Scheduler, GitHub 배포 서비스 계정
- 원격 배포용 Workload Identity 리소스가 존재하면 해당 리소스

프로젝트에는 `analyticsdata.googleapis.com`과 `todaysingi-ga4-reader` 서비스 계정만
남긴다. 이 서비스 계정은 Google Analytics 속성의 Viewer 권한만 갖고 GCP 프로젝트
IAM 역할은 추가하지 않는다. 결제 비활성 상태를 CLI로 최종 확인한다.

### Supabase Edge Function

`sync-ga4` Edge Function이 짧은 집계 작업을 담당한다.

1. 호출자를 인증한다.
2. 서비스 계정 JWT를 서명해 Google OAuth 액세스 토큰을 받는다.
3. GA4 Data API에 최근 삼십 일 보고서 두 개를 요청한다.
4. 상품 클릭 행과 유입 행을 검증·정규화한다.
5. 기존 `replace_ga4_metrics` RPC를 한 번 호출해 기간 데이터를 원자적으로 교체한다.
6. `integration_syncs`에 성공 시각, 범위, 저장 행 수 또는 제한된 오류 요약을 기록한다.

함수는 재실행해도 같은 기간을 교체하므로 중복 집계하지 않는다. 브라우저에는 서비스 계정
키와 service role 키를 반환하지 않는다.

### 인증과 비밀

- 수동 호출: 로그인한 Supabase 사용자의 JWT를 검사하고 이메일이
  `plusmg@gmail.com`인지 확인한다.
- 예약 호출: `GA4_CRON_SECRET` 전용 헤더를 상수 시간 비교로 확인한다.
- Google 자격 증명: `GA4_SERVICE_ACCOUNT_JSON`을 Supabase Function Secret에 저장한다.
- 예약 호출 비밀: 같은 값을 Function Secret과 Supabase Vault에 각각 저장한다.
- Git, Netlify 번들, 브라우저 저장소에는 어떤 비밀도 넣지 않는다.

## 예약 실행

Supabase Cron과 `pg_net`으로 매일 `19:15 UTC`, 즉 한국 시간 다음 날 오전 네 시 십오
분에 `sync-ga4`를 한 번 호출한다. 예약 작업 이름은 `todaysingi-ga4-daily`로 고정해
재적용 시 중복 생성하지 않는다. Cron 호출 결과와 함수 실행 결과는 각각 Supabase의
Cron 기록과 Edge Function 로그에서 확인한다.

## 관리자 데이터 흐름

PERFORMANCE 진입 시에는 Supabase에 마지막으로 저장된 데이터를 즉시 읽는다. 사용자가
`GA4 새로고침`을 누르면 Edge Function을 직접 호출하고, 성공 응답 뒤 대시보드 데이터를
다시 불러온다. 중복 클릭을 막고 실행 중 상태를 표시한다.

화면은 다음에 집중한다.

- 최근 삼십 일 상품 링크 클릭
- 세션과 활성 사용자
- 클릭·세션 일별 추이
- 상품별 클릭과 비중
- 유입 source / medium과 비중
- 마지막 성공 시각, 조회 범위, 저장 행 수, 마지막 오류
- 쿠팡 API 승인 대기 상태

GCP 비용 카드, 예산 그래프, Cloud Worker 연결 상태와 원격 파이프라인 버튼은 표시하지
않는다. 데이터가 없으면 0으로 확정하지 않고 `첫 동기화 대기`를 표시한다.

## GA4 이벤트 계약

공개 사이트의 상품 클릭은 GA4 `select_item` 이벤트로 전송한다. 각 이벤트는
`item_list_id=todaysingi_link_hub`와 상품의 `item_id`, `item_name`을 포함해야 한다.
Edge Function은 `itemsClickedInList` 지표를 이 목록 ID로 필터링한다. 세션 보고서는
`sessionSource`, `sessionMedium`, `sessions`, `activeUsers`를 사용한다.

## 오류 처리

- 인증 실패는 사유를 노출하지 않는 401 또는 403으로 응답한다.
- Google 인증, API 권한, 잘못된 Property ID, 응답 스키마 오류를 구분해 내부 로그에 남긴다.
- 관리자에는 천 자 이하의 비민감 오류 요약만 표시한다.
- 동기화 실패 시 기존 성공 데이터는 보존한다.
- 동시에 두 요청이 와도 DB 교체 RPC와 실행 중 상태로 결과가 일관되게 유지되도록 한다.
- 예약 호출 실패는 다음 날 자동 재시도되며 관리자가 수동으로 즉시 재시도할 수 있다.

## 데이터베이스 정리

이미 적용된 GCP 비용 실험 스키마는 정리 마이그레이션으로 제거한다.

- `gcp_cost_daily`, `gcp_cost_settings`
- 비용 조회·교체·요청 RPC
- `gcp_billing` integration 행
- 대기 중인 `sync_gcp_costs` 작업

GA4 집계 테이블, integration 행, 조회 RPC와 교체 RPC는 유지한다. 원격 미디어 파이프라인
전용 스키마 중 기존 로컬 관리자 기능이 참조하지 않는 부분은 별도 확인 후에만 제거한다.

## 검증

- Edge Function의 인증, JWT 서명 입력, 보고서 요청, 응답 파싱, 오류 매핑을 단위 테스트한다.
- SQL 마이그레이션의 RLS, RPC 권한, 기간 교체와 실패 시 보존을 테스트한다.
- 관리자 테스트에서 로딩, 성공, 비어 있음, 실패, 중복 클릭 방지를 확인한다.
- 공개 사이트가 올바른 `select_item` payload를 보내는지 확인한다.
- 실제 수동 동기화를 한 번 실행해 Supabase 행과 관리자 수치를 GA4 화면과 대조한다.
- Cron 등록과 최근 실행 기록을 확인한다.
- 마지막으로 GCP 프로젝트의 `billingEnabled=false`와 유료 리소스 부재를 확인한다.

## 비용 안전장치

- GCP 결제 계정을 프로젝트에서 완전히 해제한다.
- Supabase Free의 기존 프로젝트와 포함 호출량 안에서만 실행한다.
- 하루 한 번의 예약 호출과 사용자 수동 호출 외 자동 반복을 만들지 않는다.
- 함수는 최근 삼십 일 보고서 두 개만 요청하고 최대 행 수를 제한한다.
- 새로운 유료 서비스나 외부 생성형 AI API는 연결하지 않는다.
