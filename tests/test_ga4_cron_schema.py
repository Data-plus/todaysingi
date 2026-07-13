from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "supabase" / "migrations" / "202607130003_ga4_cron.sql"


def cron_source() -> str:
    assert MIGRATION.exists(), "GA4 cron migration is missing"
    return MIGRATION.read_text(encoding="utf-8").lower()


def test_ga4_cron_runs_daily_at_0415_kst_and_is_idempotent():
    sql = cron_source()

    assert "todaysingi-ga4-daily" in sql
    assert "15 19 * * *" in sql
    assert "cron.unschedule" in sql
    assert "cron.schedule" in sql


def test_ga4_cron_reads_secrets_from_vault_only():
    sql = cron_source()

    assert "vault.decrypted_secrets" in sql
    assert "ga4_project_url" in sql
    assert "ga4_cron_secret" in sql
    assert "x-ga4-cron-secret" in sql
    assert "ga4_publishable_key" not in sql
    assert "'apikey'" not in sql
    assert "davyotbbhgnfxpgaglki" not in sql
    assert "sb_publishable_" not in sql
    assert "eyj" not in sql
