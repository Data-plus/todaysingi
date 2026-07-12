from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def source(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_admin_has_six_real_views_with_hash_navigation():
    shell = source("admin/src/components/AppShell.tsx")
    app = source("admin/src/App.tsx")

    for label in ["개요", "상품", "작업 큐", "성과 분석", "광고", "연동·설정"]:
        assert label in shell
    for component in [
        "OverviewPage",
        "ProductsPage",
        "JobsPage",
        "PerformancePage",
        "AdsPage",
        "SettingsPage",
    ]:
        assert component in app
    assert "window.location.hash" in app
    assert "hashchange" in app


def test_external_performance_metrics_are_nullable_and_have_waiting_state():
    types = source("admin/src/types/admin.ts")
    dashboard = source("admin/src/lib/dashboard.ts")
    performance = source("admin/src/pages/PerformancePage.tsx")

    for field in [
        "linkClicks: number | null",
        "orders: number | null",
        "revenue: number | null",
        "commission: number | null",
        "adSpend: number | null",
        "roas: number | null",
    ]:
        assert field in types
    assert '"waiting"' in types
    assert "연결 대기" in dashboard
    assert "연결 대기" in performance
    assert "Measurement ID" in performance
    assert "최종 승인" in performance


def test_control_desk_loads_details_and_exposes_safe_queue_actions():
    control_desk = source("admin/src/lib/controlDesk.ts")

    for field in ["payload", "result", "progress", "error_summary", "attempts"]:
        assert field in control_desk
    for function in [
        "cancelJob",
        "retryJob",
        "enqueuePipelineSync",
    ]:
        assert f"function {function}" in control_desk
    assert 'status === "queued"' in control_desk
    assert 'status === "failed"' in control_desk
    assert 'status === "cancelled"' in control_desk
    assert "publish_reel" in control_desk
    assert "ads_" in control_desk


def test_product_drawer_is_accessible_and_has_no_fake_external_numbers():
    drawer = source("admin/src/components/ProductDrawer.tsx")

    assert 'role="dialog"' in drawer
    assert 'aria-modal="true"' in drawer
    assert "aria-label" in drawer
    assert "관련 작업" in drawer
    assert "파트너스 링크" in drawer
    assert "연결 후 사용" in drawer


def test_legacy_editorial_hero_and_dead_review_action_are_removed():
    app = source("admin/src/App.tsx")
    styles = source("admin/src/styles.css")

    for legacy in ["hero-grid", "hero-collage", "object-feature", "영상 검수하기"]:
        assert legacy not in app
        assert legacy not in styles
    assert 'font-family:"Noto Serif KR",serif' not in styles


def test_responsive_and_accessible_console_states_are_styled():
    styles = source("admin/src/styles.css")

    assert ":focus-visible" in styles
    assert "cursor:not-allowed" in styles
    assert "@media (max-width:980px)" in styles
    assert "@media (max-width:640px)" in styles
    assert "prefers-reduced-motion" in styles


def test_demo_mode_disables_actions_that_need_live_supabase():
    shell = source("admin/src/components/AppShell.tsx")
    jobs = source("admin/src/pages/JobsPage.tsx")
    drawer = source("admin/src/components/ProductDrawer.tsx")

    assert "disabled={!live}" in shell
    assert "disabled={syncing || !live}" in jobs
    assert "disabled={busy || !live}" in drawer
    assert "Supabase 연결 후 사용할 수 있습니다" in shell
    assert "Supabase 연결 후 사용할 수 있습니다" in jobs
    assert "Supabase 연결 후 사용할 수 있습니다" in drawer


def test_worker_without_recent_heartbeat_is_offline_not_unconfigured():
    dashboard = source("admin/src/lib/dashboard.ts")

    assert 'label: data.worker.online ? "연결됨" : "오프라인"' in dashboard
    assert 'status: data.worker.online ? "connected" : "waiting"' in dashboard


def test_cover_editor_exposes_candidates_copy_and_real_generate_action():
    editor = source("admin/src/components/CoverEditor.tsx")
    drawer = source("admin/src/components/ProductDrawer.tsx")
    app = source("admin/src/App.tsx")
    control_desk = source("admin/src/lib/controlDesk.ts")

    assert "릴스 커버" in editor
    assert "cover_candidate" in editor
    assert "recommended" in editor
    assert "첫 번째 줄" in editor
    assert "두 번째 줄" in editor
    assert "커버 생성" in editor
    assert "CoverEditor" in drawer
    assert "enqueueGenerateCover" in app
    assert "function enqueueGenerateCover" in control_desk
    assert 'type: "generate_cover"' in control_desk


def test_private_cover_assets_receive_signed_urls_without_public_bucket():
    types = source("admin/src/types/admin.ts")
    control_desk = source("admin/src/lib/controlDesk.ts")

    assert "metadata: Record<string, unknown>" in types
    assert "signedUrl: string | null" in types
    assert 'from("completed-assets")' in control_desk
    assert "createSignedUrls" in control_desk
    assert "getPublicUrl" not in control_desk
