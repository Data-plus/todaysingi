from pathlib import Path


SQL = (Path(__file__).resolve().parent.parent / "supabase" / "migrations" /
       "202607120001_admin_control_plane.sql").read_text(encoding="utf-8").lower()


def test_every_private_table_enables_rls():
    for table in ("products", "workers", "jobs", "job_logs", "assets", "activity_logs"):
        assert f"alter table public.{table} enable row level security" in SQL


def test_job_claim_is_atomic_and_service_role_only():
    assert "for update skip locked" in SQL
    assert "revoke all on function public.claim_next_job(text, integer) from public, anon, authenticated" in SQL
    assert "grant execute on function public.claim_next_job(text, integer) to service_role" in SQL


def test_completed_assets_bucket_is_private():
    assert "'completed-assets', 'completed-assets', false" in SQL


def test_only_owner_email_is_accepted_by_admin_helper():
    assert "plusmg@gmail.com" in SQL
    assert "auth.jwt()" in SQL
