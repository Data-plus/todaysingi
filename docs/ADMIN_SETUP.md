# 온라인 관리자 연결

관리자 프런트엔드와 Worker는 코드가 준비돼 있으며, 아래 설정 후 데모 모드에서
실데이터 모드로 전환된다. 비밀값은 공개 저장소에 커밋하지 않는다.

## 1. Supabase 프로젝트

1. 새 Supabase 프로젝트를 만든다.
2. SQL Editor에서
   `supabase/migrations/202607120001_admin_control_plane.sql`을 실행한다.
3. Authentication에서 공개 회원가입을 끄고 `plusmg@gmail.com` 사용자만 만든다.
4. URL Configuration의 허용 redirect URL에 로컬 주소와 최종 관리자 주소를 넣는다.

## 2. 환경변수

저장소 루트 `.env`에 Worker 전용 값을 추가한다.

```dotenv
SUPABASE_URL=https://프로젝트.supabase.co
SUPABASE_SERVICE_ROLE_KEY=서버전용키
TODAYSINGI_WORKER_ID=main-pc
```

`SUPABASE_SERVICE_ROLE_KEY`는 브라우저·Netlify 프런트 환경변수에 절대 넣지 않는다.

로컬 `admin/.env.local`에는 공개 가능한 브라우저 값을 넣는다.

```dotenv
VITE_SUPABASE_URL=https://프로젝트.supabase.co
VITE_SUPABASE_ANON_KEY=anon-key
VITE_ADMIN_EMAIL=plusmg@gmail.com
```

## 3. 첫 동기화와 Worker

```powershell
python worker/main.py --sync --once
python worker/main.py
```

첫 명령은 `ops/pipeline.json`의 `[001]`을 Supabase에 올리고 연결을 검사한다.
두 번째 명령은 PC가 켜져 있는 동안 작업 큐를 처리한다. Ctrl+C로 안전하게 종료한다.

## 4. 관리자 개발 확인

```powershell
cd admin
npm run dev
```

환경변수가 없으면 DEMO MODE, 있으면 이메일 magic-link 로그인 화면이 나온다.
로그인 후 상품·작업·Worker 상태가 Supabase 실데이터로 표시된다.

## 5. 작업 흐름

1. 외부 관리자에서 상품 등록
2. `create_product` 작업이 큐에 저장됨
3. PC Worker가 기존 `pipeline.py new` 실행
4. Worker가 `pipeline.json`을 다시 Supabase에 동기화
5. Typecast 재더빙 요청 시 기존 `dub.py` 실행 후 상태·로그 동기화

Instagram 게시 작업은 DB의 `approved_at`이 없으면 Worker에서도 거부한다.
