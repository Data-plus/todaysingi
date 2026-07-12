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
DEFAULT_FILE = REPO_ROOT / "site" / "products.json"


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
    if not isinstance(image, str) or not (
            image.startswith("https://") or image.startswith("images/")):
        raise ValidationError("image는 https:// URL 또는 images/ 경로여야 합니다")
    if not isinstance(link, str) or not link.startswith("https://"):
        raise ValidationError("link는 https:// 로 시작해야 합니다")
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
