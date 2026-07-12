# 오늘의신기템 관제탑(ops) — 파이프라인 통합 관리 설계

날짜: 2026-07-12
상태: 사용자 승인됨 (A안: 같은 repo에서 site/ops 분리)

## 배경과 목적

15단계 자동화 파이프라인에서 상품 하나가 "발굴 → 영상 → 릴스 → 링크 → 광고 → 분석"을 거치는 동안, **어디까지 진행됐고 산출물이 어디 있으며 성과가 어땠는지 기록하는 단일 장부가 없다.** `site/products.json`은 11번(사이트 게시)의 결과만 담는다. 관제탑은 그 장부와 이를 보는 화면을 제공한다. Phase 2부터 만들 파이프라인 스크립트들은 전부 이 장부에 상태를 기록한다.

**공개 경계(핵심 제약):** Netlify는 publish 디렉터리를 통째로 공개한다. 관제 장부에는 광고 성과·전략 노트가 담기므로 **배포 대상(site/)과 관제 데이터(ops/)를 물리적으로 분리**한다. 배포 전인 지금이 구조 변경의 최적 시점이다.

## 요구사항 (v1 범위)

- 아이템(상품)별 파이프라인 단계 추적 + 산출물 경로/링크 기록 + 타임스탬프 이력
- CLI: `new`(아이템 생성), `advance`(단계 진행 + 데이터 기록), `status`(터미널 현황표 + 다음 할 일), `dashboard`(정적 HTML 보드 생성·열기)
- 대시보드: 단계별 컬럼 보드, 조회 전용, 서버 없이 파일로 열림(데이터 인라인)
- 기존 사이트 파일을 `site/`로 이동하고 Netlify publish를 `site`로 지정

**비범위(v2 이후):** 조작형 웹 UI, 성과 자동 수집(Meta/GA4 API — Phase 3~4), Notion 미러링, 단계 자동 연쇄 실행, 인증.

## 저장소 구조

```
todaysingi/
├── netlify.toml            # [build] publish = "site"
├── site/                   # 공개 배포 대상 (기존 5개 파일 이동)
│   ├── index.html
│   ├── style.css
│   ├── app.js
│   ├── products.json
│   └── favicon.svg
├── ops/
│   ├── pipeline.json       # 관제 장부 = 진실 소스 (커밋 대상)
│   └── dashboard.html      # 생성물 (.gitignore)
├── scripts/
│   ├── add_product.py      # 기본 경로만 site/products.json으로 변경
│   └── pipeline.py         # 관제 CLI (신규, 표준 라이브러리만)
├── tests/
│   ├── test_add_product.py
│   └── test_pipeline.py
└── docs/superpowers/{specs,plans}/
```

## 파이프라인 단계 (15단계 → 9관제단계)

| slug | 한글 | 원계획 단계 | 완료 후 다음 할 일 |
|---|---|---|---|
| `sourced` | 상품확정 | 1–2 | 알리 영상 내려받고 무음화 |
| `video_ready` | 영상준비 | 3–4 | 재미있는 대본 작성 |
| `script_ready` | 대본완성 | 5 | TTS 생성 후 영상에 합성 |
| `audio_ready` | 더빙합성 | 6–7 | 인스타 캡션·해시태그 작성 |
| `caption_ready` | 캡션완성 | 8 | 릴스 업로드 |
| `published` | 릴스게시 | 9 | 파트너스 링크 전환 + 사이트 게시 |
| `linked` | 링크연결 | 10–11 | 광고 2종 세팅·집행 |
| `ads_running` | 광고집행 | 12–13 | 성과 비교 분석·기록 |
| `analyzed` | 분석완료 | 14–15 | (완료) |

## 장부 스키마 (`ops/pipeline.json`)

```json
{
  "items": [
    {
      "id": 1,
      "title": "접이식 미니 가습기",
      "coupangUrl": "https://www.coupang.com/vp/products/123",
      "stage": "video_ready",
      "history": [
        { "stage": "sourced", "at": "2026-07-12T15:00:00" },
        { "stage": "video_ready", "at": "2026-07-12T16:20:00" }
      ],
      "data": {
        "aliUrl": "https://ko.aliexpress.com/item/...",
        "mutedVideo": "assets/1/muted.mp4",
        "partnersLink": "https://link.coupang.com/a/xxxx",
        "siteProductId": "12",
        "abResult": "A승 - CTR 2.1% vs 1.3%"
      },
      "note": ""
    }
  ]
}
```

규칙:
- `id`: 1부터 증가(max+1, 비어 있으면 1). 사이트 상품 id와 별개(연결은 `data.siteProductId`).
- `stage`: 9개 slug 중 하나. `history`는 도달한 단계와 시각의 append-only 로그.
- `data`: 자유 키-값(문자열). 단계별 산출물 스키마를 조이지 않는다 — Phase 2~4에서 필드가 늘어도 스키마 변경 없음.
- 검증: `title` 비어 있으면 안 됨, `coupangUrl`은 `https://` 시작, 동일 `coupangUrl` 중복 생성 거부.
- 저장: UTF-8, `ensure_ascii=False`, indent 2, LF.

## CLI (`scripts/pipeline.py`)

```
python scripts/pipeline.py new --title "제목" --coupang-url "https://..." [--note "..."]
python scripts/pipeline.py advance <id> [--to <slug>] [--set 키=값 ...]
python scripts/pipeline.py status
python scripts/pipeline.py dashboard [--no-open]
```

- `new`: 검증 후 아이템 추가(stage=`sourced`, history 1건). 출력: `등록됨: [1] 제목 (상품확정)`.
- `advance`: 기본은 다음 단계로 1칸 진행. `--to`로 임의 단계 지정 가능(유효 slug 검증 — 재작업/건너뛰기 허용). `--set 키=값` 반복 가능, 값에 `=` 포함 허용(`split("=", 1)`), `data`에 병합. `analyzed`에서 `--to` 없는 advance는 에러. 존재하지 않는 id는 에러.
- `status`: 아이템별 한 줄 — `[id] 제목 | 단계(한글) | 갱신일 | 다음: ...`. 완료(analyzed) 아이템은 아래쪽에 분리 표시. 아이템 0개면 안내 문구.
- `dashboard`: `render_dashboard(data)`로 HTML 문자열 생성 → `ops/dashboard.html` 저장 → 기본으로 `webbrowser.open()` 호출(`--no-open`으로 생략).
- 종료 코드: 검증/입력 오류 시 1 + stderr 사유. Windows 콘솔 인코딩 보정(`sys.stdout.reconfigure`) 포함.
- 공용 모듈화: `load_data/save_data/new_item/advance_item/render_dashboard/next_action`은 테스트 가능한 순수 함수로 분리, `main()`은 argparse만.

## 대시보드 (`ops/dashboard.html`)

- 생성형 정적 HTML: 데이터가 `<script>const DATA = {...}</script>`로 인라인 — fetch 없음, 파일 더블클릭으로 열림.
- 레이아웃: 9단계 컬럼의 가로 스크롤 보드. 컬럼 헤더 = 한글 단계명 + 아이템 수. 카드 = `[id] 제목`, 마지막 갱신일, 정체일(마지막 갱신 이후 경과일 — 생성 시각 기준 계산), data의 URL 값은 링크로.
- 톤: 사이트와 같은 미니멀 화이트 계열(흰 배경, #191919 텍스트, 회색 보더). 조회 전용, 검색/필터 없음(v1).
- 생성 시각을 헤더에 표기.

## 기존 자산 변경

1. `git mv` — index.html, style.css, app.js, products.json, favicon.svg → `site/`
2. `netlify.toml` 신규: `[build]\n  publish = "site"`
3. `scripts/add_product.py`: `DEFAULT_FILE = REPO_ROOT / "site" / "products.json"` (그 외 불변; 테스트는 경로 주입이라 영향 없음)
4. `.gitignore`에 `ops/dashboard.html` 추가
5. README: 구조·로컬 확인 명령(`python -m http.server -d site 8765`)·관제탑 사용법 반영
6. Netlify 연동 안내: Publish directory를 `site`로 (netlify.toml이 있으므로 UI 기본값도 자동 인식됨)

## 엣지 케이스

- `ops/pipeline.json` 부재 시: `new`가 파일을 생성. 그 외 명령은 "장부가 없습니다. new로 시작하세요." 안내(exit 1).
- 잘못된 `--set` 형식(=없음): 에러 + 사유.
- `--to`에 없는 slug: 에러 + 유효 slug 목록 출력.
- 대시보드에 아이템 0개: 빈 보드 + 안내 문구.

## 검증 계획

1. pytest TDD: new(아이디 부여·검증·중복 거부), advance(순차/`--to`/`--set` 파싱·`analyzed` 정지·없는 id), 저장 라운드트립(한글), next_action 전 단계 매핑, render_dashboard 스모크(제목·단계 포함).
2. CLI 실사용: new → advance --set → status 출력 확인 → dashboard 생성.
3. 대시보드를 브라우저로 열어 보드/카드/링크 렌더 확인.
4. 사이트 이동 후 재검증: `python -m http.server -d site` + 브라우저 E2E(카드 렌더·클릭 속성), pytest 전체, add_product 라운드트립.
