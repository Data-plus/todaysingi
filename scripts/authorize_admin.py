#!/usr/bin/env python3
"""GitHub identity가 확인된 Supabase 사용자를 관리자 허용 목록에 등록한다."""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any, Iterable

import requests


REPO_ROOT = Path(__file__).resolve().parent.parent


class AdminAuthorizationError(ValueError):
    pass


def load_env(path: Path = REPO_ROOT / ".env") -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"\'')
    return values


def user_providers(user: dict[str, Any]) -> set[str]:
    providers: set[str] = set()
    app_metadata = user.get("app_metadata")
    if isinstance(app_metadata, dict):
        raw = app_metadata.get("providers")
        if isinstance(raw, str):
            providers.add(raw.lower())
        elif isinstance(raw, list):
            providers.update(
                item.lower() for item in raw if isinstance(item, str)
            )
        primary = app_metadata.get("provider")
        if isinstance(primary, str):
            providers.add(primary.lower())
    identities = user.get("identities")
    if isinstance(identities, list):
        for identity in identities:
            if isinstance(identity, dict) and isinstance(identity.get("provider"), str):
                providers.add(identity["provider"].lower())
    return providers


def select_admin_user(
    users: Iterable[dict[str, Any]], email: str, required_provider: str,
) -> dict[str, Any]:
    normalized_email = email.strip().lower()
    matches = [
        user for user in users
        if isinstance(user.get("email"), str)
        and user["email"].strip().lower() == normalized_email
    ]
    if not matches:
        raise AdminAuthorizationError(f"Supabase Auth 사용자를 찾을 수 없습니다: {email}")
    if len(matches) > 1:
        raise AdminAuthorizationError(f"같은 이메일의 사용자가 여러 명입니다: {email}")
    user = matches[0]
    provider = required_provider.strip().lower()
    if provider and provider not in user_providers(user):
        raise AdminAuthorizationError(
            f"{email} 계정에 {provider} identity가 연결되지 않았습니다"
        )
    user_id = user.get("id")
    if not isinstance(user_id, str) or not user_id:
        raise AdminAuthorizationError("Supabase Auth 사용자 UUID가 없습니다")
    return user


def _response_json(response: requests.Response) -> Any:
    try:
        return response.json()
    except ValueError as exc:
        raise AdminAuthorizationError("Supabase 응답이 JSON 형식이 아닙니다") from exc


def authorize_admin(
    base_url: str,
    service_key: str,
    email: str,
    required_provider: str = "github",
    *,
    session: requests.Session | None = None,
) -> str:
    if not base_url.startswith("https://"):
        raise AdminAuthorizationError("SUPABASE_URL은 https:// URL이어야 합니다")
    if not service_key:
        raise AdminAuthorizationError("SUPABASE_SERVICE_ROLE_KEY가 없습니다")
    client = session or requests.Session()
    headers = {
        "apikey": service_key,
        "Authorization": f"Bearer {service_key}",
        "Content-Type": "application/json",
    }
    users_response = client.get(
        f"{base_url.rstrip('/')}/auth/v1/admin/users",
        params={"page": 1, "per_page": 1000},
        headers=headers,
        timeout=20,
    )
    if not users_response.ok:
        raise AdminAuthorizationError(
            f"Supabase Auth 사용자 조회 실패 ({users_response.status_code})"
        )
    payload = _response_json(users_response)
    users = payload.get("users") if isinstance(payload, dict) else None
    if not isinstance(users, list):
        raise AdminAuthorizationError("Supabase Auth 사용자 목록이 없습니다")
    user = select_admin_user(users, email, required_provider)

    upsert_response = client.post(
        f"{base_url.rstrip('/')}/rest/v1/admin_users",
        params={"on_conflict": "user_id"},
        headers={
            **headers,
            "Prefer": "resolution=merge-duplicates,return=minimal",
        },
        json={"user_id": user["id"]},
        timeout=20,
    )
    if not upsert_response.ok:
        raise AdminAuthorizationError(
            f"관리자 UUID 등록 실패 ({upsert_response.status_code})"
        )
    return user["id"]


def config() -> tuple[str, str]:
    file_env = load_env()
    get = lambda key: os.environ.get(key) or file_env.get(key, "")
    return get("SUPABASE_URL"), get("SUPABASE_SERVICE_ROLE_KEY")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="GitHub identity가 연결된 사용자를 관리자 UUID로 허용합니다",
    )
    parser.add_argument("--email", required=True, help="허용할 Supabase Auth 이메일")
    parser.add_argument(
        "--require-provider", default="github", help="필수 identity provider",
    )
    args = parser.parse_args(argv)
    base_url, service_key = config()
    try:
        authorize_admin(
            base_url, service_key, args.email, args.require_provider,
        )
    except AdminAuthorizationError as exc:
        print(f"관리자 등록 실패: {exc}", file=sys.stderr)
        return 1
    print(f"관리자 허용 완료: {args.email.lower()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
