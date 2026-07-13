from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "supabase" / "migrations" / "202607130002_ga4_metrics.sql"


def migration_source() -> str:
    assert MIGRATION.exists(), "GA4 metrics migration is missing"
    return MIGRATION.read_text(encoding="utf-8").lower()


def test_ga4_daily_tables_have_stable_keys_and_non_negative_metrics():
    sql = migration_source()

    assert "create table if not exists public.ga4_product_daily" in sql
    assert "primary key (metric_date, item_id)" in sql
    assert "clicks bigint not null" in sql
    assert "clicks >= 0" in sql
    assert "create table if not exists public.ga4_traffic_daily" in sql
    assert "primary key (metric_date, source, medium)" in sql
    assert "sessions bigint not null" in sql
    assert "active_users bigint not null" in sql
    assert "create table if not exists public.integration_syncs" in sql
    assert "integration text primary key" in sql


def test_ga4_tables_are_private_and_admin_read_only():
    sql = migration_source()

    for table in ("ga4_product_daily", "ga4_traffic_daily", "integration_syncs"):
        assert f"alter table public.{table} enable row level security" in sql
        assert f"on public.{table} for select to authenticated" in sql
    assert sql.count("(select public.is_todaysingi_admin())") >= 3
    assert "revoke insert, update, delete" in sql
    assert "grant all on table public.ga4_product_daily" in sql


def test_ga4_metrics_are_replaced_atomically_by_service_role_only():
    sql = migration_source()

    assert "create or replace function public.replace_ga4_metrics" in sql
    assert "jsonb_to_recordset(p_product_rows)" in sql
    assert "jsonb_to_recordset(p_traffic_rows)" in sql
    assert "delete from public.ga4_product_daily" in sql
    assert "delete from public.ga4_traffic_daily" in sql
    assert "grant execute on function public.replace_ga4_metrics(date, date, jsonb, jsonb) to service_role" in sql
    assert "grant execute on function public.replace_ga4_metrics(date, date, jsonb, jsonb) to authenticated" not in sql


def test_ga4_schema_does_not_add_a_cloud_worker_queue():
    sql = migration_source()

    assert "request_ga4_sync" not in sql
    assert "jobs_one_active_sync_ga4" not in sql
    assert "alter table public.jobs" not in sql
