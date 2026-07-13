# 관리자 Instagram 릴스 게시 승인 구현 계획

날짜: 2026-07-13

## 목표

관리자 상품 상세의 고정 비활성 게시 버튼을 Supabase 승인 RPC와 로컬 Worker
대기열에 연결한다. Worker가 오프라인이어도 승인은 보존하고, 중복 게시와 자동
재시도를 DB와 UI 양쪽에서 차단한다.

## 작업 1: 게시 승인 DB 계약 테스트

파일:

- 새 파일 `tests/test_admin_publish_approval.py`
- 새 파일 `supabase/migrations/202607130001_admin_publish_approval.sql`

순서:

1. migration에 승인 RPC, publish 승인 check constraint, 활성 작업 partial unique
   index, `max_attempts = 1`, 관리자 권한 검사가 있어야 한다는 실패 테스트를 쓴다.
2. 해당 테스트만 실행해 migration이 아직 없어 실패하는지 확인한다.
3. SQL migration을 최소 구현한다.
4. 테스트를 다시 실행한다.

RPC `approve_publish_reel(bigint)`는 다음을 보장한다.

- `is_todaysingi_admin()` 검사
- 상품이 `caption_ready`이고 `reel_url is null`인지 검사
- 기존 활성 게시 작업이 있으면 그 작업 ID 반환
- 없으면 `approved_at = now()`, `approved_by = auth.uid()`,
  `max_attempts = 1`인 작업 생성
- activity log 기록
- authenticated 역할만 실행 가능

## 작업 2: 게시 버튼 상태 순수 로직

파일:

- 새 파일 `admin/src/lib/publishState.ts`
- 새 파일 `admin/tests/publishState.test.ts`
- 수정 `admin/package.json`

순서:

1. Node 내장 test runner로 다음 상태의 실패 테스트를 쓴다.
   - `caption_ready` + 게시 작업 없음 → ready
   - Worker 오프라인이어도 ready
   - queued/claimed/running → queued/running
   - reel URL 또는 게시 이후 단계 → published
   - 그 외 단계 → blocked
   - failed/cancelled 작업만 있으면 다시 승인 가능
2. `publishState.ts`를 구현한다.
3. `npm test` 스크립트를 추가하고 테스트를 통과시킨다.

## 작업 3: Supabase 승인 호출

파일:

- 수정 `admin/src/lib/controlDesk.ts`
- 수정 `admin/src/types/admin.ts`
- 수정 `tests/test_admin_dashboard.py`

순서:

1. 관리자 소스 계약 테스트에 `approvePublishReel`과 RPC 호출, 승인 필드 조회를
   요구하는 실패 조건을 추가한다.
2. `jobs` 조회에 `approved_at`, `approved_by`를 포함한다.
3. `AdminJob`에 승인 필드를 매핑한다.
4. `approvePublishReel(productId)`에서 RPC를 호출하고 작업 ID를 반환한다.
5. Supabase 오류를 사용자용 메시지로 전달한다.

## 작업 4: 확인 대화상자와 동적 버튼

파일:

- 새 파일 `admin/src/components/PublishApprovalDialog.tsx`
- 수정 `admin/src/components/ProductDrawer.tsx`
- 수정 `admin/src/App.tsx`
- 수정 `admin/src/styles.css`
- 수정 `tests/test_admin_dashboard.py`

순서:

1. 소스 계약 테스트에 확인 대화상자, 최종 승인 버튼, Worker 오프라인 안내,
   동적 게시 상태를 먼저 추가한다.
2. 상품 상세에서 현재 상품의 게시 상태를 계산한다.
3. ready 상태에서만 확인 대화상자를 연다.
4. 최종 커버(`reel_cover`) signed URL, 상품 번호·이름, Worker 상태와 경고를
   표시한다.
5. App에서 RPC 호출 중 busy 상태를 관리한다.
6. 성공 시 즉시 데이터를 새로고침하고 Worker 상태에 맞는 알림을 표시한다.
7. queued/running/published/blocked 상태별 버튼 문구와 title을 적용한다.
8. 모바일, focus-visible, reduced motion 스타일을 확인한다.

## 작업 5: Worker 안전성 회귀 테스트

파일:

- 수정 `tests/test_control_plane.py` 필요 시
- 수정 `worker/control_plane.py` 필요 시

순서:

1. 미승인 게시 작업이 거부되는 기존 테스트를 유지한다.
2. 승인된 게시 작업이 정확히 `publish_reel.py <id>` 명령으로 변환되는 테스트를
   추가한다.
3. side effect 작업이 자동 재시도되지 않는 설정은 SQL 계약으로 검증한다.
4. 기존의 미커밋 Worker 가격·이미지 동기화 변경과 충돌하지 않게 최소 수정한다.

## 작업 6: 전체 검증

명령:

```text
python -m pytest tests/test_admin_publish_approval.py -q
python -m pytest tests/test_admin_dashboard.py tests/test_control_plane.py -q
python -m pytest tests/ -q
npm test
npm run build
npm run build:netlify
```

추가 점검:

- `git diff --check`
- 번들에 service role, Instagram token, `.env` 값이 없는지 검색
- 기존 `[003]`은 `게시 완료`로 표시되고 새 작업이 생성되지 않는지 확인

## 작업 7: Supabase 적용과 안전한 E2E

1. `supabase migration list`로 연결 프로젝트와 적용 상태를 확인한다.
2. 새 migration을 프로젝트 `davyotbbhgnfxpgaglki`에 적용한다.
3. RPC 권한과 constraint가 실제 DB에 생성됐는지 읽기 전용으로 확인한다.
4. 이미 게시된 `[003]`에 RPC를 호출하지 않는다.
5. 관리자에서 `[003]` 버튼이 `게시 완료`로 보이는지 확인한다.
6. 다음 `caption_ready` 상품에서만 Worker 오프라인 승인 E2E를 수행한다.

## 작업 8: 커밋과 배포

1. 기존 미커밋 파일과 이번 구현 파일을 구분해 검토한다.
2. 기능 관련 파일만 `feat: 관리자 릴스 게시 승인 연결`로 커밋한다.
3. main을 push해 Netlify 배포를 시작한다.
4. `/admin/` 배포본에서 로그인, 상품 상세, 게시 완료 상태와 모바일 레이아웃을
   확인한다.
