# 오늘의신기템 v1 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 쿠팡 파트너스 상품을 카드로 보여주는 링크트리형 정적 사이트를 만들고 Netlify에 배포한다.

**Architecture:** 빌드 도구 없는 순수 정적 사이트(index.html + style.css + app.js)가 `products.json` 하나를 fetch해 렌더링한다. 상품 추가는 `scripts/add_product.py`(표준 라이브러리만 사용)가 JSON을 검증·수정하고, git push가 곧 배포다(Netlify 자동 배포). GA4 측정 ID가 비어 있으면 추적 코드는 조용히 비활성화된다.

**Tech Stack:** HTML/CSS/Vanilla JS, Python 3(stdlib + pytest는 테스트에만), Netlify, GA4(gtag.js).

**Spec:** `docs/superpowers/specs/2026-07-12-todaysingi-v1-design.md` (승인본)

**테스트 방침:** 실질 로직이 있는 `add_product.py`는 pytest로 TDD. 프런트엔드는 프레임워크·빌드가 없는 원페이지라 JS 테스트 하네스 추가가 YAGNI 위반이므로, 로컬 서버 + 브라우저 확인 절차를 각 태스크에 명시한다.

---

### Task 1: 저장소 뼈대 + 초기 데이터

**Files:**
- Create: `products.json`
- Create: `favicon.svg`
- Create: `.gitignore`

- [ ] **Step 1: `.gitignore` 작성**

```
__pycache__/
.pytest_cache/
*.pyc
```

- [ ] **Step 2: `products.json` 작성**

샘플 상품 1개를 넣는다(빈 화면 방지 + 렌더링 확인용). 실상품 추가를 시작하면 삭제한다. `avatar`가 빈 문자열이면 프런트가 이니셜 원으로 대체한다.

```json
{
  "profile": {
    "name": "오늘의신기템",
    "bio": "쿠팡에서 찾은 세상 신기한 물건들",
    "avatar": "",
    "links": [
      { "type": "instagram", "url": "https://www.instagram.com/" }
    ]
  },
  "products": [
    {
      "id": 1,
      "title": "샘플 상품 — 첫 실상품 추가 후 삭제",
      "price": 12900,
      "image": "https://picsum.photos/seed/singi1/640/400",
      "link": "https://www.coupang.com/",
      "addedAt": "2026-07-12",
      "active": true
    }
  ]
}
```

- [ ] **Step 3: `favicon.svg` 작성**

```svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><rect width="64" height="64" rx="14" fill="#191919"/><text x="32" y="43" font-size="30" font-family="sans-serif" font-weight="700" text-anchor="middle" fill="#ffffff">신</text></svg>
```

- [ ] **Step 4: JSON 유효성 확인**

Run: `python -c "import json; json.load(open('products.json', encoding='utf-8')); print('OK')"`
Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add .gitignore products.json favicon.svg
git commit -m "feat: 초기 데이터와 저장소 뼈대"
```

---

### Task 2: index.html + style.css (미니멀 화이트 레이아웃)

**Files:**
- Create: `index.html`
- Create: `style.css`

- [ ] **Step 1: `index.html` 작성**

주의: `og:image`는 아바타 이미지가 생기기 전까지 넣지 않는다(404 나는 태그가 더 나쁨). 아바타가 생기면 Task 7에서 추가.

```html
<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>오늘의신기템</title>
  <meta name="description" content="쿠팡에서 찾은 세상 신기한 물건들">
  <meta property="og:title" content="오늘의신기템">
  <meta property="og:description" content="쿠팡에서 찾은 세상 신기한 물건들">
  <meta property="og:type" content="website">
  <link rel="icon" href="favicon.svg" type="image/svg+xml">
  <link rel="stylesheet" href="style.css">
</head>
<body>
  <main class="wrap">
    <header id="profile" class="profile"></header>
    <section id="products" class="products" aria-label="상품 목록"></section>
    <p id="status" class="status" hidden></p>
    <footer class="footer">
      <p>이 포스팅은 쿠팡 파트너스 활동의 일환으로, 이에 따른 일정액의 수수료를 제공받습니다.</p>
    </footer>
  </main>
  <script src="app.js"></script>
</body>
</html>
```

- [ ] **Step 2: `style.css` 작성**

```css
:root {
  --ink: #191919;
  --muted: #888780;
  --line: #e5e4de;
  --bg-soft: #f5f4f0;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  background: #fff;
  color: var(--ink);
  font-family: "Pretendard Variable", Pretendard, "Apple SD Gothic Neo",
    "Malgun Gothic", system-ui, sans-serif;
  line-height: 1.5;
  -webkit-font-smoothing: antialiased;
}
.wrap { max-width: 480px; margin: 0 auto; padding: 32px 20px 24px; }

.profile { text-align: center; margin-bottom: 28px; }
.avatar {
  width: 72px; height: 72px; border-radius: 50%;
  margin: 0 auto 12px; display: block; object-fit: cover;
}
.avatar-fallback {
  width: 72px; height: 72px; border-radius: 50%;
  margin: 0 auto 12px; display: flex; align-items: center; justify-content: center;
  background: var(--bg-soft); color: var(--ink);
  font-size: 28px; font-weight: 600;
}
.profile h1 { font-size: 20px; margin: 0 0 4px; }
.profile .bio { color: var(--muted); font-size: 14px; margin: 0 0 12px; }
.sns { display: flex; gap: 14px; justify-content: center; }
.sns a { color: var(--ink); display: inline-flex; }
.sns svg { width: 22px; height: 22px; }

.products { display: flex; flex-direction: column; gap: 16px; }
.card { border: 1px solid var(--line); border-radius: 14px; overflow: hidden; }
.card .thumb {
  width: 100%; aspect-ratio: 16 / 10; object-fit: cover; display: block;
  background: var(--bg-soft); border: 0;
}
.card-body { padding: 14px 16px 16px; }
.card h2 { font-size: 15px; font-weight: 600; margin: 0 0 2px; }
.card .price { color: var(--muted); font-size: 14px; margin: 0 0 12px; }
.buy {
  display: block; text-align: center; background: var(--ink); color: #fff;
  text-decoration: none; font-size: 15px; font-weight: 600;
  padding: 12px 0; border-radius: 10px;
}
.buy:active { opacity: .85; }

.status { text-align: center; color: var(--muted); padding: 40px 0; }
.footer { margin-top: 40px; text-align: center; color: var(--muted); font-size: 11px; }
```

- [ ] **Step 3: 뼈대 확인(스크립트 없이도 고지문이 보여야 함)**

Run: `python -m http.server 8765` (백그라운드, 저장소 루트에서)
브라우저로 `http://localhost:8765` 열기.
Expected: 흰 배경, 하단에 쿠팡 파트너스 고지문. 프로필/상품 영역은 아직 빈 상태(app.js가 없으므로 콘솔에 404 — 다음 태스크에서 해결).

- [ ] **Step 4: Commit**

```bash
git add index.html style.css
git commit -m "feat: 미니멀 화이트 레이아웃과 파트너스 고지문"
```

---

### Task 3: app.js (렌더링 + GA4 클릭 추적)

**Files:**
- Create: `app.js`

- [ ] **Step 1: `app.js` 작성**

원칙: 텍스트는 전부 `textContent`(XSS 습관), 고정 아이콘 SVG만 `innerHTML`. GA4는 `GA_MEASUREMENT_ID`가 비어 있으면 아무것도 로드하지 않는다.

```js
const GA_MEASUREMENT_ID = ""; // GA4 측정 ID(G-XXXXXXXXXX). 비우면 추적 없이 동작.

const ICONS = {
  instagram:
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><rect x="3" y="3" width="18" height="18" rx="5"/><circle cx="12" cy="12" r="4"/><circle cx="17.2" cy="6.8" r=".9" fill="currentColor" stroke="none"/></svg>',
  youtube:
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><rect x="2.5" y="5.5" width="19" height="13" rx="3.5"/><path d="M10 9.5v5l4.5-2.5z" fill="currentColor" stroke="none"/></svg>',
  link:
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><path d="M9 15l6-6"/><path d="M11 6.5l1.5-1.5a4 4 0 015.5 5.5L16.5 12"/><path d="M13 17.5L11.5 19a4 4 0 01-5.5-5.5L7.5 12"/></svg>',
};

function setupAnalytics() {
  if (!GA_MEASUREMENT_ID) return;
  const s = document.createElement("script");
  s.async = true;
  s.src = "https://www.googletagmanager.com/gtag/js?id=" + GA_MEASUREMENT_ID;
  document.head.appendChild(s);
  window.dataLayer = window.dataLayer || [];
  window.gtag = function () { window.dataLayer.push(arguments); };
  gtag("js", new Date());
  gtag("config", GA_MEASUREMENT_ID);
}

function trackClick(product) {
  if (!GA_MEASUREMENT_ID || typeof window.gtag !== "function") return;
  gtag("event", "product_click", {
    item_id: String(product.id),
    item_name: product.title,
  });
}

const displayName = (p) => "[" + String(p.id).padStart(3, "0") + "] " + p.title;
const displayPrice = (p) => p.price.toLocaleString("ko-KR") + "원";

function renderProfile(profile) {
  const root = document.getElementById("profile");

  if (profile.avatar) {
    const img = document.createElement("img");
    img.className = "avatar";
    img.src = profile.avatar;
    img.alt = profile.name;
    img.onerror = () => img.replaceWith(makeAvatarFallback(profile.name));
    root.appendChild(img);
  } else {
    root.appendChild(makeAvatarFallback(profile.name));
  }

  const h1 = document.createElement("h1");
  h1.textContent = profile.name;
  root.appendChild(h1);

  const bio = document.createElement("p");
  bio.className = "bio";
  bio.textContent = profile.bio;
  root.appendChild(bio);

  const links = (profile.links || []).filter((l) => l.url);
  if (links.length) {
    const nav = document.createElement("nav");
    nav.className = "sns";
    for (const l of links) {
      const a = document.createElement("a");
      a.href = l.url;
      a.target = "_blank";
      a.rel = "noopener";
      a.setAttribute("aria-label", l.type);
      a.innerHTML = ICONS[l.type] || ICONS.link;
      nav.appendChild(a);
    }
    root.appendChild(nav);
  }
}

function makeAvatarFallback(name) {
  const div = document.createElement("div");
  div.className = "avatar-fallback";
  div.textContent = (name || "?").slice(0, 1);
  return div;
}

function renderProducts(products) {
  const root = document.getElementById("products");
  for (const p of products) {
    const card = document.createElement("article");
    card.className = "card";

    const img = document.createElement("img");
    img.className = "thumb";
    img.src = p.image;
    img.alt = p.title;
    img.loading = "lazy";
    img.onerror = () => { img.removeAttribute("src"); img.alt = ""; };
    card.appendChild(img);

    const body = document.createElement("div");
    body.className = "card-body";

    const h2 = document.createElement("h2");
    h2.textContent = displayName(p);
    body.appendChild(h2);

    const price = document.createElement("p");
    price.className = "price";
    price.textContent = displayPrice(p);
    body.appendChild(price);

    const buy = document.createElement("a");
    buy.className = "buy";
    buy.href = p.link;
    buy.target = "_blank";
    buy.rel = "noopener sponsored";
    buy.textContent = "구매하기";
    buy.addEventListener("click", () => trackClick(p));
    body.appendChild(buy);

    card.appendChild(body);
    root.appendChild(card);
  }
}

function showStatus(message) {
  const status = document.getElementById("status");
  status.textContent = message;
  status.hidden = false;
}

async function init() {
  setupAnalytics();
  try {
    const res = await fetch("products.json", { cache: "no-cache" });
    if (!res.ok) throw new Error("HTTP " + res.status);
    const data = await res.json();
    renderProfile(data.profile);
    const items = data.products
      .filter((p) => p.active)
      .sort((a, b) => b.id - a.id);
    if (items.length === 0) {
      showStatus("곧 신기한 물건들이 올라올 거예요.");
      return;
    }
    renderProducts(items);
  } catch (e) {
    showStatus("상품을 불러오지 못했어요. 잠시 후 새로고침해 주세요.");
  }
}

init();
```

- [ ] **Step 2: 브라우저 확인 — 정상 렌더링**

Run: `python -m http.server 8765` (이미 떠 있으면 재사용)
`http://localhost:8765` 새로고침.
Expected:
- 이니셜 "오" 원형 아바타, "오늘의신기템" 이름, 소개 문구, 인스타 아이콘
- `[001] 샘플 상품 — 첫 실상품 추가 후 삭제` 카드, `12,900원`, 검정 구매하기 버튼
- 구매하기 클릭 → 새 탭으로 쿠팡 이동
- 콘솔 에러 0건 (GA는 ID가 비어 있으므로 아무 요청도 없어야 함)

- [ ] **Step 3: 브라우저 확인 — 엣지 상태**

1. `products.json`의 상품 `active`를 `false`로 임시 변경 → 새로고침 → "곧 신기한 물건들이 올라올 거예요." 표시 확인
2. fetch URL을 임시로 `products.jsonx`로 바꾸거나 파일명을 잠시 바꿔 → "상품을 불러오지 못했어요..." 표시 확인
3. 확인 후 **모두 원복** (`git diff`가 app.js 신규 추가 외에 깨끗해야 함)

- [ ] **Step 4: 모바일 뷰포트 확인**

브라우저 개발자도구 또는 프리뷰 도구로 375px 폭 확인.
Expected: 가로 스크롤 없음, 카드가 화면 폭에 맞음.

- [ ] **Step 5: Commit**

```bash
git add app.js
git commit -m "feat: 상품 카드 렌더링과 GA4 클릭 추적(옵션)"
```

---

### Task 4: scripts/add_product.py — TDD

**Files:**
- Create: `scripts/add_product.py`
- Test: `tests/test_add_product.py`

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_add_product.py`:

```python
import datetime as dt
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from add_product import ValidationError, add_product, load_data, save_data


def make_data(products=None):
    return {"profile": {"name": "오늘의신기템"}, "products": products if products is not None else []}


def test_first_product_gets_id_1():
    data = make_data()
    p = add_product(data, title="가습기", price=12900,
                    image="https://img.example/1.jpg",
                    link="https://link.coupang.com/a/aaa")
    assert p["id"] == 1
    assert data["products"][-1] is p


def test_next_id_is_max_plus_one_with_gaps():
    data = make_data([{"id": 3, "link": "https://link.coupang.com/a/x"}])
    p = add_product(data, title="후크", price=5900,
                    image="https://img.example/2.jpg",
                    link="https://link.coupang.com/a/bbb")
    assert p["id"] == 4


def test_fills_added_at_active_and_strips_title():
    data = make_data()
    p = add_product(data, title="  가습기  ", price=12900,
                    image="https://img.example/1.jpg",
                    link="https://link.coupang.com/a/aaa",
                    today=dt.date(2026, 7, 12))
    assert p["addedAt"] == "2026-07-12"
    assert p["active"] is True
    assert p["title"] == "가습기"


@pytest.mark.parametrize("kwargs", [
    dict(title="   ", price=12900, image="https://i/1.jpg", link="https://l/a"),
    dict(title="가습기", price=0, image="https://i/1.jpg", link="https://l/a"),
    dict(title="가습기", price=-100, image="https://i/1.jpg", link="https://l/a"),
    dict(title="가습기", price=12900, image="http://i/1.jpg", link="https://l/a"),
    dict(title="가습기", price=12900, image="https://i/1.jpg", link="http://l/a"),
])
def test_rejects_invalid_input(kwargs):
    with pytest.raises(ValidationError):
        add_product(make_data(), **kwargs)


def test_rejects_duplicate_link():
    data = make_data([{"id": 1, "link": "https://link.coupang.com/a/dup"}])
    with pytest.raises(ValidationError):
        add_product(data, title="중복", price=1000,
                    image="https://i/1.jpg",
                    link="https://link.coupang.com/a/dup")


def test_save_load_roundtrip_keeps_korean(tmp_path):
    path = tmp_path / "products.json"
    data = make_data()
    add_product(data, title="접이식 미니 가습기", price=12900,
                image="https://i/1.jpg", link="https://l/a")
    save_data(path, data)
    raw = path.read_text(encoding="utf-8")
    assert "접이식 미니 가습기" in raw
    assert load_data(path) == data
```

- [ ] **Step 2: 테스트가 실패하는지 확인**

Run: `python -m pytest tests/ -v`
Expected: 전체 FAIL/ERROR — `ModuleNotFoundError: No module named 'add_product'`
(pytest가 없으면 먼저 `python -m pip install pytest`)

- [ ] **Step 3: `scripts/add_product.py` 구현**

```python
#!/usr/bin/env python3
"""오늘의신기템 상품 추가 CLI.

사용 예:
    python scripts/add_product.py --title "접이식 미니 가습기" --price 12900 \
        --image "https://...jpg" --link "https://link.coupang.com/a/xxxx" [--push]

products.json을 검증 후 수정한다. --push를 주면 commit/push까지 수행해
Netlify 자동 배포를 트리거한다. 향후 자동화 파이프라인(11번 단계)의 진입점.
"""
import argparse
import datetime as dt
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_FILE = REPO_ROOT / "products.json"


class ValidationError(ValueError):
    pass


def load_data(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_data(path, data):
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def validate(title, price, image, link, existing_products):
    if not title or not title.strip():
        raise ValidationError("title이 비어 있습니다")
    if not isinstance(price, int) or isinstance(price, bool) or price <= 0:
        raise ValidationError("price는 양의 정수여야 합니다")
    for name, url in (("image", image), ("link", link)):
        if not isinstance(url, str) or not url.startswith("https://"):
            raise ValidationError(f"{name}은(는) https:// 로 시작해야 합니다")
    if any(p["link"] == link for p in existing_products):
        raise ValidationError("이미 같은 link의 상품이 있습니다")


def add_product(data, *, title, price, image, link, today=None):
    products = data["products"]
    validate(title, price, image, link, products)
    product = {
        "id": max((p["id"] for p in products), default=0) + 1,
        "title": title.strip(),
        "price": price,
        "image": image,
        "link": link,
        "addedAt": (today or dt.date.today()).isoformat(),
        "active": True,
    }
    products.append(product)
    return product


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="products.json에 상품을 추가합니다")
    parser.add_argument("--title", required=True)
    parser.add_argument("--price", required=True, type=int)
    parser.add_argument("--image", required=True)
    parser.add_argument("--link", required=True)
    parser.add_argument("--file", default=str(DEFAULT_FILE))
    parser.add_argument("--push", action="store_true", help="git add/commit/push까지 수행")
    args = parser.parse_args(argv)

    path = Path(args.file)
    data = load_data(path)
    try:
        product = add_product(data, title=args.title, price=args.price,
                              image=args.image, link=args.link)
    except ValidationError as e:
        print(f"거부됨: {e}", file=sys.stderr)
        return 1
    save_data(path, data)
    display = f"[{product['id']:03d}] {product['title']}"
    print(f"추가됨: {display}")

    if args.push:
        subprocess.run(["git", "add", str(path)], cwd=REPO_ROOT, check=True)
        subprocess.run(["git", "commit", "-m", f"feat: 상품 추가 {display}"],
                       cwd=REPO_ROOT, check=True)
        subprocess.run(["git", "push"], cwd=REPO_ROOT, check=True)
        print("push 완료 — Netlify가 곧 배포합니다")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `python -m pytest tests/ -v`
Expected: 10 passed (parametrize 5건 포함)

- [ ] **Step 5: Commit**

```bash
git add scripts/add_product.py tests/test_add_product.py
git commit -m "feat: 상품 추가 CLI (검증 + 선택적 push) TDD"
```

---

### Task 5: 통합 검증 (로컬 E2E)

**Files:** 없음 (검증만; 수정 발생 시 해당 파일 커밋)

- [ ] **Step 1: CLI로 실제 상품 추가 라운드트립**

```bash
python scripts/add_product.py --title "통합테스트 상품" --price 9900 \
  --image "https://picsum.photos/seed/singi2/640/400" \
  --link "https://link.coupang.com/a/integration-test"
```

Expected: `추가됨: [002] 통합테스트 상품`

- [ ] **Step 2: 브라우저에서 확인**

`http://localhost:8765` 새로고침 (서버 없으면 `python -m http.server 8765`).
Expected: `[002] 통합테스트 상품`이 **맨 위**(id 내림차순), `9,900원` 표기.

- [ ] **Step 3: 거부 동작 확인**

```bash
python scripts/add_product.py --title "중복" --price 1000 \
  --image "https://i/1.jpg" --link "https://link.coupang.com/a/integration-test"
echo "exit=$?"
```

Expected: stderr에 `거부됨: 이미 같은 link의 상품이 있습니다`, `exit=1`, products.json 변화 없음

- [ ] **Step 4: 테스트 데이터 원복**

```bash
git checkout -- products.json
git status
```

Expected: working tree clean

- [ ] **Step 5: 최종 테스트 일괄 실행 후 커밋(수정이 있었던 경우만)**

Run: `python -m pytest tests/ -v` → Expected: all passed
수정 없으면 커밋 생략.

---

### Task 6: GitHub 원격 + Netlify 배포 (사용자 체크포인트 포함)

**Files:**
- 없음 (배포 설정은 Netlify UI에서; netlify.toml 불필요 — 루트 그대로 퍼블리시)

- [ ] **Step 1: GitHub 저장소 생성 + push**

```bash
gh auth status   # 로그인 안 되어 있으면: gh auth login
gh repo create todaysingi --public --source . --remote origin --push
```

Expected: `https://github.com/<계정>/todaysingi` 생성, main push 완료.
(비공개를 원하면 `--public` → `--private`; Netlify 연동에는 지장 없음)
(gh CLI가 없으면: github.com에서 빈 저장소 생성 후 `git remote add origin <URL> && git push -u origin main`)

- [ ] **Step 2: [사용자 체크포인트] Netlify 연동**

사용자가 브라우저에서 수행 (약 3분):
1. https://app.netlify.com 로그인 (GitHub 계정 연동 추천)
2. "Add new project" → "Import an existing project" → GitHub → `todaysingi` 선택
3. Build command: **비워둠**, Publish directory: **`/` (루트)** → Deploy
4. Site configuration → "Change site name" → `todaysingi` 입력 (선점 시 `todaysingi-shop` 등 대안 결정)

Expected: `https://todaysingi.netlify.app` 접속 가능

- [ ] **Step 3: 배포 검증**

- 모바일 폰에서 실제 URL 접속 → 카드 렌더 확인
- 구매하기 클릭 → 새 탭 이동 확인
- 사소한 커밋 하나를 push해 Netlify 자동 배포가 트리거되는지 확인 (통상 30초~1분 내 반영)

- [ ] **Step 4: README 작성 + 커밋**

`README.md`:

```markdown
# 오늘의신기템

쿠팡 파트너스 상품 링크 허브. https://todaysingi.netlify.app

## 상품 추가

    python scripts/add_product.py --title "제목" --price 12900 \
        --image "https://...jpg" --link "https://link.coupang.com/a/xxxx" --push

push하면 Netlify가 약 1분 내 자동 배포한다.

## 구조

정적 사이트(index.html + app.js)가 products.json을 읽는다. 빌드 없음.
- 상품 숨기기: 해당 항목 `"active": false` 후 push
- GA4 연결: app.js 상단 `GA_MEASUREMENT_ID`에 측정 ID 입력
- 설계 문서: docs/superpowers/specs/
```

```bash
git add README.md
git commit -m "docs: README (상품 추가 방법과 운영 노트)"
git push
```

---

### Task 7: 사용자 입력 반영 (입력이 준비되는 대로)

**Files:**
- Modify: `app.js:1` (GA_MEASUREMENT_ID)
- Modify: `products.json` (profile.links의 인스타 URL, profile.avatar)
- Modify: `index.html` (og:image — 아바타 생긴 후)

- [ ] **Step 1: GA4 측정 ID 입력**

사용자가 https://analytics.google.com 에서 속성 생성 → 웹 스트림 추가 → 측정 ID(G-XXXXXXXXXX) 확보.
`app.js` 1행: `const GA_MEASUREMENT_ID = "G-XXXXXXXXXX";`

- [ ] **Step 2: GA4 동작 검증**

배포된 사이트 접속 → 구매하기 클릭 → GA4 관리 화면의 "실시간" 보고서에서 `product_click` 이벤트 수신 확인.

- [ ] **Step 3: 인스타 핸들 + 아바타 반영**

- `products.json`의 `profile.links[0].url`을 실제 계정 URL로 교체
- 아바타 이미지를 `images/avatar.jpg`로 저장, `profile.avatar`에 경로 입력
- `index.html`의 og 블록에 추가: `<meta property="og:image" content="https://todaysingi.netlify.app/images/avatar.jpg">`

- [ ] **Step 4: Commit + push**

```bash
git add app.js products.json index.html images/
git commit -m "feat: GA4 연결, 인스타 링크·아바타 반영"
git push
```
