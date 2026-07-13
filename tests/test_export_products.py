from scripts.export_products import build_products_document


PROFILE = {"name": "오늘의신기템", "bio": "신기한 물건", "avatar": "", "links": []}


def test_export_keeps_schema_and_only_includes_public_ready_products():
    rows = [
        {
            "id": 4, "title": "회전 선반", "price": 28500,
            "image_url": "https://image.coupangcdn.com/4.jpg",
            "partners_link": "https://link.coupang.com/a/4",
            "stage": "published", "active": True,
            "created_at": "2026-07-13T01:02:03+00:00",
        },
        {
            "id": 5, "title": "승인 전 상품", "price": 10000,
            "image_url": "https://image.coupangcdn.com/5.jpg",
            "partners_link": None, "stage": "caption_ready", "active": True,
            "created_at": "2026-07-13T01:02:03+00:00",
        },
        {
            "id": 6, "title": "비활성 상품", "price": 10000,
            "image_url": "https://image.coupangcdn.com/6.jpg",
            "partners_link": "https://link.coupang.com/a/6",
            "stage": "linked", "active": False,
            "created_at": "2026-07-13T01:02:03+00:00",
        },
    ]

    assert build_products_document(rows, PROFILE) == {
        "profile": PROFILE,
        "products": [{
            "id": 4,
            "title": "회전 선반",
            "price": 28500,
            "image": "https://image.coupangcdn.com/4.jpg",
            "link": "https://link.coupang.com/a/4",
            "addedAt": "2026-07-13",
            "active": True,
        }],
    }
