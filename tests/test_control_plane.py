import datetime as dt
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "worker"))

from control_plane import (ControlPlaneError, build_job_command, cover_asset_specs,
                           pipeline_product_row, redact_text, run_claimed_job)


NOW = dt.datetime(2026, 7, 12, 18, 30, tzinfo=dt.timezone.utc)
REPO = Path("C:/repo/todaysingi")


def sample_item():
    return {
        "id": 1,
        "title": "불쏘는 마법지팡이",
        "coupangUrl": "https://link.coupang.com/a/test",
        "stage": "linked",
        "history": [{"stage": "linked", "at": "2026-07-12T11:55:37"}],
        "data": {
            "aliUrl": "https://ko.aliexpress.com/item/1.html",
            "partnersLink": "https://link.coupang.com/a/test",
            "reelUrl": "https://www.instagram.com/reel/test/",
            "igMediaId": "12345",
            "siteProductId": "1",
        },
        "note": "첫 상품",
    }


def test_pipeline_product_row_preserves_operational_links():
    row = pipeline_product_row(sample_item(), now=NOW)
    assert row["id"] == 1
    assert row["title"] == "불쏘는 마법지팡이"
    assert row["stage"] == "linked"
    assert row["ali_url"].startswith("https://ko.aliexpress.com")
    assert row["partners_link"].startswith("https://link.coupang.com")
    assert row["reel_url"].startswith("https://www.instagram.com")
    assert row["ig_media_id"] == "12345"
    assert row["site_product_id"] == "1"
    assert row["local_snapshot"]["history"][-1]["stage"] == "linked"
    assert row["synced_at"] == "2026-07-12T18:30:00+00:00"


@pytest.mark.parametrize("field", ["id", "title", "coupangUrl", "stage"])
def test_pipeline_product_row_rejects_missing_required_field(field):
    item = sample_item()
    del item[field]
    with pytest.raises(ControlPlaneError):
        pipeline_product_row(item, now=NOW)


def test_redact_text_masks_known_secrets_and_bearer_tokens():
    raw = (
        "TYPECAST_API_KEY=tc-secret\n"
        "SUPABASE_SERVICE_ROLE_KEY=service-secret\n"
        "Authorization: Bearer eyJverylongtoken.value.signature"
    )
    clean = redact_text(raw)
    assert "tc-secret" not in clean
    assert "service-secret" not in clean
    assert "eyJverylongtoken" not in clean
    assert clean.count("[REDACTED]") == 3


def test_build_dub_command_uses_argument_list_and_whitelist():
    job = {
        "type": "dub",
        "product_id": 7,
        "payload": {
            "voice": "tc_abc-123",
            "emotion": "toneup",
            "intensity": 1.5,
            "rate": "-5%",
        },
    }
    command = build_job_command(job, REPO, python_executable="python")
    assert command == [
        "python", str(REPO / "scripts" / "dub.py"), "7",
        "--engine", "typecast", "--voice", "tc_abc-123",
        "--emotion", "toneup", "--intensity", "1.5", "--rate=-5%",
    ]


def test_build_create_product_command_uses_existing_pipeline_cli():
    job = {
        "type": "create_product",
        "product_id": 2,
        "payload": {
            "title": "접이식 미니 가습기",
            "coupang_url": "https://www.coupang.com/vp/products/2",
            "note": "원격 등록",
        },
    }
    command = build_job_command(job, REPO, python_executable="python")
    assert command == [
        "python", str(REPO / "scripts" / "pipeline.py"), "new",
        "--title", "접이식 미니 가습기",
        "--coupang-url", "https://www.coupang.com/vp/products/2",
        "--note", "원격 등록",
    ]


def test_pipeline_projection_omits_absent_optional_links_to_preserve_remote_values():
    item = sample_item()
    item["data"] = {}
    row = pipeline_product_row(item, now=NOW)
    assert "ali_url" not in row
    assert "partners_link" not in row


@pytest.mark.parametrize("payload", [
    {"rate": "-5%; whoami"},
    {"voice": "tc_ok && calc.exe"},
    {"emotion": "unknown"},
    {"intensity": 99},
])
def test_build_dub_command_rejects_unsafe_payload(payload):
    job = {"type": "dub", "product_id": 1, "payload": payload}
    with pytest.raises(ControlPlaneError):
        build_job_command(job, REPO)


def test_publish_job_requires_explicit_approval_timestamp():
    job = {"type": "publish_reel", "product_id": 1, "payload": {}, "approved_at": None}
    with pytest.raises(ControlPlaneError, match="승인"):
        build_job_command(job, REPO)


def test_build_generate_cover_command_validates_and_passes_overrides():
    job = {
        "type": "generate_cover",
        "product_id": 2,
        "payload": {
            "frame": 5,
            "line1": "키링인 줄 알았죠?",
            "line2": "진짜 카메라입니다.",
        },
    }

    assert build_job_command(job, REPO, python_executable="python") == [
        "python", str(REPO / "scripts" / "make_cover.py"), "2",
        "--frame", "5",
        "--line1", "키링인 줄 알았죠?",
        "--line2", "진짜 카메라입니다.",
    ]


@pytest.mark.parametrize("payload", [
    {"frame": 0},
    {"frame": 7},
    {"frame": "2"},
    {"line1": ""},
    {"line2": "가" * 61},
    {"line1": "첫 줄\n명령"},
])
def test_build_generate_cover_command_rejects_unsafe_payload(payload):
    with pytest.raises(ControlPlaneError):
        build_job_command({"type": "generate_cover", "product_id": 2, "payload": payload}, REPO)


def test_cover_asset_specs_include_candidates_and_final_metadata(tmp_path):
    workdir = tmp_path / "ops" / "assets" / "2"
    frames = workdir / "frames"
    frames.mkdir(parents=True)
    (frames / "f01.jpg").write_bytes(b"one")
    (frames / "f02.jpg").write_bytes(b"two")
    (workdir / "cover.jpg").write_bytes(b"cover")
    (workdir / "cover.json").write_text(
        '{"recommendedFrame":2,"selectedFrame":2,"line1":"첫 줄",'
        '"line2":"둘째 줄","thumbOffsetMs":14550,"version":1,'
        '"scores":{"1":{"score":0.1},"2":{"score":0.9}}}',
        encoding="utf-8",
    )

    specs = cover_asset_specs(tmp_path, 2, job_id="job-cover")

    assert [spec["storage_path"] for spec in specs] == [
        "covers/2/candidate-01.jpg",
        "covers/2/candidate-02.jpg",
        "covers/2/cover.jpg",
    ]
    assert specs[1]["row"]["kind"] == "cover_candidate"
    assert specs[1]["row"]["metadata"]["recommended"] is True
    assert specs[2]["row"]["kind"] == "reel_cover"
    assert specs[2]["row"]["metadata"]["thumbOffsetMs"] == 14550
    assert specs[2]["row"]["job_id"] == "job-cover"


class FakeClient:
    def __init__(self):
        self.events = []

    def update_job(self, job_id, **fields):
        self.events.append(("update", job_id, fields))

    def log(self, job_id, message, level="info"):
        self.events.append(("log", job_id, level, message))

    def sync_pipeline(self):
        self.events.append(("sync",))
        return 1

    def get_product(self, product_id):
        self.events.append(("product", product_id))
        return {"id": product_id, "ig_media_id": "ig-confirmed"}

    def list_product_assets(self, product_id):
        self.events.append(("assets", product_id))
        return [{"id": "asset-final", "kind": "final_video"}]


def test_run_claimed_sync_job_updates_progress_and_result():
    client = FakeClient()
    job = {"id": "job-1", "type": "sync_pipeline", "payload": {}}
    run_claimed_job(client, job, REPO)
    assert ("sync",) in client.events
    final = [e for e in client.events if e[0] == "update"][-1]
    assert final[2]["status"] == "succeeded"
    assert final[2]["progress"] == 100
    assert final[2]["result"] == {"synced_products": 1}


def test_run_claimed_ga4_job_uses_data_syncer_without_a_cli_command():
    client = FakeClient()
    job = {"id": "job-ga4", "type": "sync_ga4", "payload": {"days": 30}}
    calls = []

    def ga4_syncer(received_client, payload):
        calls.append((received_client, payload))
        return {"stored_rows": 12, "range_start": "2026-06-14", "range_end": "2026-07-13"}

    assert build_job_command(job, REPO) is None
    run_claimed_job(client, job, REPO, ga4_syncer=ga4_syncer)

    assert calls == [(client, {"days": 30})]
    final = [event for event in client.events if event[0] == "update"][-1]
    assert final[2]["status"] == "succeeded"
    assert final[2]["result"]["stored_rows"] == 12


def test_run_claimed_cli_job_redacts_output_and_marks_success():
    client = FakeClient()
    job = {"id": "job-2", "type": "dub", "product_id": 1, "payload": {}}

    def runner(command, **kwargs):
        assert isinstance(command, list)
        return subprocess.CompletedProcess(command, 0, "TYPECAST_API_KEY=hidden", "")

    run_claimed_job(client, job, REPO, runner=runner)
    log_messages = [e[3] for e in client.events if e[0] == "log"]
    assert any("[REDACTED]" in message for message in log_messages)
    assert all("hidden" not in message for message in log_messages)
    assert ("sync",) in client.events
    assert [e for e in client.events if e[0] == "update"][-1][2]["status"] == "succeeded"


def test_publish_cleanup_runs_only_after_success_and_confirmed_media_id():
    client = FakeClient()
    job = {
        "id": "job-publish", "type": "publish_reel", "product_id": 1,
        "payload": {}, "approved_at": "2026-07-13T09:00:00+00:00",
    }
    cleanups = []

    def runner(command, **kwargs):
        return subprocess.CompletedProcess(command, 0, "published", "")

    def cleaner(received_client, assets, *, published_media_id):
        cleanups.append((received_client, assets, published_media_id))
        return {"deleted": 1, "pending": 0, "kept": 0}

    run_claimed_job(client, job, REPO, runner=runner, asset_cleaner=cleaner)

    assert cleanups == [(client, [{"id": "asset-final", "kind": "final_video"}], "ig-confirmed")]
    final = [event for event in client.events if event[0] == "update"][-1]
    assert final[2]["status"] == "succeeded"
    assert final[2]["result"]["cleanup"]["deleted"] == 1


def test_publish_failure_never_calls_success_cleanup():
    client = FakeClient()
    job = {
        "id": "job-publish-fail", "type": "publish_reel", "product_id": 1,
        "payload": {}, "approved_at": "2026-07-13T09:00:00+00:00",
    }
    cleanups = []

    def runner(command, **kwargs):
        return subprocess.CompletedProcess(command, 2, "", "Meta publish failed")

    run_claimed_job(client, job, REPO, runner=runner, asset_cleaner=lambda *args, **kwargs: cleanups.append(True))

    assert cleanups == []
    assert [event for event in client.events if event[0] == "update"][-1][2]["status"] == "failed"


def test_run_claimed_job_records_failure_without_raising():
    client = FakeClient()
    job = {"id": "job-3", "type": "dub", "product_id": 1, "payload": {}}

    def runner(command, **kwargs):
        return subprocess.CompletedProcess(command, 2, "", "ffmpeg failed")

    run_claimed_job(client, job, REPO, runner=runner)
    final = [e for e in client.events if e[0] == "update"][-1]
    assert final[2]["status"] == "failed"
    assert "ffmpeg failed" in final[2]["error_summary"]
