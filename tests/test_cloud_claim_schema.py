from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "supabase" / "migrations" / "202607130005_cloud_worker_claim.sql"


def test_cloud_claim_only_selects_cloud_safe_jobs_with_skip_locked():
    assert MIGRATION.exists()
    sql = MIGRATION.read_text(encoding="utf-8").lower()

    assert "create or replace function public.claim_next_cloud_job" in sql
    assert "for update skip locked" in sql
    for job_type in (
        "sync_ga4", "cleanup_assets", "source_product", "source_video",
        "analyze_video", "generate_script", "generate_voice", "compose_video",
        "generate_cover", "generate_caption", "publish_reel", "export_products",
    ):
        assert f"'{job_type}'" in sql
    assert "max_attempts = 1" in sql
    assert "grant execute on function public.claim_next_cloud_job(text, integer) to service_role" in sql
