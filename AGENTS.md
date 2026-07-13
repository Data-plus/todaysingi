# 오늘의신기템 (todaysingi) — 에이전트 컨텍스트

쿠팡 파트너스 수익화 프로젝트. 신기한 물건을 골라 → 알리익스프레스 영상으로 더빙 숏츠를 만들어 → 인스타그램 릴스에 올리고 → 링크 허브 사이트(파트너스 링크)로 구매를 유도한다. 소유자: plusmg@gmail.com, 인스타 @anfluencer.ai.

## 아키텍처

```
site/       공개 배포 대상 (Netlify가 이 폴더만 서빙, netlify.toml publish=site)
  index.html/style.css/app.js  정적 원페이지 (빌드 도구 없음, 프레임워크 없음)
  products.json                사이트의 유일한 데이터 소스 (profile + products[])
  media/<id>.mp4               로컬 폴백용 레거시 영상 (Cloud 게시에는 사용하지 않음)
ops/        비공개 로컬 폴백 데이터 (Cloud 운영의 진실 소스는 Supabase)
  pipeline.json                로컬 CLI용 파이프라인 장부
  assets/<id>/                 작업 산출물 (raw/muted/frames/script/voice/subs/final/caption) — gitignore
scripts/    운영 CLI와 Cloud 공유 유틸리티 (Python 중심)
  pipeline.py      관제탑: new/advance/status/dashboard (9단계: sourced→…→analyzed)
  fetch_video.py   알리 영상 다운로드→무음화→프레임 6장→권장 글자수 안내
  dub.py           TTS 더빙+SRT 자막 번인 (ffmpeg, cwd=작업폴더로 실행)
  tts.py           TTS 엔진 경계: Typecast(기본)/edge-tts(PoC 폴백), --list-voices
  publish_reel.py  릴스 API 게시: site/media 호스팅→컨테이너→폴링→media_publish
  add_product.py   사이트 상품 추가 (검증+append, --push면 배포까지)
admin/      React/Vite 온라인 Control Desk (GitHub OAuth + Supabase Auth)
worker/     DB 큐·Storage 기반 Cloud Run 콘텐츠/GA4/게시 Worker
dispatcher/ Supabase JWT를 재검증하고 Cloud Run Job만 실행하는 FastAPI 서비스
supabase/   RLS migration + 관리자용 dispatch-worker Edge Function
tests/      pytest 211개 (순수 로직 중심 — 외부 API는 수동 E2E)
prompts/    대본·캡션 생성 프롬프트 (script.md, caption.md) — 스타일 변경은 여기만 수정
docs/       PLAYBOOK.md(운영 매뉴얼) + superpowers/specs·plans(설계 문서)
```

- 배포: `git push` → Netlify 자동 배포(~40초). https://todaysingi.netlify.app
- 원격: https://github.com/Data-plus/todaysingi (public — **비밀·전략 데이터를 site/나 커밋에 넣지 말 것**)
- 비밀키: 로컬은 저장소 루트 `.env`, Cloud는 Google Secret Manager. 저장소·Netlify 번들·로그에 실제 값을 넣지 않는다.
- Cloud 주요 환경변수: `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `TYPECAST_API_KEY`, `TYPECAST_VOICE_ID`, `LLM_API_URL`, `LLM_API_KEY`, `LLM_MODEL`, `GA4_PROPERTY_ID`, `INSTAGRAM_ACCOUNT_ID`, `INSTAGRAM_ACCESS_TOKEN`, `NETLIFY_BUILD_HOOK_URL`.

## 현재 상태 (2026-07-13 기준)

완료:
- 사이트 라이브(GA4 클릭추적 G-1C612TT8W0, 검색창, 파트너스 고지문) + 관제탑 + 대시보드
- 콘텐츠 파이프라인 전 구간 실전 검증: 첫 상품 [001] 불쏘는 마법지팡이(28,500원)를
  영상 수집→트림·세로크롭→Typecast 더빙(Seohyeon, rate=-5%)→자막→캡션→**릴스 API 게시 성공**
  → https://www.instagram.com/reel/DarULTkCZk5/ → 사이트 [001] 게시
- 관제탑 장부: 아이템 [1] stage=linked (다음: 광고 2종 세팅·집행)
- 첫 게시 피드백 반영: 대본 숫자는 한글 표기("일 번"), dub --emotion/--intensity 옵션
- Supabase에 GA4 집계·Cloud 큐·private pipeline-assets·관리자 입력/승인 schema 적용 완료
- 원격 콘텐츠 전 단계, 게시 성공 후 미디어 삭제, 실패 자산 7일 정리, GA4 Data API 수집 코드 완료
- 관리자 성과 화면은 실제 GA4 클릭·세션·사용자·상품·유입 데이터를 표시하고 수동 동기화 가능
- Worker/dispatcher 이미지는 non-root, FFmpeg, Chromium, health smoke test까지 통과

남은 로드맵:
- **Phase 4**: Meta Marketing API로 광고 2종 A/B 집행·분석·저장 (토큰에 ads_management 권한 이미 있음)
- Cloud Run 실제 리소스 생성: 전용 결제 프로젝트 선택, GA4 Property Viewer 연결, Edge Function 배포
- 백로그: fetch_video에 트림/세로크롭 내장(현재 수동 ffmpeg), Playwright 기반 알리 영상 추출 자동화(현 requests 방식은 JS셸에 막힘 — --file 폴백 사용), pipeline에 stage 이동 없는 --set 명령, IG 토큰(60일) 만료 갱신 자동화, 쿠팡 정보 자동 수집(Playwright로 검증됨)

## 컨벤션 (지킬 것)

- 작업 흐름: 스펙(docs/superpowers/specs) → 계획(plans) → **TDD**(테스트 먼저) → 브랜치 → main 머지
- 커밋 메시지 한국어, `feat:/fix:/docs:/chore:/refactor:` 프리픽스
- Python은 표준 라이브러리 우선(현재 외부 의존: edge-tts, yt-dlp, requests뿐), 파일 저장은 UTF-8 + LF + `ensure_ascii=False`
- 테스트: `python -m pytest tests/ -q` — 순수 로직만 유닛테스트, 네트워크·ffmpeg는 스모크/E2E로
- 사이트·캡션에 쿠팡 파트너스 고지문 필수: "이 포스팅은 쿠팡 파트너스 활동의 일환으로, 이에 따른 일정액의 수수료를 제공받습니다." 캡션 첫 해시태그는 `#광고`.
- **DM·메신저·단체 메시지 자동 발송 기능은 어떤 Phase에서도 구현 금지** — 수신 동의 없는 발송은 정보통신망법상 불법 스팸(과태료 3천만원/형사처벌, 파트너스 규정 명시). 참여 유도는 시청자의 자발적 행위까지만.
- products.json 스키마 변경 금지(파이프라인·렌더러·CLI가 공유): id/title/price/image/link/addedAt/active
- edge-tts는 PoC 전용(상업 라이선스 불분명) — 게시용은 Typecast만
- dub.py의 `--rate`는 `--rate=-5%` 형식(= 필수)
- 대본·캡션 작성 규칙의 정본은 `prompts/script.md`·`prompts/caption.md` — 문서·코드에 규칙을 중복 기재하지 말 것

## 자주 쓰는 명령

```
python scripts/pipeline.py status                       # 현황 + 다음 할 일
python scripts/pipeline.py new --title .. --coupang-url ..
python scripts/fetch_video.py <id> --ali-url .. [--file 수동파일]
python scripts/dub.py <id> [--voice tc_..] [--emotion toneup] [--rate=-5%]
python scripts/publish_reel.py <id> [--dry-run]
python scripts/add_product.py --title .. --price .. --image .. --link .. --push
python -m http.server -d site 8765                      # 로컬 프리뷰
python -m worker.cloud_main --drain                     # Cloud 큐 로컬 스모크
python -m worker.cloud_main --sync-ga4                  # GA4 즉시 동기화
docker build -t todaysingi-worker .                     # Worker 이미지 검증
```

온라인 운영·배포: `docs/CLOUD_RUN_RUNBOOK.md`, 로컬 폴백: `docs/PLAYBOOK.md`
