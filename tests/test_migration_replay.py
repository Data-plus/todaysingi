from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = ROOT / "supabase" / "migrations"


def read(name: str) -> str:
    return (MIGRATIONS / name).read_text(encoding="utf-8").lower()


def test_dashboard_bootstrapped_migrations_are_safe_for_a_later_cli_replay():
    ga4 = read("202607130002_ga4_metrics.sql")
    assets = read("202607130003_pipeline_assets.sql")
    inputs = read("202607130004_pipeline_inputs.sql")
    export = read("202607130006_product_export.sql")

    assert ga4.count("create table if not exists public.") == 3
    assert "drop trigger if exists integration_syncs_touch_updated_at" in ga4
    assert ga4.count("drop policy if exists admin_read_") == 3
    assert "create unique index if not exists jobs_one_active_sync_ga4" in ga4
    assert "drop constraint if exists assets_retention_class_check" in assets
    assert "create unique index if not exists jobs_one_active_cleanup_assets" in assets
    assert "drop policy if exists admin_read_pipeline_assets" in assets
    assert "drop policy if exists admin_upload_pipeline_inputs" in inputs
    assert "drop policy if exists admin_delete_pipeline_inputs" in inputs
    assert "create index if not exists products_public_export_idx" in export
