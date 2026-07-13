import datetime as dt

import pytest

from worker.ga4_sync import (
    Ga4SyncError,
    build_product_report,
    build_traffic_report,
    parse_product_rows,
    parse_traffic_rows,
    resolve_date_range,
)


def test_product_report_uses_item_click_metric_and_link_hub_filter():
    report = build_product_report("123456", dt.date(2026, 6, 14), dt.date(2026, 7, 13))

    assert report["dateRanges"] == [{"startDate": "2026-06-14", "endDate": "2026-07-13"}]
    assert [item["name"] for item in report["dimensions"]] == ["date", "itemId", "itemName"]
    assert report["metrics"] == [{"name": "itemsClickedInList"}]
    assert report["dimensionFilter"]["filter"]["fieldName"] == "itemListId"
    assert report["dimensionFilter"]["filter"]["stringFilter"]["value"] == "todaysingi_link_hub"


def test_traffic_report_collects_daily_source_medium_sessions_and_users():
    report = build_traffic_report("123456", dt.date(2026, 7, 1), dt.date(2026, 7, 13))

    assert [item["name"] for item in report["dimensions"]] == ["date", "sessionSource", "sessionMedium"]
    assert [item["name"] for item in report["metrics"]] == ["sessions", "activeUsers"]


def test_product_rows_are_normalized_matched_and_aggregated():
    response = {
        "rows": [
            {"dimensionValues": [{"value": "20260712"}, {"value": "004"}, {"value": "회전 선반"}], "metricValues": [{"value": "3"}]},
            {"dimensionValues": [{"value": "20260712"}, {"value": "004"}, {"value": "회전 선반 새 이름"}], "metricValues": [{"value": "2"}]},
            {"dimensionValues": [{"value": "20260713"}, {"value": "999"}, {"value": "미등록 상품"}], "metricValues": [{"value": "1"}]},
            {"dimensionValues": [{"value": "20260713"}, {"value": "(not set)"}, {"value": ""}], "metricValues": [{"value": "9"}]},
        ]
    }

    rows = parse_product_rows(response, {4})

    assert rows == [
        {"metric_date": "2026-07-12", "item_id": "004", "product_id": 4, "item_name": "회전 선반 새 이름", "clicks": 5},
        {"metric_date": "2026-07-13", "item_id": "999", "product_id": None, "item_name": "미등록 상품", "clicks": 1},
    ]


def test_traffic_rows_are_normalized_and_aggregated():
    response = {
        "rows": [
            {"dimensionValues": [{"value": "20260713"}, {"value": "instagram.com"}, {"value": "referral"}], "metricValues": [{"value": "7"}, {"value": "6"}]},
            {"dimensionValues": [{"value": "20260713"}, {"value": "instagram.com"}, {"value": "referral"}], "metricValues": [{"value": "2"}, {"value": "2"}]},
        ]
    }

    assert parse_traffic_rows(response) == [{
        "metric_date": "2026-07-13",
        "source": "instagram.com",
        "medium": "referral",
        "sessions": 9,
        "active_users": 8,
    }]


def test_date_range_defaults_to_recent_thirty_days_and_rejects_large_ranges():
    assert resolve_date_range({}, today=dt.date(2026, 7, 13)) == (
        dt.date(2026, 6, 14), dt.date(2026, 7, 13)
    )
    assert resolve_date_range({"days": 7}, today=dt.date(2026, 7, 13)) == (
        dt.date(2026, 7, 7), dt.date(2026, 7, 13)
    )
    with pytest.raises(Ga4SyncError):
        resolve_date_range({"days": 91}, today=dt.date(2026, 7, 13))
