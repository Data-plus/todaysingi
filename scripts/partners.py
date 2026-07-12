#!/usr/bin/env python3
"""쿠팡 파트너스 Open API로 일반 쿠팡 URL을 파트너스 링크로 변환한다.

사용 예:
    python scripts/partners.py "https://www.coupang.com/vp/products/9433006170"

전제: .env에 PARTNERS_ACCESS_KEY, PARTNERS_SECRET_KEY
(파트너스 워크스페이스 → 추가기능 → Open API에서 발급)
"""
import datetime as dt
import hashlib
import hmac
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from tts import load_env

HOST = "https://api-gateway.coupang.com"
DEEPLINK_PATH = "/v2/providers/affiliate_open_api/apis/openapi/v1/deeplink"


def split_uri(uri):
    if "?" in uri:
        path, query = uri.split("?", 1)
        return path, query
    return uri, ""


def build_auth_header(method, uri, *, access_key, secret_key, now=None):
    """쿠팡 CEA(HmacSHA256) 인증 헤더 생성."""
    now = now or dt.datetime.utcnow()
    signed_date = now.strftime("%y%m%dT%H%M%SZ")
    path, query = split_uri(uri)
    message = signed_date + method + path + query
    signature = hmac.new(secret_key.encode(), message.encode(),
                         hashlib.sha256).hexdigest()
    return (f"CEA algorithm=HmacSHA256, access-key={access_key}, "
            f"signed-date={signed_date}, signature={signature}")


def create_deeplink(coupang_url, *, access_key, secret_key, sub_id=None):
    import requests
    body = {"coupangUrls": [coupang_url]}
    if sub_id:
        body["subId"] = sub_id
    headers = {
        "Authorization": build_auth_header("POST", DEEPLINK_PATH,
                                           access_key=access_key,
                                           secret_key=secret_key),
        "Content-Type": "application/json",
    }
    r = requests.post(HOST + DEEPLINK_PATH, headers=headers,
                      data=json.dumps(body), timeout=30)
    data = r.json()
    if r.status_code != 200 or data.get("rCode") not in ("0", 0):
        raise RuntimeError(f"딥링크 변환 실패: {data}")
    return data["data"][0]["shortenUrl"]


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    import argparse
    parser = argparse.ArgumentParser(description="쿠팡 URL → 파트너스 링크")
    parser.add_argument("url")
    parser.add_argument("--sub-id", default=None, help="채널 구분용 subId (선택)")
    args = parser.parse_args(argv)

    env = load_env()
    access_key = env.get("PARTNERS_ACCESS_KEY", "")
    secret_key = env.get("PARTNERS_SECRET_KEY", "")
    if not access_key or not secret_key:
        print(".env에 PARTNERS_ACCESS_KEY / PARTNERS_SECRET_KEY가 필요합니다.\n"
              "발급: partners.coupang.com → 추가기능 → Open API", file=sys.stderr)
        return 1

    short = create_deeplink(args.url, access_key=access_key,
                            secret_key=secret_key, sub_id=args.sub_id)
    print(short)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
