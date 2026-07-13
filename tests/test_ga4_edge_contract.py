from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "supabase" / "functions" / "sync-ga4" / "index.ts"
LOGIC = ROOT / "supabase" / "functions" / "sync-ga4" / "ga4.ts"


def test_edge_function_keeps_ga_credentials_server_side():
    assert INDEX.exists(), "sync-ga4 Edge Function is missing"
    source = INDEX.read_text(encoding="utf-8")

    assert 'Deno.env.get("GA4_SERVICE_ACCOUNT_JSON")' in source
    assert 'Deno.env.get("GA4_PROPERTY_ID")' in source
    assert 'Deno.env.get("GA4_CRON_SECRET")' in source
    assert 'Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")' in source
    assert "private_key" not in source.lower().replace("credentials.private_key", "")
    assert "console.log(credentials" not in source
    assert "access_token" not in source.lower().replace("tokenresult.access_token", "")


def test_edge_function_has_admin_and_cron_auth_boundaries():
    source = INDEX.read_text(encoding="utf-8")

    assert 'request.headers.get("x-ga4-cron-secret")' in source
    assert 'request.headers.get("authorization")' in source
    assert 'Deno.env.get("ADMIN_EMAIL")' in source
    assert "timingsafeequal" in source.lower()
    assert "auth.getuser" in source.lower()


def test_edge_function_uses_one_atomic_replace_rpc():
    source = INDEX.read_text(encoding="utf-8")

    assert '.rpc("replace_ga4_metrics"' in source
    assert '.from("integration_syncs")' in source
    assert "Promise.all" in source
    assert LOGIC.exists(), "GA4 pure logic module is missing"
