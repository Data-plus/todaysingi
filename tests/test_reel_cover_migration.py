from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
MIGRATION = ROOT / "supabase" / "migrations" / "202607120003_reel_covers.sql"


def sql_source():
    return MIGRATION.read_text(encoding="utf-8").lower()


def test_reel_cover_migration_adds_safe_job_and_asset_types():
    sql = sql_source()

    assert "drop constraint if exists jobs_type_check" in sql
    assert "generate_cover" in sql
    assert "drop constraint if exists assets_kind_check" in sql
    assert "cover_candidate" in sql
    assert "reel_cover" in sql
    assert "thumbnail" in sql
    assert "final_video" in sql


def test_reel_cover_migration_adds_non_null_metadata_and_lookup_index():
    sql = sql_source()

    assert "add column if not exists metadata jsonb" in sql
    assert "not null default '{}'::jsonb" in sql
    assert "create index if not exists assets_product_kind_idx" in sql
    assert "on public.assets (product_id, kind, created_at desc)" in sql


def test_reel_cover_migration_preserves_private_storage_and_rls():
    sql = sql_source()

    assert "alter table public.assets disable row level security" not in sql
    assert "update storage.buckets" not in sql
    assert "public = true" not in sql
