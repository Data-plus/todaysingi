"""게시 성공과 실패 보관 기간에 따른 Storage asset 정리 정책."""
from __future__ import annotations

import datetime as dt
from typing import Any, Iterable


POST_PUBLISH_DELETE_KINDS = {
    "raw_video", "muted_video", "frame", "voice", "final_video",
}


class CleanupError(ValueError):
    pass


def _utc(value: dt.datetime | None = None) -> dt.datetime:
    current = value or dt.datetime.now(dt.timezone.utc)
    if current.tzinfo is None:
        raise CleanupError("cleanup 시각에는 timezone이 필요합니다")
    return current.astimezone(dt.timezone.utc)


def _delete_one(client, asset: dict[str, Any], *, now: dt.datetime) -> bool:
    if asset.get("cleanup_status") == "deleted" or asset.get("deleted_at"):
        return True
    asset_id = str(asset.get("id") or "")
    bucket = str(asset.get("bucket_id") or "")
    storage_path = str(asset.get("storage_path") or "")
    if not asset_id or not bucket or not storage_path:
        raise CleanupError("삭제할 asset 식별자가 누락되었습니다")
    client.update_asset(asset_id, cleanup_status="cleanup_pending")
    try:
        client.delete_storage_object(bucket, storage_path)
    except Exception:
        client.update_asset(asset_id, cleanup_status="cleanup_pending")
        return False
    client.update_asset(
        asset_id,
        cleanup_status="deleted",
        deleted_at=now.isoformat(),
    )
    return True


def cleanup_after_publish(
    client,
    assets: Iterable[dict[str, Any]],
    *,
    published_media_id: str,
    now: dt.datetime | None = None,
) -> dict[str, int]:
    if not str(published_media_id or "").strip():
        raise CleanupError("Instagram 게시 성공 media ID가 있어야 정리할 수 있습니다")
    current = _utc(now)
    result = {"deleted": 0, "pending": 0, "kept": 0}
    for asset in assets:
        if asset.get("kind") not in POST_PUBLISH_DELETE_KINDS:
            result["kept"] += 1
            continue
        if _delete_one(client, asset, now=current):
            result["deleted"] += 1
        else:
            result["pending"] += 1
    return result


def mark_failed_assets_for_expiry(
    client,
    assets: Iterable[dict[str, Any]],
    *,
    job_status: str,
    now: dt.datetime | None = None,
) -> int:
    if job_status not in {"failed", "cancelled"}:
        return 0
    expires_at = (_utc(now) + dt.timedelta(days=7)).isoformat()
    changed = 0
    for asset in assets:
        if asset.get("retention_class") == "keep":
            continue
        if asset.get("expires_at") or asset.get("cleanup_status") == "deleted" or asset.get("deleted_at"):
            continue
        client.update_asset(str(asset["id"]), expires_at=expires_at)
        changed += 1
    return changed


def _parse_timestamp(value: Any) -> dt.datetime | None:
    if not value:
        return None
    try:
        parsed = dt.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError as exc:
        raise CleanupError("asset expires_at 형식이 올바르지 않습니다") from exc
    if parsed.tzinfo is None:
        raise CleanupError("asset expires_at에는 timezone이 필요합니다")
    return parsed.astimezone(dt.timezone.utc)


def cleanup_expired_assets(
    client,
    assets: Iterable[dict[str, Any]],
    *,
    now: dt.datetime | None = None,
) -> dict[str, int]:
    current = _utc(now)
    result = {"deleted": 0, "pending": 0, "skipped": 0}
    for asset in assets:
        if asset.get("cleanup_status") == "deleted" or asset.get("deleted_at"):
            result["skipped"] += 1
            continue
        expires_at = _parse_timestamp(asset.get("expires_at"))
        if expires_at is None or expires_at > current:
            result["skipped"] += 1
            continue
        if _delete_one(client, asset, now=current):
            result["deleted"] += 1
        else:
            result["pending"] += 1
    return result
