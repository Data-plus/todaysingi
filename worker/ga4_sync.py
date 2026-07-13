"""GA4 Data API 보고서를 오늘의신기템 일별 성과 행으로 변환한다."""
from __future__ import annotations

import datetime as dt
import os
from collections.abc import Callable, Mapping
from typing import Any


ANALYTICS_SCOPE = "https://www.googleapis.com/auth/analytics.readonly"
DATA_API_ROOT = "https://analyticsdata.googleapis.com/v1beta"
LINK_HUB_LIST_ID = "todaysingi_link_hub"


class Ga4SyncError(RuntimeError):
    pass


def _property_id(value: str) -> str:
    clean = str(value or "").strip()
    if not clean.isdigit():
        raise Ga4SyncError("GA4_PROPERTY_ID는 숫자 Property ID여야 합니다")
    return clean


def _iso(value: dt.date) -> str:
    if not isinstance(value, dt.date):
        raise Ga4SyncError("GA4 조회 날짜가 올바르지 않습니다")
    return value.isoformat()


def build_product_report(
    property_id: str, start_date: dt.date, end_date: dt.date,
) -> dict[str, Any]:
    _property_id(property_id)
    return {
        "dateRanges": [{"startDate": _iso(start_date), "endDate": _iso(end_date)}],
        "dimensions": [{"name": "date"}, {"name": "itemId"}, {"name": "itemName"}],
        "metrics": [{"name": "itemsClickedInList"}],
        "dimensionFilter": {
            "filter": {
                "fieldName": "itemListId",
                "stringFilter": {"matchType": "EXACT", "value": LINK_HUB_LIST_ID},
            }
        },
        "limit": "10000",
        "keepEmptyRows": False,
    }


def build_traffic_report(
    property_id: str, start_date: dt.date, end_date: dt.date,
) -> dict[str, Any]:
    _property_id(property_id)
    return {
        "dateRanges": [{"startDate": _iso(start_date), "endDate": _iso(end_date)}],
        "dimensions": [
            {"name": "date"}, {"name": "sessionSource"}, {"name": "sessionMedium"},
        ],
        "metrics": [{"name": "sessions"}, {"name": "activeUsers"}],
        "limit": "10000",
        "keepEmptyRows": False,
    }


def _value(values: Any, index: int) -> str:
    try:
        value = values[index].get("value", "")
    except (AttributeError, IndexError, TypeError) as exc:
        raise Ga4SyncError("GA4 응답 행 형식이 올바르지 않습니다") from exc
    return str(value).strip()


def _metric(values: Any, index: int) -> int:
    raw = _value(values, index)
    try:
        number = int(raw or "0")
    except ValueError as exc:
        raise Ga4SyncError(f"GA4 지표가 정수가 아닙니다: {raw}") from exc
    if number < 0:
        raise Ga4SyncError("GA4 지표가 음수입니다")
    return number


def _metric_date(raw: str) -> str:
    try:
        return dt.datetime.strptime(raw, "%Y%m%d").date().isoformat()
    except ValueError as exc:
        raise Ga4SyncError(f"GA4 날짜 형식이 올바르지 않습니다: {raw}") from exc


def parse_product_rows(
    response: Mapping[str, Any], known_product_ids: set[int],
) -> list[dict[str, Any]]:
    aggregated: dict[tuple[str, str], dict[str, Any]] = {}
    for raw_row in response.get("rows", []) or []:
        dimensions = raw_row.get("dimensionValues", [])
        metrics = raw_row.get("metricValues", [])
        metric_date = _metric_date(_value(dimensions, 0))
        item_id = _value(dimensions, 1)
        if not item_id or item_id == "(not set)":
            continue
        if len(item_id) > 128:
            raise Ga4SyncError("GA4 item_id가 너무 깁니다")
        item_name = _value(dimensions, 2)
        clicks = _metric(metrics, 0)
        numeric_id = int(item_id) if item_id.isdigit() else None
        product_id = numeric_id if numeric_id in known_product_ids else None
        key = (metric_date, item_id)
        if key not in aggregated:
            aggregated[key] = {
                "metric_date": metric_date,
                "item_id": item_id,
                "product_id": product_id,
                "item_name": item_name,
                "clicks": 0,
            }
        aggregated[key]["clicks"] += clicks
        if item_name:
            aggregated[key]["item_name"] = item_name
    return [aggregated[key] for key in sorted(aggregated)]


def parse_traffic_rows(response: Mapping[str, Any]) -> list[dict[str, Any]]:
    aggregated: dict[tuple[str, str, str], dict[str, Any]] = {}
    for raw_row in response.get("rows", []) or []:
        dimensions = raw_row.get("dimensionValues", [])
        metrics = raw_row.get("metricValues", [])
        metric_date = _metric_date(_value(dimensions, 0))
        source = _value(dimensions, 1) or "(not set)"
        medium = _value(dimensions, 2) or "(not set)"
        if len(source) > 256 or len(medium) > 128:
            raise Ga4SyncError("GA4 유입 경로 값이 너무 깁니다")
        key = (metric_date, source, medium)
        if key not in aggregated:
            aggregated[key] = {
                "metric_date": metric_date,
                "source": source,
                "medium": medium,
                "sessions": 0,
                "active_users": 0,
            }
        aggregated[key]["sessions"] += _metric(metrics, 0)
        aggregated[key]["active_users"] += _metric(metrics, 1)
    return [aggregated[key] for key in sorted(aggregated)]


def resolve_date_range(
    payload: Mapping[str, Any], *, today: dt.date | None = None,
) -> tuple[dt.date, dt.date]:
    today = today or dt.datetime.now(dt.timezone.utc).date()
    if payload.get("range_start") is not None or payload.get("range_end") is not None:
        try:
            start = dt.date.fromisoformat(str(payload["range_start"]))
            end = dt.date.fromisoformat(str(payload["range_end"]))
        except (KeyError, TypeError, ValueError) as exc:
            raise Ga4SyncError("GA4 조회 기간 형식이 올바르지 않습니다") from exc
    else:
        days = payload.get("days", 30)
        if not isinstance(days, int) or isinstance(days, bool) or not 1 <= days <= 90:
            raise Ga4SyncError("GA4 조회 기간은 일 일부터 구십 일까지 가능합니다")
        end = today
        start = end - dt.timedelta(days=days - 1)
    if start > end or (end - start).days > 89:
        raise Ga4SyncError("GA4 조회 기간은 최대 구십 일입니다")
    return start, end


def adc_access_token() -> str:
    try:
        import google.auth
        from google.auth.transport.requests import Request
    except ImportError as exc:
        raise Ga4SyncError("google-auth 패키지가 설치되지 않았습니다") from exc
    credentials, _project = google.auth.default(scopes=[ANALYTICS_SCOPE])
    if not credentials.valid:
        credentials.refresh(Request())
    if not credentials.token:
        raise Ga4SyncError("Google ADC 액세스 토큰을 발급하지 못했습니다")
    return str(credentials.token)


def run_report(
    property_id: str,
    report: Mapping[str, Any],
    access_token: str,
    *,
    session=None,
) -> dict[str, Any]:
    if session is None:
        import requests
        session = requests.Session()
    url = f"{DATA_API_ROOT}/properties/{_property_id(property_id)}:runReport"
    response = session.post(
        url,
        headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"},
        json=dict(report),
        timeout=60,
    )
    if response.status_code >= 400:
        message = str(getattr(response, "text", ""))[:1000]
        raise Ga4SyncError(f"GA4 Data API {response.status_code}: {message}")
    try:
        return response.json()
    except ValueError as exc:
        raise Ga4SyncError("GA4 Data API가 JSON이 아닌 응답을 반환했습니다") from exc


def sync_ga4(
    client,
    payload: Mapping[str, Any],
    *,
    property_id: str | None = None,
    session=None,
    token_provider: Callable[[], str] = adc_access_token,
    today: dt.date | None = None,
) -> dict[str, Any]:
    start, end = resolve_date_range(payload, today=today)
    property_id = _property_id(property_id or os.environ.get("GA4_PROPERTY_ID", ""))
    client.mark_integration_sync(
        "ga4", status="running", range_start=start.isoformat(), range_end=end.isoformat(),
        error_summary=None,
    )
    try:
        token = token_provider()
        product_response = run_report(
            property_id, build_product_report(property_id, start, end), token, session=session,
        )
        traffic_response = run_report(
            property_id, build_traffic_report(property_id, start, end), token, session=session,
        )
        known_product_ids = set(client.list_product_ids())
        product_rows = parse_product_rows(product_response, known_product_ids)
        traffic_rows = parse_traffic_rows(traffic_response)
        affected = client.replace_ga4_metrics(start, end, product_rows, traffic_rows)
        return {
            "range_start": start.isoformat(),
            "range_end": end.isoformat(),
            "product_rows": len(product_rows),
            "traffic_rows": len(traffic_rows),
            "stored_rows": affected,
        }
    except Exception as exc:
        client.mark_integration_sync(
            "ga4", status="failed", range_start=start.isoformat(), range_end=end.isoformat(),
            error_summary=str(exc)[:1000],
        )
        raise
