from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTROL_DESK = ROOT / "admin" / "src" / "lib" / "controlDesk.ts"
APP = ROOT / "admin" / "src" / "App.tsx"
PERFORMANCE = ROOT / "admin" / "src" / "pages" / "PerformancePage.tsx"


def test_admin_loads_real_ga4_rows_and_integration_status():
    source = CONTROL_DESK.read_text(encoding="utf-8")

    assert '.from("ga4_product_daily")' in source
    assert '.from("ga4_traffic_daily")' in source
    assert '.from("integration_syncs")' in source
    assert "summarizeGa4" in source


def test_manual_refresh_invokes_edge_function_directly_without_cloud_queue():
    source = CONTROL_DESK.read_text(encoding="utf-8")
    app = APP.read_text(encoding="utf-8")

    assert 'functions.invoke("sync-ga4"' in source
    assert "request_ga4_sync" not in source
    assert "dispatch-worker" not in source
    assert "invokeGa4Sync" in app
    assert "await refresh()" in app


def test_performance_page_is_ga_dashboard_without_gcp_or_llm_cost_ui():
    source = PERFORMANCE.read_text(encoding="utf-8")

    assert "GA4 새로고침" in source
    assert "상품별 클릭" in source
    assert "유입 경로" in source
    assert "GCP 운영비" not in source
    assert "CLOUD COST" not in source
    assert "LLM" not in source
