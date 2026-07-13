import datetime as dt

import pytest

from worker.asset_cleanup import (
    CleanupError,
    cleanup_after_publish,
    cleanup_expired_assets,
    mark_failed_assets_for_expiry,
)


NOW = dt.datetime(2026, 7, 13, 9, 0, tzinfo=dt.timezone.utc)


def asset(asset_id, kind, *, retention="ephemeral", status="active", expires_at=None):
    return {
        "id": asset_id,
        "kind": kind,
        "bucket_id": "pipeline-assets",
        "storage_path": f"products/4/jobs/job/{asset_id}.mp4",
        "retention_class": retention,
        "cleanup_status": status,
        "deleted_at": None,
        "expires_at": expires_at,
    }


class FakeClient:
    def __init__(self, fail_delete=()):
        self.fail_delete = set(fail_delete)
        self.deleted = []
        self.updates = []

    def delete_storage_object(self, bucket, storage_path):
        asset_id = storage_path.rsplit("/", 1)[-1].split(".", 1)[0]
        if asset_id in self.fail_delete:
            raise RuntimeError("storage unavailable")
        self.deleted.append((bucket, storage_path))

    def update_asset(self, asset_id, **fields):
        self.updates.append((asset_id, fields))


def test_publish_cleanup_deletes_media_but_keeps_cover_and_text():
    client = FakeClient()
    assets = [
        asset("raw", "raw_video"), asset("muted", "muted_video"),
        asset("frame", "frame"), asset("voice", "voice"),
        asset("final", "final_video", retention="review"),
        asset("cover", "reel_cover", retention="keep"),
        asset("script", "script", retention="keep"),
        asset("caption", "caption", retention="keep"),
        asset("subtitle", "subtitle", retention="keep"),
    ]

    result = cleanup_after_publish(client, assets, published_media_id="ig-123", now=NOW)

    assert result == {"deleted": 5, "pending": 0, "kept": 4}
    assert {path.rsplit("/", 1)[-1] for _, path in client.deleted} == {
        "raw.mp4", "muted.mp4", "frame.mp4", "voice.mp4", "final.mp4",
    }
    deleted_updates = [fields for _, fields in client.updates if fields.get("cleanup_status") == "deleted"]
    assert len(deleted_updates) == 5
    assert all(fields["deleted_at"] == NOW.isoformat() for fields in deleted_updates)


def test_publish_cleanup_failure_stays_pending_without_failing_publish():
    client = FakeClient(fail_delete={"final"})

    result = cleanup_after_publish(
        client, [asset("final", "final_video", retention="review")],
        published_media_id="ig-123", now=NOW,
    )

    assert result == {"deleted": 0, "pending": 1, "kept": 0}
    assert client.updates[-1] == ("final", {"cleanup_status": "cleanup_pending"})


def test_publish_cleanup_requires_confirmed_instagram_media_id():
    with pytest.raises(CleanupError):
        cleanup_after_publish(FakeClient(), [asset("raw", "raw_video")], published_media_id="", now=NOW)


def test_failed_job_assets_expire_after_seven_days_but_keep_assets_do_not():
    client = FakeClient()
    assets = [asset("raw", "raw_video"), asset("script", "script", retention="keep")]

    changed = mark_failed_assets_for_expiry(client, assets, job_status="failed", now=NOW)

    assert changed == 1
    assert client.updates == [("raw", {"expires_at": "2026-07-20T09:00:00+00:00"})]


def test_review_waiting_assets_do_not_receive_an_expiry():
    client = FakeClient()
    assert mark_failed_assets_for_expiry(
        client, [asset("final", "final_video", retention="review")],
        job_status="succeeded", now=NOW,
    ) == 0
    assert client.updates == []


def test_expired_cleanup_is_idempotent_and_skips_already_deleted_assets():
    client = FakeClient()
    due = asset("due", "raw_video", expires_at="2026-07-13T08:00:00+00:00")
    deleted = asset("gone", "raw_video", status="deleted", expires_at="2026-07-12T00:00:00+00:00")
    deleted["deleted_at"] = "2026-07-12T00:00:00+00:00"

    result = cleanup_expired_assets(client, [due, deleted], now=NOW)

    assert result == {"deleted": 1, "pending": 0, "skipped": 1}
    assert len(client.deleted) == 1
