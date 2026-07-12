# Phase 2 콘텐츠 파이프라인 (반자동 PoC) — 설계

날짜: 2026-07-12
상태: 사용자 승인됨

## 배경과 목적

쿠팡 링크 하나에서 출발해 **더빙·자막이 입혀진 릴스용 영상 + 인스타 캡션**을 만드는 반자동 라인. 릴스 업로드(원계획 9번)는 이 Phase에서는 수동이고 Phase 3에서 API 자동화한다. 모든 단계는 완료 시 관제탑(`scripts/pipeline.py`) 장부를 자동 갱신한다.

**확정된 방식 결정:**
- 상품 발굴·알리 매칭 = 사람 (수동 모드 기본, 2026-07-12 사용자 결정)
- TTS = **edge-tts로 PoC**, 실제 게시 전 Typecast API로 전환(엔진 추상화 필수). edge-tts는 상업 라이선스가 불분명하므로 게시용으로 쓰지 않는다.
- 대본·캡션 = **Claude Code 세션에서 작성** (프레임 이미지 기반, 인스타 알고리즘 스킬 활용). API 자동화는 후기 Phase.

## 역할 분담 (한 상품 처리 흐름)

1. 사람: 쿠팡에서 신기템 발견 → `pipeline.py new` (stage: sourced)
2. 사람: 알리익스프레스에서 동일 상품 찾음 (URL 확보)
3. 스크립트 `fetch_video.py`: 영상 다운로드 → 무음화 → 프레임 추출 → (stage: video_ready)
4. Claude 세션: 프레임 + 상품 정보 보고 대본 작성 → `script.txt` → (stage: script_ready)
5. 스크립트 `dub.py`: TTS 생성 → 자막 SRT 생성 → 영상 합성 → (stage: audio_ready)
6. Claude 세션: 캡션·해시태그 작성(고지문 포함) → `caption.txt` → (stage: caption_ready)
7. 사람: 인스타 앱에서 final.mp4 + caption.txt로 릴스 게시 → `advance <id>` (stage: published)

## 작업 폴더 구조

```
ops/assets/<id>/          # git 제외 (.gitignore에 ops/assets/)
├── raw.mp4               # 원본 (fetch_video)
├── muted.mp4             # 무음화 (fetch_video)
├── frames/f01.jpg …f06.jpg  # 대본 작성용 균등 6장 (fetch_video)
├── script.txt            # 더빙 대본 (Claude 세션)
├── voice.mp3             # TTS 음성 (dub)
├── subs.srt              # 자막 (dub)
├── final.mp4             # 완성본 (dub)
└── caption.txt           # 인스타 캡션 (Claude 세션)
```

## `scripts/fetch_video.py`

```
python scripts/fetch_video.py <id> --ali-url "https://ko.aliexpress.com/item/..." [--file 수동파일.mp4]
```

- 장부에서 `<id>` 존재 확인. `ops/assets/<id>/` 생성.
- 영상 확보 전략(순서대로, 성공하면 중단):
  1. `--file` 지정 시 해당 파일을 `raw.mp4`로 복사
  2. `--ali-url` HTML을 requests로 받아(모바일 UA) mp4 URL 패턴 추출 후 다운로드
  3. `yt-dlp <ali-url>` 시도
  4. 전부 실패: 수동 다운로드 안내 출력(브라우저 개발자도구 네트워크 탭에서 mp4 저장 → `--file`로 재실행), exit 1
- 무음화: `ffmpeg -y -i raw.mp4 -c:v copy -an muted.mp4` (재인코딩 없음 — 원본 음악 저작권도 이 단계에서 제거됨)
- 프레임: ffprobe로 길이(초) 확인 → 균등 6장 `frames/f01~06.jpg`
- 출력: 영상 길이와 **대본 권장 글자수**(초당 5자 기준, 훅 포함) 안내
- 장부 갱신: `advance <id> --to video_ready --set aliUrl=... mutedVideo=...` (pipeline 모듈 import 호출)
- 멱등성: 재실행 시 기존 파일 덮어씀(`-y`), 장부는 `--to`라 중복 진행 안전

## 대본 작성 절차 (Claude 세션 — PLAYBOOK에 수록)

- 입력: `frames/*.jpg`(Read), 상품 제목·쿠팡 페이지 특징, 영상 길이·권장 글자수
- 구조: **훅(첫 1~2초, 스크롤 멈춤용)** → 신기한 포인트 2~3개 → CTA("프로필 링크 [00N]번")
- 존댓말 짧은 구어체, 문장은 자막 블록 단위로 짧게(≤14자 지향)
- 저장: `ops/assets/<id>/script.txt` (UTF-8, 순수 낭독 텍스트만 — 지시문·이모지 금지)
- 장부: `advance <id> --to script_ready`

## `scripts/dub.py`

```
python scripts/dub.py <id> [--voice ko-KR-SunHiNeural] [--rate "+0%"] [--no-subs]
```

- `script.txt` 필수(없으면 안내 후 exit 1).
- **TTS 추상화**: `synthesize(text, voice, rate, out_mp3) -> list[Word]` 함수 하나가 엔진 경계. v1 구현은 edge-tts(비동기 stream: 오디오 청크 저장 + `WordBoundary` 이벤트로 단어 타이밍 수집). Typecast 전환 시 이 함수만 교체.
- `Word = {text, start_s, end_s}` (100ns 오프셋을 초로 변환).
- **SRT 생성**(`generate_srt(words, max_chars=14)` 순수 함수): 단어를 이어 붙이다 문장부호(.?!) 또는 max_chars 초과 시 블록 분리. 타임코드 `HH:MM:SS,mmm`.
- 길이 검사: 음성 길이 > 영상 길이면 에러 — "대본을 N자 줄이거나 --rate +10% 사용" 안내(자동으로 자르지 않는다 — 대본이 잘리면 콘텐츠가 망가짐).
- 합성(ffmpeg):
  - 자막 포함(기본): `ffmpeg -y -i muted.mp4 -i voice.mp3 -map 0:v -map 1:a -vf subtitles=subs.srt:force_style='FontSize=14,Bold=1,PrimaryColour=&HFFFFFF&,OutlineColour=&H000000&,Outline=2,MarginV=40' -c:v libx264 -preset veryfast -crf 20 -c:a aac -shortest final.mp4`
  - `--no-subs`: `-c:v copy`로 재인코딩 없이 오디오만 결합
  - Windows의 subtitles 필터 경로(콜론) 문제 회피를 위해 **ffmpeg는 `ops/assets/<id>/`를 cwd로 실행**하고 상대 파일명만 사용
- 장부 갱신: `advance <id> --to audio_ready --set finalVideo=... voice=<보이스명>`

## 캡션 작성 절차 (Claude 세션 — PLAYBOOK에 수록)

- 구조: 훅 한 줄 → 상품 포인트 → "🔗 프로필 링크 [00N]번" → 해시태그(연관 5~10개) → **고지문 필수**: "이 포스팅은 쿠팡 파트너스 활동의 일환으로, 이에 따른 일정액의 수수료를 제공받습니다."
- 인스타 알고리즘 스킬(anthropic-skills:instagram-algorithm) 참조해 작성
- 저장: `caption.txt`, 장부: `advance <id> --to caption_ready`

## `docs/PLAYBOOK.md`

상품 1개 처리의 운영 매뉴얼: 위 7단계를 명령어 복사-붙여넣기 수준으로 수록 + 대본/캡션 작성 기준 + 트러블슈팅(영상 추출 실패, 음성이 김, ffmpeg 없음).

## 의존성

`scripts/requirements.txt`: `edge-tts`, `yt-dlp`, `requests` (+ 시스템: ffmpeg — 이미 설치 확인됨). pytest는 기존.

## 비범위 (Phase 3+)

릴스 API 업로드, 파트너스 링크 API 전환, 광고, Typecast 실연동(추상화 자리만), 알리 이미지 검색 자동화, Anthropic API 대본 자동화.

## 엣지 케이스

- ffmpeg/ffprobe 부재: 설치 안내 후 exit 1
- 알리 상품에 영상이 없음(이미지만): 전략 4의 수동 안내로 수렴
- script.txt가 비어 있음: 에러
- 음성이 영상보다 김: 위 길이 검사 에러(자동 절단 금지)
- 재실행: 산출물 덮어쓰기, 장부는 --to로 멱등

## 검증 계획

1. pytest(순수 로직): ffmpeg 명령 조립 2종, `generate_srt`(블록 분리·타임코드 포맷·문장부호 경계), 초→타임코드 변환, 대본 권장 글자수 계산, 알리 HTML mp4 URL 추출 정규식(샘플 조각).
2. 통합 스모크: ffmpeg로 3초 테스트 영상을 로컬 생성 → 가짜 대본으로 dub.py 전체 실행(edge-tts 실호출 1회) → final.mp4 생성·오디오 트랙 존재 확인(ffprobe).
3. E2E: 실상품 1개(사용자 제공 쿠팡+알리 링크)로 7단계 전부 → 첫 완성 영상.
