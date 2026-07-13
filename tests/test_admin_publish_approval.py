from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
MIGRATION = ROOT / "supabase" / "migrations" / "202607130001_admin_publish_approval.sql"


def sql_source():
    return MIGRATION.read_text(encoding="utf-8").lower()


def test_publish_approval_migration_requires_explicit_admin_approval():
    sql = sql_source()

    assert "create or replace function public.approve_publish_reel(p_product_id bigint)" in sql
    assert "security definer" in sql
    assert "public.is_todaysingi_admin()" in sql
    assert "auth.uid()" in sql
    assert "approved_at" in sql
    assert "approved_by" in sql
    assert "max_attempts" in sql
    assert "max_attempts = 1" in sql


def test_publish_approval_migration_checks_product_readiness():
    sql = sql_source()

    assert "product_stage <> 'caption_ready'" in sql
    assert "product_reel_url is not null" in sql
    assert "publish_reel_requires_approval" in sql
    assert "approved_at is not null" in sql
    assert "approved_by is not null" in sql


def test_publish_approval_migration_prevents_two_active_jobs():
    sql = sql_source()

    assert "create unique index" in sql
    assert "jobs_one_active_publish_reel_per_product" in sql
    assert "where type = 'publish_reel'" in sql
    for status in ("queued", "claimed", "running"):
        assert f"'{status}'" in sql


def test_publish_approval_rpc_is_admin_only_and_audited():
    sql = sql_source()

    assert "insert into public.activity_logs" in sql
    assert "revoke all on function public.approve_publish_reel(bigint)" in sql
    assert "grant execute on function public.approve_publish_reel(bigint) to authenticated" in sql
    assert "from public.jobs" in sql
    assert "return existing_job_id" in sql
