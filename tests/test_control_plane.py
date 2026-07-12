import datetime as dt
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "worker"))

from control_plane import (ControlPlaneError, build_job_command, pipeline_product_row,
                           redact_text, run_claimed_job)


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


def test_run_claimed_sync_job_updates_progress_and_result():
    client = FakeClient()
    job = {"id": "job-1", "type": "sync_pipeline", "payload": {}}
    run_claimed_job(client, job, REPO)
    assert ("sync",) in client.events
    final = [e for e in client.events if e[0] == "update"][-1]
    assert final[2]["status"] == "succeeded"
    assert final[2]["progress"] == 100
    assert final[2]["result"] == {"synced_products": 1}


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


def test_run_claimed_job_records_failure_without_raising():
    client = FakeClient()
    job = {"id": "job-3", "type": "dub", "product_id": 1, "payload": {}}

    def runner(command, **kwargs):
        return subprocess.CompletedProcess(command, 2, "", "ffmpeg failed")

    run_claimed_job(client, job, REPO, runner=runner)
    final = [e for e in client.events if e[0] == "update"][-1]
    assert final[2]["status"] == "failed"
    assert "ffmpeg failed" in final[2]["error_summary"]
