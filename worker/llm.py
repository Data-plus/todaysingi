"""공급자에 종속되지 않는 OpenAI-compatible JSON 콘텐츠 생성 경계."""
from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from typing import Any


AFFILIATE_DISCLOSURE = "이 포스팅은 쿠팡 파트너스 활동의 일환으로, 이에 따른 일정액의 수수료를 제공받습니다."
ASCII_DIGIT = re.compile(r"[0-9]")
FENCED_JSON = re.compile(r"^```(?:json)?\s*([\s\S]*?)\s*```$", re.IGNORECASE)


class LlmError(ValueError):
    pass


def parse_json_content(value: str) -> dict[str, Any]:
    text = str(value or "").strip()
    match = FENCED_JSON.fullmatch(text)
    if match:
        text = match.group(1).strip()
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise LlmError("LLM 응답이 단일 JSON 객체가 아닙니다") from exc
    if not isinstance(parsed, dict):
        raise LlmError("LLM 응답 최상위 값은 JSON 객체여야 합니다")
    return parsed


def _required_text(payload: Mapping[str, Any], key: str, *, maximum: int) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise LlmError(f"{key}가 비어 있습니다")
    clean = re.sub(r"\s+", " ", value).strip()
    if len(clean) > maximum:
        raise LlmError(f"{key}가 너무 깁니다")
    return clean


def validate_content_package(payload: Mapping[str, Any]) -> dict[str, Any]:
    hook = _required_text(payload, "hook", maximum=100)
    narration = _required_text(payload, "narration", maximum=900)
    caption = _required_text(payload, "caption", maximum=2000)
    if ASCII_DIGIT.search(narration):
        raise LlmError("게시용 대본의 숫자는 한글로 써야 합니다")
    cover_lines = payload.get("cover_lines")
    if not isinstance(cover_lines, list) or len(cover_lines) != 2:
        raise LlmError("cover_lines는 정확히 두 줄이어야 합니다")
    cover = []
    for line in cover_lines:
        if not isinstance(line, str) or not line.strip() or len(line.strip()) > 60:
            raise LlmError("커버 문구는 줄마다 육십 자 이하여야 합니다")
        cover.append(re.sub(r"\s+", " ", line).strip())
    hashtags = payload.get("hashtags", [])
    if not isinstance(hashtags, list) or len(hashtags) > 20:
        raise LlmError("hashtags 형식이 올바르지 않습니다")
    clean_hashtags = []
    for value in hashtags:
        if not isinstance(value, str):
            raise LlmError("hashtag는 문자열이어야 합니다")
        tag = re.sub(r"[^0-9A-Za-z가-힣_]", "", value.lstrip("#"))
        if tag and len(tag) <= 30 and tag not in clean_hashtags:
            clean_hashtags.append(tag)
    if AFFILIATE_DISCLOSURE not in caption:
        caption = f"{caption}\n\n{AFFILIATE_DISCLOSURE}"
    return {
        "hook": hook,
        "narration": narration,
        "caption": caption,
        "cover_lines": cover,
        "hashtags": clean_hashtags,
    }


def content_prompt(product: Mapping[str, Any], visual_analysis: Mapping[str, Any]) -> str:
    safe_product = {
        "title": str(product.get("title") or "")[:200],
        "price": product.get("price"),
        "description": str(product.get("description") or "")[:3000],
    }
    return (
        "아래 상품과 영상 분석을 바탕으로 한국어 인스타그램 릴스 패키지를 만드세요. "
        "과장된 효능이나 확인되지 않은 주장을 쓰지 말고, 내레이션의 모든 숫자는 한글로 쓰세요. "
        "hook, narration, caption, cover_lines(정확히 두 줄), hashtags 배열만 담은 JSON 객체로 답하세요.\n"
        f"상품: {json.dumps(safe_product, ensure_ascii=False)}\n"
        f"영상 분석: {json.dumps(dict(visual_analysis), ensure_ascii=False)[:6000]}"
    )


class JsonLlmClient:
    def __init__(self, endpoint: str, api_key: str, model: str, *, session=None):
        if not endpoint.startswith("https://"):
            raise LlmError("LLM_API_URL은 https:// URL이어야 합니다")
        if not api_key or not model:
            raise LlmError("LLM API key와 model이 필요합니다")
        if session is None:
            import requests
            session = requests.Session()
        self.endpoint = endpoint
        self.api_key = api_key
        self.model = model
        self.session = session

    def generate_json(
        self,
        prompt: str,
        *,
        system: str = "당신은 사실 확인을 중시하는 한국어 숏폼 콘텐츠 에디터입니다.",
        image_data_urls: Sequence[str] = (),
    ) -> dict[str, Any]:
        user_content: str | list[dict[str, Any]]
        if image_data_urls:
            user_content = [{"type": "text", "text": prompt}]
            user_content.extend({"type": "image_url", "image_url": {"url": url}} for url in image_data_urls)
        else:
            user_content = prompt
        response = self.session.post(
            self.endpoint,
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            json={
                "model": self.model,
                "response_format": {"type": "json_object"},
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user_content},
                ],
                "temperature": 0.7,
            },
            timeout=180,
        )
        if response.status_code >= 400:
            detail = str(getattr(response, "text", ""))[:1000].replace(self.api_key, "[REDACTED]")
            raise LlmError(f"LLM API {response.status_code}: {detail}")
        try:
            content = response.json()["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise LlmError("LLM API 응답 형식이 올바르지 않습니다") from exc
        return parse_json_content(content)
