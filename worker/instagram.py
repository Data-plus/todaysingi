"""Supabase signed URL을 Instagram Graph API에 한 번만 게시한다."""
from __future__ import annotations

import os
import re
import time
import urllib.parse
from typing import Any, Callable


GRAPH_VERSION = re.compile(r"^v\d{1,2}\.\d$")


class InstagramPublishError(RuntimeError):
    pass


def _video_url(value: str) -> str:
    parsed = urllib.parse.urlparse(str(value or ""))
    host = (parsed.hostname or "").lower()
    extra_hosts = {
        item.strip().lower()
        for item in os.environ.get("INSTAGRAM_VIDEO_HOSTS", "").split(",")
        if item.strip()
    }
    allowed = host.endswith(".supabase.co") or host == "todaysingi.netlify.app" or host in extra_hosts
    if parsed.scheme != "https" or not allowed:
        raise InstagramPublishError("Instagram 영상 URL host가 허용되지 않았습니다")
    return parsed.geturl()


def _json(response, context: str, token: str) -> dict[str, Any]:
    try:
        payload = response.json()
    except ValueError as exc:
        raise InstagramPublishError(f"{context} 응답이 JSON이 아닙니다") from exc
    if response.status_code >= 400:
        detail = str(payload)[:800].replace(token, "[REDACTED]")
        raise InstagramPublishError(f"{context} 실패: {detail}")
    return payload


def publish_reel_from_url(
    *,
    video_url: str,
    caption: str,
    thumb_offset_ms: int | None = None,
    ig_account_id: str | None = None,
    access_token: str | None = None,
    graph_version: str | None = None,
    session=None,
    sleep: Callable[[float], None] = time.sleep,
    poll_interval_seconds: int = 5,
    poll_timeout_seconds: int = 300,
) -> dict[str, str]:
    ig_account_id = str(ig_account_id or os.environ.get("INSTAGRAM_ACCOUNT_ID", ""))
    access_token = str(access_token or os.environ.get("INSTAGRAM_ACCESS_TOKEN", ""))
    graph_version = str(graph_version or os.environ.get("META_GRAPH_VERSION", "v21.0"))
    if not ig_account_id or not access_token:
        raise InstagramPublishError("Instagram 계정 ID와 access token이 필요합니다")
    if not GRAPH_VERSION.fullmatch(graph_version):
        raise InstagramPublishError("Meta Graph API version 형식이 올바르지 않습니다")
    caption = str(caption or "").strip()
    if not caption or len(caption) > 2200:
        raise InstagramPublishError("Instagram 캡션은 이천이백 자 이하여야 합니다")
    if thumb_offset_ms is not None and (
        not isinstance(thumb_offset_ms, int) or isinstance(thumb_offset_ms, bool) or thumb_offset_ms < 0
    ):
        raise InstagramPublishError("thumb_offset_ms가 올바르지 않습니다")
    if session is None:
        import requests
        session = requests.Session()
    graph = f"https://graph.facebook.com/{graph_version}"
    create_params: dict[str, Any] = {
        "media_type": "REELS",
        "video_url": _video_url(video_url),
        "caption": caption,
        "access_token": access_token,
    }
    if thumb_offset_ms is not None:
        create_params["thumb_offset"] = thumb_offset_ms
    created = _json(
        session.post(f"{graph}/{ig_account_id}/media", data=create_params, timeout=60),
        "Instagram 컨테이너 생성", access_token,
    )
    container_id = str(created.get("id") or "")
    if not container_id:
        raise InstagramPublishError("Instagram 컨테이너 ID가 없습니다")

    waited = 0
    while True:
        state = _json(
            session.get(
                f"{graph}/{container_id}",
                params={"fields": "status_code", "access_token": access_token},
                timeout=30,
            ),
            "Instagram 처리 상태", access_token,
        ).get("status_code", "UNKNOWN")
        if state in {"FINISHED", "PUBLISHED"}:
            break
        if state in {"ERROR", "EXPIRED"} or waited >= poll_timeout_seconds:
            raise InstagramPublishError(f"Instagram 영상 처리 실패 또는 시간초과: {state}")
        sleep(poll_interval_seconds)
        waited += poll_interval_seconds

    published = _json(
        session.post(
            f"{graph}/{ig_account_id}/media_publish",
            data={"creation_id": container_id, "access_token": access_token},
            timeout=60,
        ),
        "Instagram media_publish", access_token,
    )
    media_id = str(published.get("id") or "")
    if not media_id:
        raise InstagramPublishError("Instagram media ID가 없습니다")
    media = _json(
        session.get(
            f"{graph}/{media_id}",
            params={"fields": "permalink", "access_token": access_token},
            timeout=30,
        ),
        "Instagram permalink 조회", access_token,
    )
    permalink = str(media.get("permalink") or "")
    if not permalink.startswith("https://www.instagram.com/"):
        raise InstagramPublishError("Instagram permalink를 확인하지 못했습니다")
    return {"media_id": media_id, "permalink": permalink}
