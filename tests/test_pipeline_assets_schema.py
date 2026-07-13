from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "supabase" / "migrations" / "202607130003_pipeline_assets.sql"


def source() -> str:
    assert MIGRATION.exists(), "pipeline asset migration is missing"
    return MIGRATION.read_text(encoding="utf-8").lower()


def test_pipeline_bucket_is_private_and_server_written():
    sql = source()

    assert "'pipeline-assets', 'pipeline-assets', false" in sql
    assert "admin_read_pipeline_assets" in sql
    assert "bucket_id = 'pipeline-assets'" in sql
    assert "admin_write_pipeline_assets" not in sql


def test_assets_have_retention_and_cleanup_lifecycle():
    sql = source()

    for column in ("bucket_id", "retention_class", "expires_at", "cleanup_status", "deleted_at"):
        assert f"add column if not exists {column}" in sql
    for kind in ("raw_video", "muted_video", "frame", "script", "voice", "subtitle", "final_video", "reel_cover", "caption"):
        assert f"'{kind}'" in sql
    assert "assets_cleanup_due_idx" in sql


def test_jobs_support_remote_pipeline_waiting_input_and_cleanup():
    sql = source()

    assert "'waiting_input'" in sql
    for job_type in (
        "source_product", "source_video", "analyze_video", "generate_script",
        "generate_voice", "compose_video", "generate_caption", "cleanup_assets",
    ):
        assert f"'{job_type}'" in sql
    assert "jobs_one_active_cleanup_assets" in sql
