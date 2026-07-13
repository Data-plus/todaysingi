from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_JS = ROOT / "site" / "app.js"


def test_product_click_uses_ga4_recommended_select_item_event():
    source = APP_JS.read_text(encoding="utf-8")

    assert 'gtag("event", "select_item"' in source
    assert 'item_list_id: "todaysingi_link_hub"' in source
    assert 'item_list_name: "오늘의신기템 링크 허브"' in source
    assert "items: [" in source
    assert "item_id: String(product.id).padStart(3, \"0\")" in source
    assert "item_name: product.title" in source
    assert 'gtag("event", "product_click"' not in source
