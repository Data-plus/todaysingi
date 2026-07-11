# 오늘의신기템 v1 — 링크트리형 상품 큐레이션 사이트 설계

날짜: 2026-07-12
상태: 사용자 승인됨 (브레인스토밍 완료)

## 배경과 목적

인스타그램 숏츠로 쿠팡 파트너스 상품을 홍보하는 자동화 파이프라인(상품 발굴 → 알리 영상 수집 → TTS 더빙 → 릴스 업로드 → 광고 A/B)의 **종착지가 되는 링크 허브**. litt.ly·inpock 같은 서비스는 API가 없어 자동화가 불가하므로, 직접 소유한 정적 사이트로 대체한다.

전체 파이프라인 빌드 순서 중 1단계에 해당: ① 링크트리 사이트(본 문서) → ② 콘텐츠 파이프라인 반자동 PoC → ③ 업로드·링크 자동화 → ④ 광고 + A/B 분석.

## 요구사항 (v1 범위)

- 프로필 헤더: 아바타(없으면 이니셜 원), 이름, 한 줄 소개, SNS 아이콘 링크(인스타그램 등)
- 상품 카드 리스트: 썸네일, `[001] 제목` 형식 표시명, 가격, "구매하기" 버튼 → 쿠팡 파트너스 링크 새 탭 이동
- GA4 클릭 추적: 상품별 클릭 이벤트 (향후 A/B 분석의 원천 데이터)
- 쿠팡 파트너스 고지문 푸터 상시 표기
- 상품 추가 스크립트(`scripts/add_product.py`) — 향후 파이프라인 11번 단계가 그대로 호출

**비범위(v2 이후):** 카테고리/필터, 검색, 상품 상세 페이지, 다크 모드(화이트 컨셉 고정), 관리자 UI, Supabase 등 백엔드, 파이프라인 자체.

## 브랜딩·디자인

- 브랜드명: **오늘의신기템**
- 디자인 방향: **A 미니멀 화이트** — 흰 배경, 검정 CTA 버튼, 얇은 회색 보더 카드. 상품 썸네일이 주인공.
- 모바일 퍼스트: 인스타그램 인앱 브라우저 기준, 콘텐츠 최대폭 480px 중앙 정렬. 데스크톱에서도 같은 단일 컬럼.
- 타이포: 시스템 폰트 스택(Pretendard 있으면 사용, 없으면 system-ui 폴백). 웹폰트 로딩으로 첫 렌더 지연시키지 않는다.

## 아키텍처

빌드 도구 없는 순수 정적 사이트. GitHub push → Netlify 자동 배포.

```
todaysingi/
├── index.html          # 마크업 + GA4 스니펫 + OG 메타
├── style.css           # 미니멀 화이트 스타일
├── app.js              # products.json fetch → 카드 렌더 → 클릭 이벤트
├── products.json       # 프로필 + 상품 데이터 (유일한 데이터 소스)
├── images/             # (선택) 로컬 저장 썸네일, 프로필 이미지
├── favicon.svg
├── scripts/
│   └── add_product.py  # 상품 추가 CLI (검증 + append + 선택적 push)
└── docs/superpowers/specs/  # 설계 문서
```

- 호스팅: Netlify 무료 티어, 저장소 루트를 그대로 퍼블리시(netlify.toml 불필요)
- 도메인: `todaysingi.netlify.app` 목표(선점 시 배포 시점에 변형 결정), 커스텀 도메인은 나중에
- 저장소: `C:\Users\abcd0\github\todaysingi`, GitHub 원격 연결 후 Netlify 연동

## 데이터 모델 (`products.json`)

```json
{
  "profile": {
    "name": "오늘의신기템",
    "bio": "쿠팡에서 찾은 세상 신기한 물건들",
    "avatar": "images/avatar.jpg",
    "links": [
      { "type": "instagram", "url": "https://instagram.com/PLACEHOLDER" }
    ]
  },
  "products": [
    {
      "id": 1,
      "title": "접이식 미니 가습기",
      "price": 12900,
      "image": "https://thumbnail.coupangcdn.com/...jpg",
      "link": "https://link.coupang.com/a/xxxx",
      "addedAt": "2026-07-12",
      "active": true
    }
  ]
}
```

규칙:
- `id`: 1부터 증가하는 정수. 표시명은 렌더 시 `[${String(id).padStart(3, "0")}] ${title}` — 데이터에 번호를 중복 저장하지 않는다. 1000번 이상은 자연스럽게 4자리.
- `price`: 원 단위 정수. 렌더 시 `toLocaleString("ko-KR") + "원"`.
- `image`: 원격 URL(쿠팡 파트너스 API 제공 URL 등) 또는 로컬 `images/` 경로 모두 허용.
- `active: false`인 상품은 렌더하지 않는다(품절·단종 대응, 데이터는 보존).
- 렌더 순서: `id` 내림차순(최신이 위).
- `profile.avatar`가 없거나 로드 실패 시 이름 첫 글자 이니셜 원으로 대체.

## 렌더링·동작 상세

- `app.js`가 `products.json`을 `fetch`해 카드 DOM 생성 (프레임워크 없음).
- 구매 버튼: `<a target="_blank" rel="noopener sponsored">`. 클릭 시 GA4 이벤트 전송 후 기본 동작(새 탭)을 막지 않는다.
- OG 메타: `og:title`(오늘의신기템), `og:description`(bio), `og:image`(아바타 또는 기본 이미지) — 인스타 바이오·DM 공유 미리보기용.
- 파트너스 고지문(푸터 고정, 정확 문구): "이 포스팅은 쿠팡 파트너스 활동의 일환으로, 이에 따른 일정액의 수수료를 제공받습니다."

## GA4 클릭 추적

- 측정 ID는 `app.js` 상단 상수 `GA_MEASUREMENT_ID`. 값이 있으면 `app.js`가 gtag.js를 동적으로 로드하고 `config`를 호출한다(스니펫을 HTML에 하드코딩하지 않음).
- ID가 빈 문자열이면 gtag 로드·이벤트 전송을 조용히 건너뛴다(사이트 동작에 영향 없음) — 발급 전에도 배포 가능.
- 이벤트: `product_click`, 파라미터 `{ item_id: id, item_name: title }`.
- 페이지뷰는 GA4 기본 수집 사용.

## `scripts/add_product.py`

```
python scripts/add_product.py --title "제목" --price 12900 \
    --image "https://...jpg" --link "https://link.coupang.com/a/xxx" [--push]
```

- 동작: `products.json` 로드 → 검증 → `id = max(id) + 1`(상품 0개면 1), `addedAt = 오늘(로컬 날짜)`, `active = true`로 항목 추가 → 저장(UTF-8, 들여쓰기 2, `ensure_ascii=False`).
- 검증 실패 시 비정상 종료(exit 1) + 이유 출력: `link`·`image`는 `https://` 시작, `price`는 양의 정수, `title` 비어 있지 않음, 동일 `link` 중복 시 거부.
- `--push` 옵션: `git add products.json && git commit && git push` 까지 수행. 기본은 파일 수정만.
- 표준 라이브러리만 사용(의존성 0).

## 엣지 케이스

- `products.json` fetch 실패 → "상품을 불러오지 못했어요. 잠시 후 새로고침해 주세요." 문구 표시.
- 상품 썸네일 로드 실패 → 회색 플레이스홀더(`onerror` 처리).
- `active` 상품 0개 → "곧 신기한 물건들이 올라올 거예요." 빈 상태 문구.

## 검증 계획

1. 로컬 서버(`python -m http.server`)로 열어 렌더 확인 — `fetch`는 `file://`에서 동작하지 않으므로 반드시 서버 경유.
2. 데스크톱·모바일(375px) 뷰포트에서 레이아웃 확인.
3. `add_product.py` 라운드트립: 임시 데이터로 추가 → 스키마 검증 → 렌더 확인 → 원복.
4. 잘못된 입력(가격 음수, http 링크, 중복 링크)에서 스크립트가 거부하는지 확인.
5. 배포 후 실제 URL에서: 카드 클릭 → 새 탭 파트너스 링크 이동, GA4 DebugView(또는 실시간 보고서)에서 `product_click` 수신 확인.

## 사용자 준비물

- Netlify 계정(무료) + GitHub 원격 저장소 생성 권한
- GA4 측정 ID (선택 — 나중에 상수만 채우면 됨)
- 프로필 아바타 이미지 (선택)
- 인스타그램 계정 핸들 확정 후 `profile.links` 갱신
