# 관리자 Instagram 릴스 게시 승인 설계

날짜: 2026-07-13
상태: 사용자 승인됨

## 목적

온라인 관리자에서 릴스 게시를 명시적으로 승인하고, 로컬 PC의 Worker가 꺼져
있어도 요청을 Supabase 대기열에 보존한다. Worker가 실행되면 기존
`publish_reel.py`를 사용해 한 번만 게시하고 결과를 관리자에 반영한다.

## 확정 방식

Supabase 승인 RPC와 작업 대기열을 사용한다. 브라우저가 `jobs` 행을 직접
삽입하거나 Netlify에서 Meta API를 직접 호출하지 않는다.

- 관리자 브라우저: 게시 가능 상태 표시, 확인 대화상자, 승인 RPC 호출
- Supabase RPC: 관리자 확인, 상품 상태 확인, 활성 중복 작업 차단, 승인 작업 생성
- 로컬 Worker: 온라인이 되면 승인된 작업을 선점하고 기존 게시 CLI 실행
- 관리자 데이터: polling으로 대기·진행·성공·실패와 릴스 URL 표시

PC 전원만 켜진 상태는 Worker 온라인이 아니다. `worker/main.py` 프로세스가
실행되어 heartbeat를 보내야 작업을 처리한다. Worker가 오프라인이어도 승인
버튼은 사용할 수 있으며 작업은 `queued`로 유지된다.

## 게시 가능 조건

다음 조건을 모두 만족할 때만 새 게시 승인을 받는다.

1. 로그인한 사용자가 `is_todaysingi_admin()`을 통과한다.
2. 상품 단계가 `caption_ready`다.
3. 상품에 `reel_url`이 아직 없다.
4. 같은 상품에 `queued`, `claimed`, `running` 상태의 `publish_reel` 작업이 없다.

이미 `published`, `linked`, `ads_running`, `analyzed` 단계이거나 릴스 URL이
있으면 버튼은 `게시 완료`로 표시한다. 활성 게시 작업이 있으면 해당 작업 상태를
표시하고 새 승인을 만들지 않는다.

## 승인 RPC와 데이터 무결성

새 SQL migration에 다음을 추가한다.

- `approve_publish_reel(p_product_id bigint)` RPC
- 상품별 활성 게시 작업을 하나만 허용하는 partial unique index
- `publish_reel` 작업은 `approved_at`, `approved_by`가 필수인 check constraint
- side effect 작업의 `max_attempts = 1`
- 승인 행의 `approved_by = auth.uid()`, `approved_at = now()`
- 승인 활동을 `activity_logs`에 기록

RPC는 동시에 여러 번 호출돼도 기존 활성 작업을 반환하거나 하나만 생성한다.
실패한 게시 작업은 자동 재시도하지 않는다. 실패 원인을 검토한 후 사용자가
다시 확인 대화상자를 거쳐 새 작업을 승인한다.

## 관리자 UX

상품 상세 하단의 게시 버튼은 상태에 따라 바뀐다.

- 게시 가능: `릴스 게시 승인`
- 요청 중: `승인 처리 중…`
- Worker 오프라인 대기: `게시 대기 · Worker를 켜면 처리`
- Worker 온라인 대기/실행: `게시 대기` 또는 `게시 중`
- 완료: `게시 완료`
- 준비 미완료: `캡션 완성 후 게시 가능`

활성 버튼을 누르면 즉시 게시하지 않고 확인 대화상자를 연다. 대화상자에는 상품
번호와 이름, 최종 릴스 커버, 현재 Worker 상태, 게시 후 되돌리기 어렵다는 경고를
보여준다. 최종 `Instagram 게시 승인` 버튼을 눌러야 RPC를 호출한다.

Worker가 오프라인이면 성공 알림에 `승인됨 · Worker를 켜면 자동 게시`를
표시한다. 온라인이면 `승인됨 · Worker가 곧 처리`를 표시한다.

## 실행 흐름

1. 관리자가 상품 상세에서 게시 버튼을 누른다.
2. 프런트엔드가 상품·작업 상태를 다시 확인하고 확인 대화상자를 연다.
3. 관리자가 최종 승인한다.
4. Supabase RPC가 승인된 `publish_reel` 작업을 원자적으로 생성한다.
5. Worker가 작업을 선점한다.
6. Worker의 기존 승인 검사 후 `scripts/publish_reel.py <id>`를 실행한다.
7. 성공하면 pipeline이 `published`로 이동하고 릴스 URL과 Meta media ID를 저장한다.
8. Worker가 pipeline을 Supabase에 동기화한다.
9. 관리자가 성공 상태와 릴스 링크를 확인한다.

## 오류 처리

- 네트워크/RPC 오류: 대화상자를 유지하고 오류 메시지를 표시한다.
- 중복 클릭/동시 요청: RPC와 unique index가 하나의 활성 작업만 허용한다.
- Worker 오프라인: 오류가 아니며 작업을 `queued`로 유지한다.
- 로컬 영상·캡션 누락: Worker 작업을 실패 처리하고 진단 요약을 저장한다.
- Meta API 실패: 자동 재시도하지 않고 수동 재승인을 요구한다.
- Worker 중단: side effect 작업은 자동 재실행하지 않고 실패 상태로 전환한다.

## 테스트

- SQL 계약 테스트: 승인 필드, 단일 활성 게시 index, RPC 권한과 단계 검사
- 프런트엔드 순수 로직 테스트: 게시 가능·대기·진행·완료·미준비 상태 계산
- Worker 테스트: 미승인 작업 거부, 승인 작업 명령 생성, 자동 재시도 없음
- 빌드 검증: TypeScript와 Vite production build
- 수동 E2E: Worker 오프라인 승인 → queued 확인 → Worker 실행 → 게시 결과 반영

실제 E2E에서는 테스트용 새 상품만 사용한다. 이미 게시된 상품 `[003]`은 버튼이
`게시 완료`로 표시되는지만 확인하고 다시 게시하지 않는다.

## 범위 밖

- 관리자 웹에서 로컬 PC나 Worker 프로세스를 원격으로 켜는 기능
- Meta API를 Netlify에서 직접 호출하는 기능
- 광고 집행 승인과 자동 재시도
- 기존 릴스의 수정·삭제·재게시
