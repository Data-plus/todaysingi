from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EDGE = ROOT / "supabase" / "functions" / "dispatch-worker" / "index.ts"


def test_edge_dispatch_revalidates_admin_and_forwards_user_jwt():
    assert EDGE.exists()
    source = EDGE.read_text(encoding="utf-8")

    assert "auth.getUser(token)" in source
    assert "plusmg@gmail.com" in source
    assert 'Deno.env.get("CLOUD_DISPATCHER_URL")' in source
    assert '`Bearer ${token}`' in source
    assert "service_role" not in source.lower()
    assert "Access-Control-Allow-Origin" in source
