# 오늘의신기템 관리자 GitHub 로그인 구현 계획

설계 정본: `docs/plans/2026-07-12-admin-github-login-design.md`

## 목표와 경계

관리자 로그인 UI를 이메일 매직링크에서 GitHub OAuth로 교체하고, 데이터베이스
권한을 이메일 문자열이 아닌 Supabase 사용자 UUID 허용 목록으로 강화한다.
GitHub OAuth App의 Client Secret은 Supabase에만 저장한다.

이메일 provider는 GitHub 운영 로그인이 검증되기 전까지 비상 복구 수단으로
유지하되 관리자 UI에서는 제거한다. 운영 검증 후 Supabase에서 비활성화한다.

## 1. 실패하는 인증 계약 테스트

- [ ] `tests/test_admin_auth.py`를 추가한다.
- [ ] 로그인 컴포넌트가 `signInWithOAuth`, provider `github`, 고정 redirect
  설정을 사용한다고 검증한다.
- [ ] 이메일 OTP 호출과 매직링크 문구가 제거된다고 검증한다.
- [ ] 앱이 관리자 이메일뿐 아니라 GitHub provider를 확인한다고 검증한다.
- [ ] 새 migration이 `admin_users`, `auth.uid()`, service-role 전용 쓰기 권한을
  정의한다고 검증한다.
- [ ] 테스트를 실행해 구현 전 실패를 확인한다.

명령: `python -m pytest tests/test_admin_auth.py -q`

## 2. UUID 기반 관리자 RLS

- [ ] `supabase/migrations/202607120002_admin_github_auth.sql`을 추가한다.
- [ ] `public.admin_users(user_id uuid)` 테이블과 생성 시각을 정의한다.
- [ ] anon/authenticated의 직접 접근을 철회하고 service role만 변경 가능하게 한다.
- [ ] `public.is_todaysingi_admin()`을 `auth.uid()` 허용 목록 검사로 교체한다.
- [ ] 기존 모든 정책이 helper를 공유하므로 정책 재작성 없이 강화되는지 확인한다.
- [ ] migration 계약 테스트를 통과시킨다.

## 3. 관리자 허용 명령

- [ ] `scripts/authorize_admin.py`에 service role 기반 관리 명령을 구현한다.
- [ ] 이메일로 Supabase Auth 사용자를 찾고 GitHub identity가 연결됐는지 검증한다.
- [ ] 확인된 UUID를 `admin_users`에 멱등 upsert한다.
- [ ] 토큰과 service role 값을 출력하지 않는다.
- [ ] 순수 파싱·검증 로직을 유닛 테스트한다.

명령: `python scripts/authorize_admin.py --email plusmg@gmail.com --require-provider github`

## 4. GitHub 로그인 UI

- [ ] `admin/src/lib/auth.ts`에 redirect URL과 관리자 세션 판정 함수를 둔다.
- [ ] `Login.tsx`를 GitHub OAuth 버튼과 오류·진행 상태로 교체한다.
- [ ] GitHub 아이콘을 기존 아이콘 체계에 추가한다.
- [ ] `App.tsx`가 이메일과 GitHub provider를 모두 만족한 세션만 통과시킨다.
- [ ] `admin/.env.example`에 공개 redirect URL 변수를 문서화한다.
- [ ] callback 오류 파라미터가 있으면 접근 가능한 한국어 오류를 표시한다.

## 5. 회귀 검증

- [ ] 새 인증 테스트를 통과시킨다.
- [ ] 전체 Python 테스트를 통과시킨다.
- [ ] 관리자 TypeScript/Netlify 빌드를 통과시킨다.
- [ ] 빌드 결과에 Client Secret, service role, 토큰이 없는지 검색한다.
- [ ] 기존 공개 사이트 파일과 `products.json`이 바뀌지 않았는지 확인한다.

명령:

```text
python -m pytest tests/ -q
npm --prefix admin run build
npm --prefix admin run build:netlify
```

## 6. 외부 OAuth 설정

- [ ] GitHub OAuth App을 생성한다.
- [ ] Homepage URL을 `https://todaysingi.netlify.app/admin/`으로 지정한다.
- [ ] Callback URL을
  `https://davyotbbhgnfxpgaglki.supabase.co/auth/v1/callback`으로 지정한다.
- [ ] GitHub Client ID/Secret을 Supabase GitHub provider에 저장한다.
- [ ] Supabase redirect allow list에 운영 관리자 URL이 있는지 재확인한다.
- [ ] SQL migration을 Supabase 프로젝트에 적용한다.

Client Secret 입력은 사용자 계정의 보안 경계 안에서 수행하고 채팅, 로그,
스크린샷, 저장소에 노출하지 않는다.

## 7. 운영 E2E와 배포

- [ ] 기능 브랜치를 push하고 Netlify preview 또는 운영 배포를 확인한다.
- [ ] 지정 GitHub 계정으로 OAuth를 완료한다.
- [ ] `authorize_admin.py`로 GitHub identity가 연결된 UUID를 허용한다.
- [ ] 대시보드 조회와 작업 요청을 확인한다.
- [ ] 로그아웃, 새로고침 세션 유지, 재로그인을 확인한다.
- [ ] 비허용 계정은 UI와 RLS에서 거부되는지 확인한다.
- [ ] 성공 후 Supabase Email provider를 비활성화한다.
- [ ] main에 병합하고 Netlify 운영 배포를 최종 확인한다.

## 완료 조건

- 이메일 발송 없이 GitHub로 로그인할 수 있다.
- 허용된 UUID 외에는 관리자 데이터를 읽거나 쓸 수 없다.
- OAuth 비밀값이 Supabase 외부에 저장되지 않는다.
- 전체 테스트와 빌드가 통과하고 기존 공개 사이트가 유지된다.
