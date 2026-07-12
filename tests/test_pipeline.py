import datetime as dt
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from pipeline import (SLUGS, ValidationError, advance_item, load_data,
                      new_item, next_action, parse_sets, render_dashboard,
                      save_data)

NOW = dt.datetime(2026, 7, 12, 15, 0, 0)


def make_data(items=None):
    return {"items": items if items is not None else []}


def add_sample(data, title="접이식 미니 가습기", url="https://www.coupang.com/vp/products/1"):
    return new_item(data, title=title, coupang_url=url, now=NOW)


def test_new_item_seeds_fields():
    data = make_data()
    item = add_sample(data)
    assert item["id"] == 1
    assert item["stage"] == "sourced"
    assert item["history"] == [{"stage": "sourced", "at": "2026-07-12T15:00:00"}]
    assert item["data"] == {}
    assert data["items"][-1] is item


def test_new_item_id_is_max_plus_one():
    data = make_data([{"id": 5, "coupangUrl": "https://www.coupang.com/vp/products/5"}])
    item = add_sample(data)
    assert item["id"] == 6


@pytest.mark.parametrize("kwargs", [
    dict(title="   ", coupang_url="https://www.coupang.com/vp/products/1"),
    dict(title="가습기", coupang_url="http://www.coupang.com/vp/products/1"),
    dict(title="가습기", coupang_url="같은url아님"),
])
def test_new_item_rejects_invalid(kwargs):
    with pytest.raises(ValidationError):
        new_item(make_data(), now=NOW, **kwargs)


def test_new_item_rejects_duplicate_coupang_url():
    data = make_data()
    add_sample(data)
    with pytest.raises(ValidationError):
        add_sample(data, title="다른 제목")


def test_advance_moves_to_next_and_appends_history():
    data = make_data()
    add_sample(data)
    later = dt.datetime(2026, 7, 12, 16, 0, 0)
    item = advance_item(data, 1, now=later)
    assert item["stage"] == "video_ready"
    assert item["history"][-1] == {"stage": "video_ready", "at": "2026-07-12T16:00:00"}
    assert len(item["history"]) == 2


def test_advance_set_stores_values_including_equals():
    data = make_data()
    add_sample(data)
    sets = parse_sets(["aliUrl=https://ko.aliexpress.com/item/1.html?spm=a=b"])
    item = advance_item(data, 1, sets=sets, now=NOW)
    assert item["data"]["aliUrl"] == "https://ko.aliexpress.com/item/1.html?spm=a=b"


def test_advance_to_jumps_to_named_stage():
    data = make_data()
    add_sample(data)
    item = advance_item(data, 1, to="published", now=NOW)
    assert item["stage"] == "published"


def test_advance_rejects_unknown_slug():
    data = make_data()
    add_sample(data)
    with pytest.raises(ValidationError):
        advance_item(data, 1, to="does_not_exist", now=NOW)


def test_advance_rejects_unknown_id():
    with pytest.raises(ValidationError):
        advance_item(make_data(), 99, now=NOW)


def test_advance_stops_at_analyzed():
    data = make_data()
    add_sample(data)
    item = advance_item(data, 1, to="analyzed", now=NOW)
    assert item["stage"] == "analyzed"
    with pytest.raises(ValidationError):
        advance_item(data, 1, now=NOW)


def test_parse_sets_rejects_missing_equals():
    with pytest.raises(ValidationError):
        parse_sets(["키만있음"])


def test_save_load_roundtrip_keeps_korean(tmp_path):
    path = tmp_path / "pipeline.json"
    data = make_data()
    add_sample(data)
    save_data(path, data)
    raw = path.read_text(encoding="utf-8")
    assert "접이식 미니 가습기" in raw
    assert load_data(path) == data


def test_every_stage_has_next_action():
    for slug in SLUGS:
        action = next_action(slug)
        assert isinstance(action, str) and action


def test_render_dashboard_smoke():
    data = make_data()
    add_sample(data)
    advance_item(data, 1, sets={"aliUrl": "https://ko.aliexpress.com/item/1.html"}, now=NOW)
    html = render_dashboard(data, generated_at=NOW)
    assert "접이식 미니 가습기" in html
    assert "상품확정" in html and "영상준비" in html
    assert "https://ko.aliexpress.com/item/1.html" in html
