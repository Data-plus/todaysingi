#!/usr/bin/env python3
"""Supabase 공개 준비 상품을 기존 site/products.json 스키마로 내보낸다."""
from __future__ import annotations

import json
import os
import sys
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "site" / "products.json"
PUBLIC_STAGES = {"published", "linked", "ads_running", "analyzed"}


class ExportError(ValueError):
    pass


def build_products_document(
    rows: Iterable[dict[str, Any]], profile: dict[str, Any],
) -> dict[str, Any]:
    products = []
    for row in sorted(rows, key=lambda value: int(value.get("id") or 0)):
        if row.get("stage") not in PUBLIC_STAGES or row.get("active", True) is not True:
            continue
        link = str(row.get("partners_link") or "")
        image = str(row.get("image_url") or "")
        title = str(row.get("title") or "").strip()
        try:
            product_id = int(row["id"])
            price = int(row["price"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ExportError("공개 상품의 id와 price가 올바르지 않습니다") from exc
        if product_id < 1 or price < 0 or not title or not link.startswith("https://link.coupang.com/"):
            raise ExportError(f"공개 상품 {product_id}의 필수 정보가 올바르지 않습니다")
        if not image.startswith("https://") and not image.startswith("images/"):
            raise ExportError(f"공개 상품 {product_id}의 이미지 URL이 올바르지 않습니다")
        added_at = str(row.get("created_at") or "")[:10]
        if len(added_at) != 10:
            raise ExportError(f"공개 상품 {product_id}의 생성일이 없습니다")
        products.append({
            "id": product_id,
            "title": title,
            "price": price,
            "image": image,
            "link": link,
            "addedAt": added_at,
            "active": True,
        })
    return {"profile": profile, "products": products}


def fetch_products(supabase_url: str, service_key: str) -> list[dict[str, Any]]:
    query = urllib.parse.urlencode({
        "select": "id,title,price,image_url,partners_link,stage,active,created_at",
        "partners_link": "not.is.null",
        "order": "id.asc",
    })
    request = urllib.request.Request(
        f"{supabase_url.rstrip('/')}/rest/v1/products?{query}",
        headers={"apikey": service_key, "Authorization": f"Bearer {service_key}"},
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        raise ExportError("Supabase 상품 조회에 실패했습니다") from exc
    if not isinstance(payload, list):
        raise ExportError("Supabase 상품 응답이 배열이 아닙니다")
    return payload


def main() -> int:
    supabase_url = os.environ.get("SUPABASE_URL", "")
    service_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if not supabase_url.startswith("https://") or not service_key:
        print("SUPABASE_URL과 SUPABASE_SERVICE_ROLE_KEY가 필요합니다", file=sys.stderr)
        return 2
    existing = json.loads(OUTPUT.read_text(encoding="utf-8"))
    profile = existing.get("profile")
    if not isinstance(profile, dict):
        print("site/products.json profile이 올바르지 않습니다", file=sys.stderr)
        return 2
    try:
        document = build_products_document(fetch_products(supabase_url, service_key), profile)
    except ExportError as exc:
        print(f"상품 export 오류: {exc}", file=sys.stderr)
        return 1
    temporary = OUTPUT.with_suffix(".json.tmp")
    temporary.write_text(
        json.dumps(document, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    temporary.replace(OUTPUT)
    print(f"공개 상품 export: {len(document['products'])}개")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
