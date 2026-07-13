import asyncio
from pathlib import Path

import pytest
from fastapi import HTTPException

from dispatcher.app.config import Settings
from dispatcher.app.cloud_run import job_run_url
from dispatcher.app.security import verify_admin_token


ROOT = Path(__file__).resolve().parents[1]


class FakeResponse:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload
        self.text = str(payload)

    def json(self):
        return self._payload


class FakeHttpClient:
    def __init__(self, response):
        self.response = response
        self.calls = []

    async def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return self.response


def settings():
    return Settings(
        supabase_url="https://project.supabase.co",
        supabase_anon_key="anon-key",
        admin_email="plusmg@gmail.com",
        gcp_project="project",
        gcp_region="asia-northeast3",
        cloud_run_job="todaysingi-worker",
    )


def test_supabase_auth_user_must_match_the_only_admin():
    client = FakeHttpClient(FakeResponse(200, {"id": "user-1", "email": "plusmg@gmail.com"}))
    user = asyncio.run(verify_admin_token("valid-jwt", settings(), client))
    assert user == {"id": "user-1", "email": "plusmg@gmail.com"}
    assert client.calls[0][1]["headers"]["Authorization"] == "Bearer valid-jwt"


@pytest.mark.parametrize("response", [
    FakeResponse(401, {"message": "bad jwt"}),
    FakeResponse(200, {"id": "user-2", "email": "attacker@example.com"}),
    FakeResponse(200, {"id": "", "email": "plusmg@gmail.com"}),
])
def test_invalid_or_non_admin_supabase_identity_is_rejected(response):
    with pytest.raises(HTTPException) as caught:
        asyncio.run(verify_admin_token("bad-jwt", settings(), FakeHttpClient(response)))
    assert caught.value.status_code in {401, 403}
    assert "bad jwt" not in str(caught.value.detail)


def test_settings_require_https_supabase_and_a_safe_job_name():
    with pytest.raises(ValueError):
        Settings(
            supabase_url="http://project.supabase.co",
            supabase_anon_key="anon",
            admin_email="plusmg@gmail.com",
            gcp_project="project",
            gcp_region="asia-northeast3",
            cloud_run_job="worker; rm -rf",
        )


def test_cloud_run_job_url_is_built_from_validated_settings():
    assert job_run_url(settings()) == (
        "https://run.googleapis.com/v2/projects/project/locations/asia-northeast3/"
        "jobs/todaysingi-worker:run"
    )


def test_dispatcher_container_is_digest_pinned_and_non_root():
    dockerfile = (ROOT / "dispatcher" / "Dockerfile").read_text(encoding="utf-8")

    assert dockerfile.startswith("FROM python:3.12-slim@sha256:")
    assert "USER appuser" in dockerfile
    assert "uvicorn app.main:app" in dockerfile
