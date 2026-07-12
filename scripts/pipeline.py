#!/usr/bin/env python3
"""오늘의신기템 파이프라인 관제탑 CLI.

상품(아이템)별로 15단계 파이프라인의 진행 상태·산출물·이력을
ops/pipeline.json 장부에 기록하고, 정적 대시보드를 생성한다.

사용 예:
    python scripts/pipeline.py new --title "접이식 미니 가습기" \
        --coupang-url "https://www.coupang.com/vp/products/123"
    python scripts/pipeline.py advance 1 --set aliUrl=https://ko.aliexpress.com/item/1.html
    python scripts/pipeline.py advance 1 --to published --set reelUrl=https://...
    python scripts/pipeline.py status
    python scripts/pipeline.py dashboard [--no-open]
"""
import argparse
import datetime as dt
import html
import json
import sys
import webbrowser
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_FILE = REPO_ROOT / "ops" / "pipeline.json"
DASHBOARD_FILE = REPO_ROOT / "ops" / "dashboard.html"

# (slug, 한글 이름, 이 단계를 마친 뒤 할 일)
STAGES = [
    ("sourced", "상품확정", "알리 영상 내려받고 무음화"),
    ("video_ready", "영상준비", "재미있는 대본 작성"),
    ("script_ready", "대본완성", "TTS 생성 후 영상에 합성"),
    ("audio_ready", "더빙합성", "인스타 캡션·해시태그 작성"),
    ("caption_ready", "캡션완성", "릴스 업로드"),
    ("published", "릴스게시", "파트너스 링크 전환 + 사이트 게시(add_product)"),
    ("linked", "링크연결", "광고 2종 세팅·집행"),
    ("ads_running", "광고집행", "성과 비교 분석·기록"),
    ("analyzed", "분석완료", "완료"),
]
SLUGS = [slug for slug, _, _ in STAGES]
LABELS = {slug: label for slug, label, _ in STAGES}
ACTIONS = {slug: action for slug, _, action in STAGES}


class ValidationError(ValueError):
    pass


def load_data(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_data(path, data):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def next_action(slug):
    return ACTIONS[slug]


def _timestamp(now):
    return (now or dt.datetime.now()).isoformat(timespec="seconds")


def new_item(data, *, title, coupang_url, note="", now=None):
    items = data["items"]
    if not title or not title.strip():
        raise ValidationError("title이 비어 있습니다")
    if not isinstance(coupang_url, str) or not coupang_url.startswith("https://"):
        raise ValidationError("coupang-url은 https:// 로 시작해야 합니다")
    if any(i["coupangUrl"] == coupang_url for i in items):
        raise ValidationError("이미 같은 coupangUrl의 아이템이 있습니다")
    item = {
        "id": max((i["id"] for i in items), default=0) + 1,
        "title": title.strip(),
        "coupangUrl": coupang_url,
        "stage": SLUGS[0],
        "history": [{"stage": SLUGS[0], "at": _timestamp(now)}],
        "data": {},
        "note": note,
    }
    items.append(item)
    return item


def advance_item(data, item_id, *, to=None, sets=None, now=None):
    item = next((i for i in data["items"] if i["id"] == item_id), None)
    if item is None:
        raise ValidationError(f"id {item_id} 아이템이 없습니다")
    if to is not None:
        if to not in SLUGS:
            raise ValidationError("없는 단계입니다. 유효: " + ", ".join(SLUGS))
        target = to
    else:
        idx = SLUGS.index(item["stage"])
        if idx == len(SLUGS) - 1:
            raise ValidationError("이미 분석완료 단계입니다 (--to로만 이동 가능)")
        target = SLUGS[idx + 1]
    item["stage"] = target
    item["history"].append({"stage": target, "at": _timestamp(now)})
    if sets:
        item["data"].update(sets)
    return item


def parse_sets(pairs):
    out = {}
    for pair in pairs or []:
        key, sep, value = pair.partition("=")
        if not sep or not key:
            raise ValidationError(f"--set 형식 오류(키=값): {pair}")
        out[key] = value
    return out


def _last_updated(item):
    return item["history"][-1]["at"]


def format_status(data):
    items = data["items"]
    if not items:
        return "아이템이 없습니다. new로 시작하세요."
    lines = []
    active = [i for i in items if i["stage"] != SLUGS[-1]]
    done = [i for i in items if i["stage"] == SLUGS[-1]]
    for item in active:
        lines.append(
            f"[{item['id']}] {item['title']} | {LABELS[item['stage']]}"
            f" | {_last_updated(item)[:10]} | 다음: {next_action(item['stage'])}"
        )
    if done:
        lines.append("--- 완료 ---")
        for item in done:
            lines.append(f"[{item['id']}] {item['title']} | {_last_updated(item)[:10]}")
    return "\n".join(lines)


def _card_html(item, today):
    updated = _last_updated(item)
    stale_days = (today - dt.date.fromisoformat(updated[:10])).days
    stale = f'<span class="stale">{stale_days}일 정체</span>' if stale_days >= 3 else ""
    links = "".join(
        f'<a href="{html.escape(v)}" target="_blank" rel="noopener">{html.escape(k)}</a>'
        for k, v in item["data"].items()
        if isinstance(v, str) and v.startswith("https://")
    )
    note = f'<p class="note">{html.escape(item["note"])}</p>' if item["note"] else ""
    return (
        f'<div class="item"><h3>[{item["id"]}] {html.escape(item["title"])}</h3>'
        f'<p class="meta">{updated[:10]} {stale}</p>{note}'
        f'<p class="links">{links}</p></div>'
    )


def render_dashboard(data, generated_at=None):
    generated_at = generated_at or dt.datetime.now()
    today = generated_at.date()
    columns = []
    for slug, label, _ in STAGES:
        items = [i for i in data["items"] if i["stage"] == slug]
        cards = "".join(_card_html(i, today) for i in items) or '<p class="empty">-</p>'
        columns.append(
            f'<section class="col"><h2>{label} <span class="count">{len(items)}</span></h2>'
            f"{cards}</section>"
        )
    board = "".join(columns)
    if not data["items"]:
        board = '<p class="empty-board">아이템이 없습니다. pipeline.py new로 시작하세요.</p>' + board
    stamp = generated_at.isoformat(timespec="minutes")
    return f"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>오늘의신기템 관제탑</title>
<style>
  body {{ margin: 0; background: #fff; color: #191919; line-height: 1.5;
    font-family: "Pretendard Variable", Pretendard, "Apple SD Gothic Neo",
      "Malgun Gothic", system-ui, sans-serif; }}
  header {{ padding: 20px 24px 8px; }}
  header h1 {{ font-size: 18px; margin: 0; }}
  header p {{ color: #888780; font-size: 12px; margin: 4px 0 0; }}
  .board {{ display: flex; gap: 12px; align-items: flex-start;
    overflow-x: auto; padding: 16px 24px 32px; }}
  .col {{ min-width: 190px; flex: 0 0 190px; background: #f5f4f0;
    border-radius: 12px; padding: 10px 10px 12px; }}
  .col h2 {{ font-size: 13px; margin: 0 0 8px; padding: 0 2px; }}
  .count {{ color: #888780; font-weight: 400; }}
  .item {{ background: #fff; border: 1px solid #e5e4de; border-radius: 10px;
    padding: 8px 10px; margin-bottom: 8px; }}
  .item h3 {{ font-size: 12px; margin: 0 0 2px; }}
  .meta {{ font-size: 11px; color: #888780; margin: 0; }}
  .stale {{ color: #c0392b; }}
  .note {{ font-size: 11px; color: #555; margin: 4px 0 0; }}
  .links {{ margin: 4px 0 0; }}
  .links a {{ display: inline-block; font-size: 11px; color: #191919;
    background: #f1efe8; border-radius: 6px; padding: 1px 6px;
    margin: 2px 4px 0 0; text-decoration: none; }}
  .empty {{ color: #b4b2a9; text-align: center; font-size: 12px; margin: 4px 0; }}
  .empty-board {{ color: #888780; padding: 0 24px; }}
</style>
</head>
<body>
<header>
  <h1>오늘의신기템 관제탑</h1>
  <p>생성 {stamp} · 진실 소스: ops/pipeline.json</p>
</header>
<div class="board">{board}</div>
</body>
</html>
"""


def _load_or_exit(path):
    if not Path(path).exists():
        print("장부가 없습니다. new로 시작하세요.", file=sys.stderr)
        raise SystemExit(1)
    return load_data(path)


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="파이프라인 관제탑")
    parser.add_argument("--file", default=str(DEFAULT_FILE))
    sub = parser.add_subparsers(dest="command", required=True)

    p_new = sub.add_parser("new", help="아이템 등록")
    p_new.add_argument("--title", required=True)
    p_new.add_argument("--coupang-url", required=True)
    p_new.add_argument("--note", default="")

    p_adv = sub.add_parser("advance", help="단계 진행")
    p_adv.add_argument("id", type=int)
    p_adv.add_argument("--to", choices=SLUGS)
    p_adv.add_argument("--set", dest="sets", action="append", default=[],
                       metavar="키=값")

    sub.add_parser("status", help="현황 표")

    p_dash = sub.add_parser("dashboard", help="대시보드 생성")
    p_dash.add_argument("--no-open", action="store_true")

    args = parser.parse_args(argv)
    path = Path(args.file)

    try:
        if args.command == "new":
            data = load_data(path) if path.exists() else {"items": []}
            item = new_item(data, title=args.title, coupang_url=args.coupang_url,
                            note=args.note)
            save_data(path, data)
            print(f"등록됨: [{item['id']}] {item['title']} ({LABELS[item['stage']]})")
        elif args.command == "advance":
            data = _load_or_exit(path)
            sets = parse_sets(args.sets)
            item = advance_item(data, args.id, to=args.to, sets=sets)
            save_data(path, data)
            print(f"[{item['id']}] {item['title']} → {LABELS[item['stage']]}"
                  f" | 다음: {next_action(item['stage'])}")
        elif args.command == "status":
            data = _load_or_exit(path)
            print(format_status(data))
        elif args.command == "dashboard":
            data = _load_or_exit(path)
            DASHBOARD_FILE.parent.mkdir(parents=True, exist_ok=True)
            DASHBOARD_FILE.write_text(render_dashboard(data), encoding="utf-8")
            print(f"생성됨: {DASHBOARD_FILE}")
            if not args.no_open:
                webbrowser.open(DASHBOARD_FILE.as_uri())
    except ValidationError as e:
        print(f"거부됨: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
