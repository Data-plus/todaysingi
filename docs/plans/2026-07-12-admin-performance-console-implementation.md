# 오늘의신기템 성과 중심 관리자 콘솔 구현 계획

설계 정본: `docs/plans/2026-07-12-admin-performance-console-design.md`

## 목표와 경계

기존 GitHub 로그인과 Supabase RLS를 유지하면서 관리자 앱을 실제 화면 전환,
상품 상세, 작업 제어, 외부 데이터 연결 상태를 갖춘 운영 콘솔로 교체한다.

이번 구현에서 숫자로 보여주는 데이터는 현재 Supabase에 존재하는 상품, 작업,
Worker 데이터뿐이다. GA4, 쿠팡 파트너스, Meta 지표는 API가 연결될 때까지
nullable로 유지하고 UI에는 `연결 대기`를 표시한다.

## 1. 실패하는 관리자 콘솔 계약 테스트

파일:

- 추가: `tests/test_admin_dashboard.py`

작업:

- [ ] 여섯 개 화면 ID와 실제 화면 컴포넌트가 존재하는지 검사한다.
- [ ] 레거시 편집형 히어로·콜라주 구조가 제거되는지 검사한다.
- [ ] 외부 성과 값이 nullable이며 `연결 대기` 상태를 갖는지 검사한다.
- [ ] 작업 취소·재시도와 파이프라인 동기화 함수 계약을 검사한다.
- [ ] 상품 상세 패널과 접근 가능한 닫기 동작을 검사한다.
- [ ] 구현 전 테스트 실패를 확인한다.

명령:

```text
python -m pytest tests/test_admin_dashboard.py -q -p no:cacheprovider
```

## 2. 관리자 도메인 타입과 파생 로직

파일:

- 추가: `admin/src/types/admin.ts`
- 추가: `admin/src/lib/dashboard.ts`
- 수정: `admin/src/lib/controlDesk.ts`

작업:

- [ ] 상품 원본 필드, 상세 작업, Worker, 자산, 연결 상태 타입을 정의한다.
- [ ] 외부 성과는 `number | null`로 정의한다.
- [ ] 단계·작업·상태 한국어 라벨을 한 곳에서 관리한다.
- [ ] 날짜·가격·진행률 포맷과 운영 요약 계산을 순수 함수로 분리한다.
- [ ] 상품, 작업, Worker, 자산을 병렬 조회한다.
- [ ] 상품 ID로 관련 작업과 자산을 연결한다.
- [ ] Supabase 오류를 첫 번째 실패 원인으로 전파한다.

## 3. 안전한 작업 큐 액션

파일:

- 수정: `admin/src/lib/controlDesk.ts`

작업:

- [ ] `queued` 작업만 `cancelled`로 변경하는 함수를 추가한다.
- [ ] `failed`·`cancelled` 작업만 새 작업으로 재요청한다.
- [ ] 재요청은 원본 payload와 새 멱등 키를 사용하고 기존 기록을 보존한다.
- [ ] 파이프라인 동기화 작업을 중복되지 않는 멱등 키로 추가한다.
- [ ] 외부 부작용 작업은 일반 재시도에서 차단한다.
- [ ] 액션 완료 후 전체 데이터를 다시 읽는다.

## 4. 앱 셸과 실제 화면 전환

파일:

- 추가: `admin/src/components/AppShell.tsx`
- 추가: `admin/src/components/StatusBadge.tsx`
- 추가: `admin/src/components/MetricCard.tsx`
- 수정: `admin/src/components/Icon.tsx`
- 수정: `admin/src/App.tsx`

작업:

- [ ] 사이드바, 모바일 메뉴, 상단 도구막대를 구현한다.
- [ ] 개요·상품·작업 큐·성과 분석·광고·연동 설정 화면을 실제로 전환한다.
- [ ] 화면 ID를 URL hash와 양방향 동기화한다.
- [ ] 전체 검색어와 신규 상품 대화상자를 전역에서 공유한다.
- [ ] 로딩, 오류, 다시 시도, 마지막 새로고침 상태를 구현한다.
- [ ] 기존 GitHub 인증 판정과 로그아웃을 유지한다.

## 5. 개요와 상품 관리

파일:

- 추가: `admin/src/pages/OverviewPage.tsx`
- 추가: `admin/src/pages/ProductsPage.tsx`
- 추가: `admin/src/components/ProductDrawer.tsx`

작업:

- [ ] 실제 상품·작업·Worker 운영 KPI를 표시한다.
- [ ] 외부 성과 KPI는 가짜 0 없이 `연결 대기`로 표시한다.
- [ ] 상품 성과 표와 최근 작업 표를 구현한다.
- [ ] 상품 검색, 단계, 활성 상태 필터를 구현한다.
- [ ] 상품 행 선택 시 상세 drawer를 연다.
- [ ] 상세에 링크, 단계, 관련 자산, 관련 작업, 다음 액션을 표시한다.
- [ ] 더빙 재생성은 기존 `enqueueDub`를 사용한다.
- [ ] 미구현 게시·광고 동작은 사유가 있는 비활성 버튼으로 표시한다.

## 6. 작업 큐 화면

파일:

- 추가: `admin/src/pages/JobsPage.tsx`

작업:

- [ ] 상태 요약과 작업 상태 필터를 구현한다.
- [ ] 진행률, Worker, 시도 횟수, 오류 요약을 표시한다.
- [ ] payload/result 상세를 펼쳐 볼 수 있게 한다.
- [ ] 허용 상태에서만 취소·재시도 버튼을 활성화한다.
- [ ] 재시도 금지 작업에는 이유를 표시한다.
- [ ] 파이프라인 동기화 요청 버튼을 실제로 연결한다.

## 7. 성과·광고·연동 설정 화면

파일:

- 추가: `admin/src/pages/PerformancePage.tsx`
- 추가: `admin/src/pages/AdsPage.tsx`
- 추가: `admin/src/pages/SettingsPage.tsx`

작업:

- [ ] GA4, 쿠팡, Meta 서비스별 연결 상태 카드를 구현한다.
- [ ] 쿠팡 최종 승인 전 필요한 조건을 표시한다.
- [ ] GA4 Measurement ID와 Data API 자격 증명의 차이를 설명한다.
- [ ] 차트 대신 데이터 연결 전용 빈 상태를 표시한다.
- [ ] 광고 생성·집행은 확인 가능한 비활성 사유를 제공한다.
- [ ] Supabase와 Worker의 실제 상태를 설정 화면에 표시한다.
- [ ] 어떠한 비밀키 값도 렌더링하지 않는다.

## 8. 운영 콘솔 시각 시스템과 반응형

파일:

- 수정: `admin/src/styles.css`

작업:

- [ ] 레거시 큰 세리프 히어로와 콜라주 CSS를 제거한다.
- [ ] 중립 배경, 흰 표면, 슬레이트 텍스트, 오렌지 포인트로 교체한다.
- [ ] 조밀한 KPI 카드, 표, 상태 배지, drawer, dialog 스타일을 구현한다.
- [ ] 키보드 focus, hover, disabled, loading 상태를 구분한다.
- [ ] 980px 이하에서 모바일 내비게이션과 카드형 표를 제공한다.
- [ ] 640px 이하에서 drawer를 전체 화면으로 전환한다.
- [ ] `prefers-reduced-motion`을 존중한다.

## 9. 회귀 검증과 로컬 UI 검사

파일:

- 필요 시 수정: `tests/test_admin_dashboard.py`

작업:

- [ ] 새 관리자 계약 테스트를 통과시킨다.
- [ ] 전체 Python 테스트를 통과시킨다.
- [ ] TypeScript 및 Vite 빌드를 통과시킨다.
- [ ] Netlify 관리자 빌드를 통과시킨다.
- [ ] 빌드 결과에 service role, OAuth secret, API token이 없는지 확인한다.
- [ ] 로컬 관리자에서 데스크톱과 모바일 화면을 시각 검수한다.
- [ ] 기존 로그인, 신규 상품 등록, 더빙 요청을 회귀 확인한다.
- [ ] 공개 `site/index.html`과 `site/products.json`이 의도치 않게 바뀌지 않았는지 확인한다.

명령:

```text
python -m pytest tests/ -q -p no:cacheprovider
npm --prefix admin run build
npm --prefix admin run build:netlify
```

## 10. 커밋과 배포

- [ ] 테스트, 데이터 계층, 셸, 화면, 스타일 단위로 논리적인 한국어 커밋을 만든다.
- [ ] 기능 브랜치를 원격에 push한다.
- [ ] `main`에 병합하고 Netlify 배포를 확인한다.
- [ ] 운영 URL에서 GitHub 로그인과 실제 Supabase 데이터 렌더링을 확인한다.
- [ ] 쿠팡 API 승인 전 성과 값이 모두 `연결 대기`로 보이는지 확인한다.

## 완료 조건

- 관리자 첫 화면이 랜딩 페이지가 아니라 실제 운영 콘솔로 보인다.
- 모든 내비게이션과 활성 버튼이 실제 동작한다.
- 상품, 작업, Worker의 실제 상태를 조회하고 안전한 작업을 실행할 수 있다.
- 상품별 상세와 성과 표 구조가 준비되어 있다.
- 외부 API 미연결 값은 가짜 숫자가 아닌 명확한 연결 상태로 보인다.
- 전체 테스트와 빌드가 통과하고 기존 공개 사이트와 인증이 유지된다.
