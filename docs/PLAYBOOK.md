# PLAYBOOK — 상품 1개 처리 표준 절차

쿠팡 링크 하나 → 더빙·자막 릴스 영상 + 캡션 + 사이트 게시까지의 반자동 절차.
담당: 사람 / Claude 세션 / 스크립트. 모든 진행 상태는 관제탑이 기록한다
(`python scripts/pipeline.py status` 로 언제든 확인, `dashboard`로 보드 열기).

## 0. 사전 조건 (1회)

- `pip install -r scripts/requirements.txt` + ffmpeg 설치
- **Typecast API 키**: 저장소 루트의 `.env` 파일에 `TYPECAST_API_KEY=키값` 한 줄
  (`.env.example` 참고, `.env`는 git에 올라가지 않음).
  키가 있으면 dub이 자동으로 Typecast(상업 라이선스 OK)를 쓰고,
  없으면 edge-tts 폴백(PoC 전용 — 게시 금지 경고 출력).
- 음성 고르기: `python scripts/tts.py --list-voices` → `dub.py --voice tc_...`

## 1. 상품 등록 — 사람

쿠팡에서 신기한 물건 발견하면:

    python scripts/pipeline.py new --title "상품명" --coupang-url "https://www.coupang.com/vp/products/..."

## 2. 알리 영상 확보 — 사람 + 스크립트

알리익스프레스에서 같은 상품을 찾아 URL 복사(이미지 검색 활용) 후:

    python scripts/fetch_video.py <id> --ali-url "https://ko.aliexpress.com/item/....html"

자동 추출 실패 시 안내가 뜬다. 폴백: 브라우저 F12 → Network → 영상 재생 → mp4 저장 후

    python scripts/fetch_video.py <id> --file "C:/Downloads/저장한영상.mp4"

성공하면 영상 길이와 **대본 권장 글자수**가 출력된다.

## 3. 대본 작성 — Claude 세션

Claude Code에서: "ops/assets/<id>/frames 프레임 보고 <상품명> 대본 써줘"

- 구조: 훅(첫 1~2초, 스크롤 멈춤) → 신기한 포인트 2~3개 → CTA "프로필 링크 [00N]번"
- 권장 글자수 이내(초당 5자), 짧은 구어체 문장, 낭독 텍스트만(이모지·지시문 금지)
- **숫자·번호는 한글로 표기**: "1번" → "일 번" (TTS가 "한번"으로 오독함), "2개" → "두 개"
- 저장: `ops/assets/<id>/script.txt` (UTF-8)
- 장부: `python scripts/pipeline.py advance <id> --to script_ready`

## 4. 더빙 + 자막 — 스크립트

    python scripts/dub.py <id>

- 엔진: `.env`에 키가 있으면 Typecast 자동, 강제하려면 `--engine typecast|edge`
- **톤 조절**: 기본이 차분하면 `--emotion happy` 또는 `--emotion toneup` (+`--intensity 1.5`)
- 속도: `--rate=-5%` 처럼 **반드시 = 붙여서** (공백으로 주면 argparse가 옵션으로 오해)
- 보이스 변경: Typecast는 `--voice tc_...`(목록: `python scripts/tts.py --list-voices`),
  edge는 `--voice ko-KR-InJoonNeural`(남성) 등
- 음성이 영상보다 길면 에러 — 대본을 줄이거나 `--rate "+10%"`
- 자막 빼기: `--no-subs`
- 결과: `ops/assets/<id>/final.mp4` (재생해서 확인할 것)

## 5. 캡션 작성 — Claude 세션

"[id] 캡션 써줘" — 인스타 알고리즘 스킬 기반으로 작성.

- 구조: 훅 한 줄 → 포인트 → "🔗 프로필 링크 [00N]번" → 해시태그 5~10개 → 고지문(필수):
  "이 포스팅은 쿠팡 파트너스 활동의 일환으로, 이에 따른 일정액의 수수료를 제공받습니다."
- 저장: `ops/assets/<id>/caption.txt`
- 장부: `python scripts/pipeline.py advance <id> --to caption_ready`

## 6. 릴스 게시 — 사람 (Phase 3에서 자동화 예정)

인스타 앱에서 final.mp4 업로드 + caption.txt 붙여넣기 → 게시 후:

    python scripts/pipeline.py advance <id> --to published --set reelUrl=<릴스URL>

## 7. 파트너스 링크 + 사이트 게시 — 사람 + 스크립트 (파트너스 승인 후)

쿠팡 파트너스에서 링크 생성 후:

    python scripts/add_product.py --title "상품명" --price 12900 \
        --image "<썸네일URL>" --link "https://link.coupang.com/a/..." --push
    python scripts/pipeline.py advance <id> --to linked --set partnersLink=... siteProductId=<사이트id>

## 트러블슈팅

| 증상 | 처방 |
|---|---|
| 영상 자동 추출 실패 | 2번의 --file 폴백 (개발자도구로 mp4 저장) |
| 음성이 영상보다 김 | 대본 축약(에러 메시지에 글자수 안내) 또는 `--rate "+10%"` |
| 자막이 안 붙음(경고) | TTS 타이밍 부재 폴백 — 재실행하거나 --no-subs로 진행 |
| ffmpeg 없음 | https://ffmpeg.org 설치(또는 `winget install ffmpeg`) |
| 관제탑 현황 안 맞음 | `pipeline.py advance <id> --to <단계>`로 수동 보정 |
