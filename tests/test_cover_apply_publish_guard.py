from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MIGRATION = ROOT / "supabase" / "migrations" / "202607140001_cover_apply_publish_guard.sql"


def sql_source():
    return MIGRATION.read_text(encoding="utf-8").lower()


def test_publish_rpc_rejects_active_cover_jobs():
    sql = sql_source()
    assert "create or replace function public.approve_publish_reel" in sql
    assert "type = 'generate_cover'" in sql
    for status in ("queued", "claimed", "running"):
        assert f"'{status}'" in sql
    assert "errcode = '55000'" in sql
    assert "커버 적용 작업이 완료된 후 게시할 수 있습니다" in sql


def test_publish_rpc_keeps_admin_and_readiness_guards():
    sql = sql_source()
    assert "public.is_todaysingi_admin()" in sql
    assert "product_stage <> 'caption_ready'" in sql
    assert "product_reel_url is not null" in sql
    assert "grant execute on function public.approve_publish_reel(bigint) to authenticated" in sql
