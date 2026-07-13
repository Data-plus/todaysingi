from __future__ import annotations

import hmac
from typing import Any

from fastapi import HTTPException, status

from .config import Settings


async def verify_admin_token(token: str, settings: Settings, http_client) -> dict[str, Any]:
    if not token or len(token) > 8192:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="인증이 필요합니다")
    response = await http_client.get(
        f"{settings.supabase_url.rstrip('/')}/auth/v1/user",
        headers={
            "apikey": settings.supabase_anon_key,
            "Authorization": f"Bearer {token}",
        },
        timeout=15,
    )
    if response.status_code != 200:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="유효하지 않은 관리자 인증입니다")
    try:
        user = response.json()
        user_id = str(user.get("id") or "")
        email = str(user.get("email") or "").lower()
    except (AttributeError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="관리자 인증 응답이 올바르지 않습니다") from exc
    if not user_id or not hmac.compare_digest(email, settings.admin_email.lower()):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="허용된 관리자 계정이 아닙니다")
    return {"id": user_id, "email": email}
