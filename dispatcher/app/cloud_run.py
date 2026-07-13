from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any

from fastapi import HTTPException, status

from .config import Settings


CLOUD_PLATFORM_SCOPE = "https://www.googleapis.com/auth/cloud-platform"


def job_run_url(settings: Settings) -> str:
    return (
        "https://run.googleapis.com/v2/projects/"
        f"{settings.gcp_project}/locations/{settings.gcp_region}/"
        f"jobs/{settings.cloud_run_job}:run"
    )


def adc_access_token() -> str:
    try:
        import google.auth
        from google.auth.transport.requests import Request
    except ImportError as exc:
        raise RuntimeError("google-auth is required") from exc
    credentials, _project = google.auth.default(scopes=[CLOUD_PLATFORM_SCOPE])
    if not credentials.valid:
        credentials.refresh(Request())
    if not credentials.token:
        raise RuntimeError("Google ADC did not return an access token")
    return str(credentials.token)


class CloudRunJobService:
    def __init__(
        self,
        settings: Settings,
        http_client,
        *,
        token_provider: Callable[[], str] = adc_access_token,
    ):
        self.settings = settings
        self.http_client = http_client
        self.token_provider = token_provider

    async def run(self) -> dict[str, Any]:
        try:
            token = await asyncio.to_thread(self.token_provider)
            response = await self.http_client.post(
                job_run_url(self.settings),
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                json={"overrides": {"containerOverrides": [{"args": ["--drain"]}]}},
                timeout=30,
            )
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Cloud Run 실행 요청을 보내지 못했습니다",
            ) from exc
        if response.status_code not in {200, 201, 202}:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Cloud Run이 실행 요청을 거부했습니다",
            )
        try:
            payload = response.json()
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Cloud Run 실행 응답이 올바르지 않습니다",
            ) from exc
        return {"operation": payload.get("name"), "accepted": True}
