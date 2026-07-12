import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from partners import build_auth_header, split_uri

NOW = dt.datetime(2026, 7, 12, 3, 30, 0)


def test_split_uri():
    path, query = split_uri("/v2/providers/x/deeplink")
    assert path == "/v2/providers/x/deeplink" and query == ""
    path, query = split_uri("/v2/x?a=1&b=2")
    assert path == "/v2/x" and query == "a=1&b=2"


def test_build_auth_header_format():
    h = build_auth_header("POST", "/v2/providers/affiliate_open_api/apis/openapi/v1/deeplink",
                          access_key="AK", secret_key="SK", now=NOW)
    assert h.startswith("CEA algorithm=HmacSHA256, access-key=AK, signed-date=260712T033000Z, signature=")
    sig = h.split("signature=")[1]
    assert len(sig) == 64 and all(c in "0123456789abcdef" for c in sig)


def test_build_auth_header_deterministic():
    a = build_auth_header("POST", "/v2/x", access_key="AK", secret_key="SK", now=NOW)
    b = build_auth_header("POST", "/v2/x", access_key="AK", secret_key="SK", now=NOW)
    assert a == b


def test_build_auth_header_signature_changes_with_input():
    base = build_auth_header("POST", "/v2/x", access_key="AK", secret_key="SK", now=NOW)
    other_path = build_auth_header("POST", "/v2/y", access_key="AK", secret_key="SK", now=NOW)
    other_secret = build_auth_header("POST", "/v2/x", access_key="AK", secret_key="XX", now=NOW)
    assert base != other_path and base != other_secret
