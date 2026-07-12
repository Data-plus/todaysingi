# 오늘의신기템

쿠팡 파트너스 상품 링크 허브 + 파이프라인 관제탑. https://todaysingi.netlify.app

## 구조

- `site/` — 배포되는 정적 사이트(빌드 없음). Netlify가 이 폴더만 공개한다(netlify.toml).
- `ops/` — 파이프라인 관제 장부(pipeline.json)와 대시보드(생성물). 배포되지 않는다.
- `scripts/` — 운영 CLI 두 개.

## 상품 추가 (사이트 게시)

    python scripts/add_product.py --title "제목" --price 12900 \
        --image "https://...jpg" --link "https://link.coupang.com/a/xxxx" --push

push하면 Netlify가 약 1분 내 자동 배포한다.

- 상품 숨기기: `site/products.json`에서 해당 항목 `"active": false` 후 push
- GA4 연결: `site/app.js` 상단 `GA_MEASUREMENT_ID`에 측정 ID 입력
- 로컬 확인: `python -m http.server -d site 8765`

## 파이프라인 관제탑

    python scripts/pipeline.py new --title "제목" --coupang-url "https://..."
    python scripts/pipeline.py advance 1 --set aliUrl=https://...   # 다음 단계로 + 산출물 기록
    python scripts/pipeline.py advance 1 --to published             # 단계 지정 이동
    python scripts/pipeline.py status                               # 터미널 현황 + 다음 할 일
    python scripts/pipeline.py dashboard                            # 보드 생성해 브라우저로 열기

단계: 상품확정 → 영상준비 → 대본완성 → 더빙합성 → 캡션완성 → 릴스게시 → 링크연결 → 광고집행 → 분석완료

## 콘텐츠 파이프라인 (Phase 2)

쿠팡 링크 → 알리 영상 수집(`scripts/fetch_video.py`) → 대본(Claude) →
더빙+자막(`scripts/dub.py`, edge-tts PoC) → 캡션(Claude) → 수동 게시.
상품 1개 처리 절차는 **`docs/PLAYBOOK.md`** 참조.

## 문서

- 운영 매뉴얼: `docs/PLAYBOOK.md`
- 설계 스펙: `docs/superpowers/specs/`
- 구현 계획: `docs/superpowers/plans/`
