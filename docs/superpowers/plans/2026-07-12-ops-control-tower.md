# 관제탑(ops) 구현 계획

> **For agentic workers:** 이 계획은 스펙(`docs/superpowers/specs/2026-07-12-ops-control-tower-design.md`)과 한 몸이다. 스키마·CLI 동작·단계 표의 정본은 스펙이며, 이 문서는 실행 순서와 수용 기준만 정의한다. (작성 세션에서 인라인 실행 전제 — 컨트롤러가 스펙 전체를 컨텍스트에 보유)

**Goal:** 파이프라인 아이템 장부(ops/pipeline.json) + CLI(pipeline.py) + 정적 대시보드를 만들고, 배포 전 site/ops 분리를 완료한다.

**Tech Stack:** Python 3 stdlib(+pytest), 생성형 정적 HTML. 의존성 추가 없음.

---

### Task A: site/ops 재구조화

- [ ] `git mv index.html style.css app.js products.json favicon.svg site/`
- [ ] `netlify.toml` 생성: `[build]` / `  publish = "site"`
- [ ] `scripts/add_product.py`의 `DEFAULT_FILE`을 `REPO_ROOT / "site" / "products.json"`으로 수정
- [ ] `.gitignore`에 `ops/dashboard.html` 추가
- [ ] 검증: `python -m pytest tests/ -q` 전체 통과, `python -m http.server -d site 8766` 후 브라우저에서 카드 렌더·구매 링크 속성 확인, `python scripts/add_product.py` 라운드트립(추가→확인→`git checkout -- site/products.json`)
- [ ] Commit: `refactor: 배포(site)와 관제(ops) 분리, Netlify publish=site`

### Task B: pipeline.py TDD

- [ ] `tests/test_pipeline.py` 작성 — 스펙 "검증 계획 1" 항목 전부: new(첫 id=1·max+1·title/URL 검증·중복 coupangUrl 거부), advance(순차 진행·history append·`--set` 파싱(값에 = 포함)·`--to` 점프·잘못된 slug 거부·없는 id 거부·analyzed에서 순차 advance 에러), save/load 한글 라운드트립, 전 단계 next_action 존재, render_dashboard 스모크(제목·단계 한글 포함)
- [ ] `python -m pytest tests/test_pipeline.py -q` → 실패(ModuleNotFoundError) 확인
- [ ] `scripts/pipeline.py` 구현 — 스펙의 단계 표·스키마·CLI 규칙 그대로. 순수 함수(new_item/advance_item/parse_sets/next_action/render_dashboard) + argparse `main()`
- [ ] `python -m pytest tests/ -q` → 전체 통과
- [ ] Commit: `feat: 파이프라인 관제 CLI (new/advance/status/dashboard) TDD`

### Task C: 대시보드 실사용 검증 + 문서/머지

- [ ] 실데이터 시나리오: `new` 2건 → `advance --set`으로 각각 다른 단계까지 진행 → `status` 출력 확인 → `dashboard --no-open` 생성
- [ ] 브라우저로 `ops/dashboard.html` 열어 9컬럼 보드·카드·링크 확인 (이 검증용 아이템은 실제 운영 첫 데이터로 남겨도 무방 — 판단 후 유지/정리)
- [ ] README에 관제탑 사용법·새 구조 반영
- [ ] Commit: `docs: README 관제탑 사용법` → main 머지
- [ ] 수용 기준: pytest 전체 통과 + 사이트 E2E 이상 없음 + 대시보드가 파일 열기만으로 렌더
