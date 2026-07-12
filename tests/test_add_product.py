import datetime as dt
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from add_product import ValidationError, add_product, load_data, save_data


def make_data(products=None):
    return {"profile": {"name": "오늘의신기템"}, "products": products if products is not None else []}


def test_first_product_gets_id_1():
    data = make_data()
    p = add_product(data, title="가습기", price=12900,
                    image="https://img.example/1.jpg",
                    link="https://link.coupang.com/a/aaa")
    assert p["id"] == 1
    assert data["products"][-1] is p


def test_next_id_is_max_plus_one_with_gaps():
    data = make_data([{"id": 3, "link": "https://link.coupang.com/a/x"}])
    p = add_product(data, title="후크", price=5900,
                    image="https://img.example/2.jpg",
                    link="https://link.coupang.com/a/bbb")
    assert p["id"] == 4


def test_fills_added_at_active_and_strips_title():
    data = make_data()
    p = add_product(data, title="  가습기  ", price=12900,
                    image="https://img.example/1.jpg",
                    link="https://link.coupang.com/a/aaa",
                    today=dt.date(2026, 7, 12))
    assert p["addedAt"] == "2026-07-12"
    assert p["active"] is True
    assert p["title"] == "가습기"


@pytest.mark.parametrize("kwargs", [
    dict(title="   ", price=12900, image="https://i/1.jpg", link="https://l/a"),
    dict(title="가습기", price=0, image="https://i/1.jpg", link="https://l/a"),
    dict(title="가습기", price=-100, image="https://i/1.jpg", link="https://l/a"),
    dict(title="가습기", price=12900, image="http://i/1.jpg", link="https://l/a"),
    dict(title="가습기", price=12900, image="https://i/1.jpg", link="http://l/a"),
])
def test_rejects_invalid_input(kwargs):
    with pytest.raises(ValidationError):
        add_product(make_data(), **kwargs)


def test_accepts_local_images_path():
    data = make_data()
    p = add_product(data, title="가습기", price=12900,
                    image="images/001.jpg",
                    link="https://link.coupang.com/a/aaa")
    assert p["image"] == "images/001.jpg"


def test_rejects_local_path_outside_images():
    with pytest.raises(ValidationError):
        add_product(make_data(), title="가습기", price=12900,
                    image="C:/somewhere/1.jpg",
                    link="https://link.coupang.com/a/aaa")


def test_rejects_duplicate_link():
    data = make_data([{"id": 1, "link": "https://link.coupang.com/a/dup"}])
    with pytest.raises(ValidationError):
        add_product(data, title="중복", price=1000,
                    image="https://i/1.jpg",
                    link="https://link.coupang.com/a/dup")


def test_save_load_roundtrip_keeps_korean(tmp_path):
    path = tmp_path / "products.json"
    data = make_data()
    add_product(data, title="접이식 미니 가습기", price=12900,
                image="https://i/1.jpg", link="https://l/a")
    save_data(path, data)
    raw = path.read_text(encoding="utf-8")
    assert "접이식 미니 가습기" in raw
    assert load_data(path) == data
