"""Shows how each posted episode performed, so you can make more of what works.

    python insights.py

Reads the posted media IDs from state.json and asks Instagram for likes, comments
and (where the API allows) views, reach, shares and saves. Not tested against a
live account; metric names change between API versions, so missing numbers show
as "-".
"""
import json

import requests

import config

INSIGHT_METRICS = ["views", "reach", "shares", "saved"]


def _get(url: str, params: dict) -> dict:
    params = dict(params, access_token=config.IG_ACCESS_TOKEN)
    try:
        return requests.get(url, params=params, timeout=30).json()
    except Exception as exc:
        return {"error": str(exc)}


def fetch(media_id: str) -> dict:
    base = f"{config.IG_GRAPH_HOST.rstrip('/')}/{config.IG_API_VERSION}"
    row = {}
    basic = _get(f"{base}/{media_id}", {"fields": "like_count,comments_count,permalink"})
    row["likes"] = basic.get("like_count", "-")
    row["comments"] = basic.get("comments_count", "-")
    row["link"] = basic.get("permalink", "")
    for metric in INSIGHT_METRICS:
        data = _get(f"{base}/{media_id}/insights", {"metric": metric})
        try:
            row[metric] = data["data"][0]["values"][0]["value"]
        except (KeyError, IndexError, TypeError):
            row[metric] = "-"
    return row


def main() -> None:
    if not config.STATE_FILE.exists():
        print("Nothing posted yet.")
        return
    history = json.loads(config.STATE_FILE.read_text(encoding="utf-8")).get("history", [])
    posted = [h for h in history if h.get("media_id")]
    if not posted:
        print("Nothing posted yet.")
        return

    rows = []
    for h in posted:
        rows.append({**h, **fetch(h["media_id"])})

    def views(r):
        return r["views"] if isinstance(r["views"], int) else -1

    rows.sort(key=views, reverse=True)
    print(f"{'Ep':>3}  {'Format':<6} {'Item':<20} {'Views':>8} {'Reach':>8} "
          f"{'Shares':>6} {'Saves':>6} {'Likes':>6} {'Cmts':>5}")
    for r in rows:
        print(f"{r['episode'] + 1:>3}  {r.get('format', '?'):<6} {r.get('item_short', '')[:20]:<20} "
              f"{r['views']!s:>8} {r['reach']!s:>8} {r['shares']!s:>6} {r['saved']!s:>6} "
              f"{r['likes']!s:>6} {r['comments']!s:>5}")

    by_format = {}
    for r in rows:
        if isinstance(r["views"], int):
            by_format.setdefault(r.get("format", "?"), []).append(r["views"])
    if by_format:
        print("\nAverage views by format:")
        for fmt, values in by_format.items():
            print(f"  {fmt}: {sum(values) // len(values)} ({len(values)} reels)")
        print("Make more of the format and items at the top of the table.")


if __name__ == "__main__":
    main()
