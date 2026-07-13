from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_worker_container_is_non_root_and_runs_cloud_entrypoint():
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    ignore = (ROOT / ".dockerignore").read_text(encoding="utf-8")

    assert dockerfile.startswith("FROM mcr.microsoft.com/playwright/python:v1.61.0-noble")
    assert "ffmpeg" in dockerfile
    assert "playwright==1.61.0" in (ROOT / "scripts" / "requirements.txt").read_text(encoding="utf-8")
    assert "playwright install-deps" not in dockerfile
    assert "playwright install chromium" not in dockerfile
    assert "USER appuser" in dockerfile
    assert 'CMD ["python", "-m", "worker.cloud_main", "--drain"]' in dockerfile
    assert ".env" in ignore
    assert "ops/assets" in ignore
    assert ".git" in ignore
