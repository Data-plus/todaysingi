import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "worker"))

from control_plane import build_job_command  # noqa: E402


def test_approved_publish_job_builds_existing_publish_cli_command():
    job = {
        "type": "publish_reel",
        "product_id": 7,
        "payload": {"requested_from": "admin"},
        "approved_at": "2026-07-13T10:00:00+00:00",
    }

    command = build_job_command(job, ROOT, python_executable="python-test")

    assert command == ["python-test", str(ROOT / "scripts" / "publish_reel.py"), "7"]
