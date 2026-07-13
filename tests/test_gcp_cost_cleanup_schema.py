from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "supabase" / "migrations" / "202607130008_remove_gcp_cost_monitoring.sql"


def cleanup_source() -> str:
    assert MIGRATION.exists(), "GCP cost cleanup migration is missing"
    return MIGRATION.read_text(encoding="utf-8").lower()


def test_cleanup_removes_only_gcp_cost_experiment_objects():
    sql = cleanup_source()

    assert "drop table if exists public.gcp_cost_daily" in sql
    assert "drop table if exists public.gcp_cost_settings" in sql
    assert "drop function if exists public.get_gcp_cost_overview" in sql
    assert "drop function if exists public.replace_gcp_costs" in sql
    assert "drop function if exists public.request_gcp_cost_sync" in sql
    assert "integration = 'gcp_billing'" in sql
    assert "type = 'sync_gcp_costs'" in sql


def test_cleanup_preserves_ga4_and_local_pipeline_data():
    sql = cleanup_source()

    assert "drop table if exists public.ga4" not in sql
    assert "drop table if exists public.products" not in sql
    assert "drop table if exists public.jobs" not in sql
    assert "delete from public.jobs" in sql
    assert "where type = 'sync_gcp_costs'" in sql
