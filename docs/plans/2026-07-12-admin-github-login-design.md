# 오늘의신기템 관리자 GitHub 로그인 설계

날짜: 2026-07-12  
상태: 사용자 승인됨

## 목적

관리자 페이지의 이메일 매직링크 로그인을 GitHub OAuth 로그인으로 교체한다.
이메일 발송 한도와 링크 전달 지연을 제거하고, GitHub 계정의 2단계 인증과
패스키를 활용해 한 명의 관리자만 편리하게 접속하도록 한다.

## 선택한 방식

- Supabase Auth의 GitHub OAuth provider를 사용한다.
- 로그인 화면은 `GitHub로 계속하기` 버튼 하나만 제공한다.
- GitHub OAuth App의 callback은 Supabase Auth callback URL로 지정한다.
- 인증 완료 후에는 `https://todaysingi.netlify.app/admin/`으로 돌아온다.
- GitHub Client Secret은 Supabase에만 저장하며 Git, Netlify, 브라우저 번들에
  포함하지 않는다.

고정 비밀번호 방식은 별도의 비밀번호 생성·보관·재설정 책임이 생기므로
채택하지 않는다. Supabase 직접 Passkey는 현재 Beta이며 최초 인증이 필요해
이번 범위에서 제외한다.

## 인증과 권한 흐름

1. 비로그인 사용자가 관리자 페이지에서 GitHub 로그인 버튼을 누른다.
2. 프런트엔드는 `supabase.auth.signInWithOAuth`를 GitHub provider와 고정된
   운영 redirect URL로 호출한다.
3. GitHub가 사용자를 인증하고 Supabase callback으로 돌려보낸다.
4. Supabase는 같은 검증 이메일의 기존 사용자와 GitHub identity를 자동으로
   연결한다.
5. 관리자 앱은 세션의 이메일과 GitHub provider 포함 여부를 확인한다.
6. 데이터베이스 RLS는 허용된 Supabase 사용자 UUID만 접근시킨다.
7. 허용되지 않은 계정은 세션을 종료하고 데이터 요청 전에 접근 거부 화면을
   표시한다.

## 관리자 UUID 허용 목록

이메일 문자열만 검사하던 기존 RLS helper를 UUID 기반 허용 목록으로 강화한다.

- `admin_users(user_id uuid primary key)` 테이블을 추가한다.
- 테이블은 service role만 변경할 수 있고 일반 클라이언트에는 노출하지 않는다.
- `is_todaysingi_admin()`은 `auth.uid()`가 허용 목록에 있는지만 확인한다.
- 기존 `plusmg@gmail.com` 사용자의 UUID를 migration에 고정하지 않고 배포 시
  service role을 이용한 별도 운영 명령으로 등록한다.
- GitHub identity가 기존 사용자에 자동 연결되면 UUID가 유지된다.
- 자동 연결되지 않으면 새 GitHub 사용자를 확인한 후 명시적으로 허용하고 기존
  이메일 사용자는 허용 목록에서 제거한다.

## UI와 오류 처리

- 기존 Atelier Zero 로그인 레이아웃과 시각 언어를 유지한다.
- 버튼에는 GitHub 아이콘, 진행 상태, 키보드 포커스 상태를 제공한다.
- OAuth 시작 실패, 사용자의 취소, callback 실패, 허용되지 않은 계정을 서로
  구분해 한국어 메시지로 표시한다.
- 중복 클릭을 막기 위해 OAuth 요청 중에는 버튼을 비활성화한다.
- 인증 실패 시 관리자 데이터나 demo 데이터를 노출하지 않는다.
- 로그아웃은 기존 Supabase 세션 종료 동작을 유지한다.

## 설정 순서

1. GitHub OAuth App을 만들고 홈페이지 URL과 Supabase callback URL을 등록한다.
2. Client ID와 Client Secret을 Supabase GitHub provider에 저장한다.
3. GitHub 로그인 UI와 callback 처리를 배포한다.
4. 최초 GitHub 로그인과 기존 계정 자동 연결 여부를 확인한다.
5. 확인된 사용자 UUID를 관리자 허용 목록에 등록한다.
6. 허용 계정·비허용 계정·새로고침 세션을 검증한다.
7. 검증이 끝난 뒤 이메일 로그인을 UI와 Supabase provider에서 비활성화한다.

이메일 provider 비활성화는 GitHub 로그인이 실제 운영 환경에서 성공한 뒤에만
수행한다. 이를 통해 설정 오류로 관리자가 완전히 잠기는 상황을 피한다.

## 테스트

- OAuth 요청이 provider `github`와 정확한 운영 redirect URL을 사용한다.
- 요청 중 중복 클릭이 차단되고 오류가 사용자에게 표시된다.
- GitHub provider가 없는 세션은 접근이 거부된다.
- 허용 목록에 없는 UUID는 모든 비공개 테이블 RLS에서 거부된다.
- 허용된 UUID는 기존 대시보드 조회와 작업 요청을 수행할 수 있다.
- 로그인 후 새로고침해도 세션이 유지되고 로그아웃 후에는 접근할 수 없다.
- Netlify `/admin/*` SPA fallback과 기존 공개 링크 사이트가 회귀하지 않는다.
- Client Secret, service role, OAuth token이 빌드 결과와 Git diff에 없다.

## 완료 기준

1. 운영 관리자 페이지에 이메일 로그인 UI가 없다.
2. 지정된 GitHub 계정으로 한 번의 OAuth 흐름을 거쳐 로그인할 수 있다.
3. 다른 GitHub 계정은 관리자 데이터에 접근할 수 없다.
4. 이메일 발송 한도와 무관하게 반복 로그인할 수 있다.
5. GitHub·Supabase 비밀값이 클라이언트와 저장소에 노출되지 않는다.
6. 기존 관리자 기능과 공개 사이트 테스트가 모두 통과한다.
