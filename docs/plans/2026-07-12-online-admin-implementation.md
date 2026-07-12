# 오늘의신기템 온라인 관리자 구현 계획

설계 정본: `docs/plans/2026-07-12-online-admin-design.md`

## 목표와 경계

1차 릴리스는 관리자 로그인, 상품 관리, 작업 큐, 로컬 Worker, 진행 로그,
완성 영상 업로드와 검수까지 제공한다. Instagram 게시와 광고는 데이터 구조와
승인 UI의 자리를 만들되 실제 API 실행은 후속 릴리스로 둔다.

기존 `scripts/`는 Claude가 계속 수정할 수 있으므로 직접 재작성하지 않는다.
Worker의 handler/adapter가 기존 CLI를 subprocess로 호출한다.

## 기술 구성

- `admin/`: Vite + React + TypeScript
- 스타일: CSS custom properties와 자체 컴포넌트. Atelier Zero 토큰을 중앙 관리
- 데이터: `@supabase/supabase-js`, TanStack Query
- 검증: Vitest + Testing Library, Playwright 모바일/데스크톱 스모크
- `supabase/`: SQL migration, RLS, RPC, seed/migration script
- `worker/`: Python polling Worker와 작업 handler

## 0. 사전 결정 및 환경

- [ ] 관리자 이메일을 Netlify/Supabase 환경변수로 지정
- [ ] Supabase 프로젝트 생성 후 URL과 anon key를 Netlify에 등록
- [ ] 로컬 `.env`에 service role key를 추가하되 git에는 포함하지 않음
- [ ] `netlify.toml`에서 기존 공개 사이트와 `/admin/*` SPA 배포 전략 확정
- [ ] Claude가 수정 중인 파일의 작업이 끝났는지 확인하고 겹치는 파일을 피함

수용 기준: 비밀키가 git diff나 브라우저 번들에 포함되지 않는다.

## 1. Supabase 스키마와 권한

- [ ] products, jobs, content, assets, publications, campaigns, metrics,
  activity_logs, workers 테이블 migration 작성
- [ ] enum 대신 확장 가능한 check constraint로 상태 검증
- [ ] updated_at trigger와 작업/승인 감사 로그 trigger 작성
- [ ] private `completed-assets` Storage bucket 정책 작성
- [ ] 관리자 한 명만 접근하는 RLS helper와 전 테이블 정책 작성
- [ ] `claim_next_job(worker_id)` RPC를 `FOR UPDATE SKIP LOCKED` 방식으로 작성
- [ ] heartbeat와 만료 lock 복구 RPC 작성
- [ ] SQL 테스트 또는 로컬 Supabase 검증 스크립트 작성

수용 기준: anon 사용자는 데이터 접근 불가, 허용된 로그인 사용자만 CRUD 가능,
service-role Worker 둘이 동시에 실행돼도 한 작업을 중복 선점하지 않는다.

## 2. 기존 데이터 이행

- [ ] `ops/pipeline.json`을 읽어 products와 history/activity_logs로 변환하는 dry-run 도구 작성
- [ ] `site/products.json`과 연결해 partnersLink/siteProductId를 보존
- [ ] 중복 URL과 잘못된 단계에 대한 명확한 보고서 출력
- [ ] 실제 import는 `--apply`가 있을 때만 수행

수용 기준: `[001]`을 손실 없이 변환하고 재실행해도 중복 생성되지 않는다.

## 3. 관리자 앱 기반

- [ ] `admin/` 앱 생성, TypeScript strict mode와 테스트 설정
- [ ] Supabase client, Query client, route guard 구성
- [ ] 이메일 로그인과 로그아웃 구현
- [ ] 허용 이메일 불일치 시 접근 차단 화면 구현
- [ ] 데스크톱 상단 내비게이션과 모바일 하단 내비게이션 구현
- [ ] 로딩, 빈 상태, 오류 경계, toast 공통 컴포넌트 구현

수용 기준: 비로그인 사용자는 관리자 내용을 볼 수 없고 모바일 390px에서도
핵심 내비게이션이 동작한다.

## 4. Atelier Zero 디자인 시스템

- [ ] 종이색, 잉크색, 버밀리언, 상태색, 간격, 선, 그림자 토큰 정의
- [ ] 한국어용 세리프/산세리프 폰트 스택과 유동형 타이포 스케일 정의
- [ ] EditorialHeader, Rule, PrintLabel, MetricIndex, StatusStamp 구현
- [ ] ProductCollage, PipelineRail, WorkerSignal 구현
- [ ] scroll reveal은 reduced-motion 환경에서 비활성화
- [ ] 포커스 링, 키보드 이동, 명암 대비 검증

수용 기준: Open Design 레퍼런스의 편집감을 유지하면서 상태와 실행 버튼이
장식에 묻히지 않는다.

## 5. 대시보드와 상품 관리

- [ ] Worker online/offline, 작업 수, 현재 상품 지표 조회
- [ ] 최근 상품 콜라주와 9단계 pipeline rail 구현
- [ ] 상품 목록 검색·단계 필터·정렬 구현
- [ ] 상품 생성/수정 폼과 URL 검증 구현
- [ ] 상품 상세의 개요, 콘텐츠, 자산, 활동 탭 구현
- [ ] optimistic update 실패 시 안전하게 롤백

수용 기준: 상품 생성 후 새 작업을 큐에 넣을 수 있고 새로고침 후 데이터가 유지된다.

## 6. 작업 큐 UI

- [ ] 작업 유형과 payload를 검증해 jobs에 생성
- [ ] 대기, 실행, 성공, 실패 필터와 진행률 표시
- [ ] 사용자 요약 로그와 진단 로그 분리
- [ ] 재시도 가능한 작업만 재시도 버튼 표시
- [ ] Instagram/광고 작업은 승인 없이는 생성 불가한 UI와 DB 제약 추가
- [ ] realtime subscription 또는 짧은 polling으로 상태 갱신

수용 기준: 중복 클릭이 같은 멱등 키의 작업을 두 개 만들지 않는다.

## 7. 로컬 Worker

- [ ] worker 등록과 heartbeat loop 구현
- [ ] 원자적 작업 선점, lock 연장, 취소 확인 구현
- [ ] handler registry와 subprocess adapter 구현
- [ ] 기존 `fetch_video.py`, `dub.py`, `add_product.py` handler 연결
- [ ] stdout/stderr를 redaction 후 단계별 로그로 전송
- [ ] graceful shutdown 시 작업 상태와 lock 정리
- [ ] 완료 파일의 checksum과 metadata 생성

수용 기준: PC 종료 후 요청이 보존되고, 재실행 시 안전하게 처리된다. 비밀키나
전체 환경변수는 로그에 나타나지 않는다.

## 8. 완성 영상 업로드와 검수

- [ ] final.mp4와 썸네일만 private Storage에 업로드
- [ ] 업로드 성공 후에만 assets를 ready로 전환
- [ ] 관리자에서 signed URL로 세로 영상 재생
- [ ] 대본/캡션 편집과 버전 저장
- [ ] 승인, 수정 요청, 반려 동작과 활동 로그 구현
- [ ] 게시 승인 버튼은 publication record만 만들고 실제 Meta 실행은 feature flag로 차단

수용 기준: 휴대폰에서 영상을 재생하고 승인할 수 있으며 만료된 URL은 재발급된다.

## 9. 배포와 운영

- [ ] Netlify build/redirect 설정으로 기존 `site/`와 관리자 경로 공존
- [ ] CSP, Referrer-Policy, frame 제한 등 보안 헤더 설정
- [ ] production 환경변수 검증과 연결 상태 화면 구현
- [ ] Worker 시작 명령과 Windows 자동 시작 선택지를 README에 문서화
- [ ] DB 백업, Storage 정리, 실패 작업 정리 절차 문서화

수용 기준: 기존 공개 링크 페이지가 회귀 없이 동작하고 `/admin`은 로그인으로
보호된다.

## 10. 최종 검증

- [ ] unit/component 테스트 전체 통과
- [ ] Supabase RLS 부정 테스트 통과
- [ ] 두 Worker 동시 선점 테스트 통과
- [ ] PC offline → 요청 → online → 완료 E2E 통과
- [ ] 실패 → 로그 확인 → 재시도 E2E 통과
- [ ] 모바일 영상 검수와 승인 E2E 통과
- [ ] 기존 `site/` 공개 페이지 회귀 테스트 통과
- [ ] 키/토큰/개인정보가 번들, 로그, git에 없는지 점검

## 후속 릴리스

### 2차: Instagram

승인 레코드 소비, 미디어 컨테이너 생성, 상태 polling, 게시, permalink 저장,
중복 게시 방지와 수동 복구를 구현한다.

### 3차: 광고와 분석

A/B 소재 생성, 예산 승인, 캠페인 생성, Insights 수집, 비교 분석과 다음 콘텐츠
생성 피드백을 구현한다.
