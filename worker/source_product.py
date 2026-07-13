"""쿠팡 상품 페이지의 공개 메타데이터만 수집하고 차단 시 입력을 요청한다."""
from __future__ import annotations

import json
import re
import urllib.parse
from html.parser import HTMLParser
from typing import Any


class SourceInputRequired(RuntimeError):
    pass


def validate_coupang_url(value: str) -> str:
    parsed = urllib.parse.urlparse(str(value or ""))
    hostname = (parsed.hostname or "").lower()
    if parsed.scheme != "https" or not (hostname == "coupang.com" or hostname.endswith(".coupang.com")):
        raise ValueError("쿠팡 https URL만 사용할 수 있습니다")
    return parsed.geturl()


class _MetadataParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.meta: dict[str, str] = {}
        self.json_ld: list[str] = []
        self._json_buffer: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]):
        values = {key.lower(): value or "" for key, value in attrs}
        if tag.lower() == "meta":
            key = (values.get("property") or values.get("name") or "").lower()
            if key and values.get("content"):
                self.meta[key] = values["content"].strip()
        if tag.lower() == "script" and values.get("type", "").lower() == "application/ld+json":
            self._json_buffer = []

    def handle_data(self, data: str):
        if self._json_buffer is not None:
            self._json_buffer.append(data)

    def handle_endtag(self, tag: str):
        if tag.lower() == "script" and self._json_buffer is not None:
            self.json_ld.append("".join(self._json_buffer))
            self._json_buffer = None


def _walk_product(value: Any) -> dict[str, Any] | None:
    if isinstance(value, dict):
        kind = value.get("@type")
        if kind == "Product" or (isinstance(kind, list) and "Product" in kind):
            return value
        for nested in value.values():
            found = _walk_product(nested)
            if found:
                return found
    elif isinstance(value, list):
        for nested in value:
            found = _walk_product(nested)
            if found:
                return found
    return None


def _price(value: Any) -> int | None:
    if isinstance(value, dict):
        value = value.get("price") or value.get("lowPrice")
    text = re.sub(r"[^0-9.]", "", str(value or ""))
    if not text:
        return None
    try:
        number = int(float(text))
    except ValueError:
        return None
    return number if number >= 0 else None


def parse_coupang_product(html: str) -> dict[str, Any]:
    source = str(html or "")
    lowered = source.lower()
    if any(marker in lowered for marker in ("access denied", "captcha", "robot check")):
        raise SourceInputRequired("쿠팡 자동 접근이 차단되었습니다. 상품 정보를 직접 확인해 주세요")
    parser = _MetadataParser()
    parser.feed(source)
    product: dict[str, Any] = {}
    for block in parser.json_ld:
        try:
            parsed = json.loads(block)
        except json.JSONDecodeError:
            continue
        found = _walk_product(parsed)
        if found:
            product = found
            break
    title = parser.meta.get("og:title") or str(product.get("name") or "").strip()
    if not title:
        raise SourceInputRequired("쿠팡 상품 정보를 자동으로 읽지 못했습니다. 상품명을 입력해 주세요")
    image = parser.meta.get("og:image")
    if not image:
        raw_image = product.get("image")
        image = raw_image[0] if isinstance(raw_image, list) and raw_image else raw_image
    description = parser.meta.get("og:description") or str(product.get("description") or "").strip()
    price = _price(parser.meta.get("product:price:amount")) or _price(product.get("offers"))
    return {
        "title": re.sub(r"\s+", " ", title).strip()[:300],
        "image_url": str(image or "").strip() or None,
        "description": re.sub(r"\s+", " ", description).strip()[:5000],
        "price": price,
    }


def fetch_coupang_product(url: str, *, session=None) -> dict[str, Any]:
    validated = validate_coupang_url(url)
    if session is None:
        import requests
        session = requests.Session()
    response = session.get(
        validated,
        headers={"User-Agent": "Mozilla/5.0 (compatible; todaysingi-product-source/1.0)"},
        timeout=30,
        allow_redirects=True,
    )
    if response.status_code in {403, 429}:
        raise SourceInputRequired("쿠팡 자동 접근이 차단되었습니다. 상품 정보를 직접 입력해 주세요")
    if response.status_code >= 400:
        raise SourceInputRequired(f"쿠팡 상품 페이지를 읽지 못했습니다 ({response.status_code})")
    validate_coupang_url(str(response.url))
    return parse_coupang_product(response.text)
