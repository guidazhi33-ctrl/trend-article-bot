"""
news_translator.py — 海外金融ニュース RSS を取得 → 日本語化要約 → X 投稿。

データソース (すべて RSS、認証不要):
  - Reuters Business
  - Bloomberg Markets
  - CoinDesk
  - CNBC Top News
  - FT Markets (一部のみ)

重複投稿防止のため、過去24h以内に投稿した記事URLをローカル
state ファイル (`state/news_posted.json`) で管理する。
GitHub Actions ではこの state を branch にコミットして保持する。
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

import feedparser
import requests
from anthropic import Anthropic

from .x_poster import post
from .engagement_optimizer import build_news_tweet

log = logging.getLogger(__name__)

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"
STATE_DIR = Path(__file__).resolve().parent.parent / "state"
STATE_FILE = STATE_DIR / "news_posted.json"

MODEL = "claude-sonnet-4-6"

FEEDS = [
    ("Reuters Business",  "https://feeds.reuters.com/reuters/businessNews"),
    ("Bloomberg Markets", "https://feeds.bloomberg.com/markets/news.rss"),
    ("CoinDesk",          "https://www.coindesk.com/arc/outboundfeeds/rss/"),
    ("CNBC Markets",      "https://www.cnbc.com/id/15839069/device/rss/rss.html"),
]

POSTS_PER_RUN = 2     # 1 回の実行で投稿する本数 (4h毎×2本=12本/日 → だが Free tier 480 枠を考慮し 1本に絞る運用も可)
STALE_HOURS = 24      # state の保持期間


# ----------------------------------------------------------------------
# State 管理
# ----------------------------------------------------------------------

def _load_state() -> dict:
    if not STATE_FILE.exists():
        return {"posted": {}}
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {"posted": {}}


def _save_state(state: dict) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(
        json.dumps(state, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _prune_state(state: dict) -> None:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=STALE_HOURS)
    state["posted"] = {
        k: v for k, v in state.get("posted", {}).items()
        if datetime.fromisoformat(v).replace(tzinfo=timezone.utc) > cutoff
    }


def _entry_id(entry) -> str:
    base = entry.get("id") or entry.get("link") or entry.get("title", "")
    return hashlib.sha256(base.encode()).hexdigest()[:16]


# ----------------------------------------------------------------------
# 取得
# ----------------------------------------------------------------------

def _fetch_entries() -> list[dict]:
    """全フィードからエントリを集めて時系列でマージ。"""
    entries: list[dict] = []
    for source, url in FEEDS:
        try:
            parsed = feedparser.parse(url)
        except Exception as e:
            log.warning("feed %s failed: %s", source, e)
            continue

        for e in parsed.entries[:15]:
            entries.append({
                "source": source,
                "id": _entry_id(e),
                "title": e.get("title", ""),
                "summary": _strip_html(e.get("summary", "") or e.get("description", "")),
                "link": e.get("link", ""),
                "published": e.get("published", ""),
            })

    entries.sort(key=lambda x: x.get("published", ""), reverse=True)
    return entries


def _strip_html(text: str) -> str:
    import re
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _guess_category_from_title(title: str) -> str:
    t = title.lower()
    if any(w in t for w in ("bitcoin", "ethereum", "crypto", "btc", "eth",
                            "blockchain", "stablecoin")):
        return "crypto"
    if any(w in t for w in ("dollar", "yen", "euro", "forex", "fx",
                            "currency", "exchange rate")):
        return "fx"
    return "stock"


# ----------------------------------------------------------------------
# 翻訳
# ----------------------------------------------------------------------

def _claude() -> Anthropic:
    return Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])


def _translate(client: Anthropic, entry: dict) -> str:
    system = (PROMPTS_DIR / "news_translate.md").read_text(encoding="utf-8")
    user = f"""## 入力ニュース
- ソース: {entry['source']}
- 見出し: {entry['title']}
- 本文抜粋: {entry['summary'][:800]}
"""
    resp = client.messages.create(
        model=MODEL,
        max_tokens=600,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return "".join(b.text for b in resp.content if hasattr(b, "text")).strip()


# ----------------------------------------------------------------------
# メイン
# ----------------------------------------------------------------------

def run() -> int:
    state = _load_state()
    _prune_state(state)
    posted_ids = set(state["posted"].keys())

    entries = _fetch_entries()
    if not entries:
        log.error("no news entries fetched")
        return 0

    client = _claude()
    sent = 0
    for entry in entries:
        if sent >= POSTS_PER_RUN:
            break
        if entry["id"] in posted_ids:
            continue
        if not entry["title"]:
            continue

        try:
            jp = _translate(client, entry)
        except Exception as e:
            log.warning("translate failed: %s", e)
            continue

        category = _guess_category_from_title(entry["title"])
        tweet = build_news_tweet(jp, category, entry.get("link", ""))

        tid = post(tweet)
        if tid:
            state["posted"][entry["id"]] = datetime.now(timezone.utc).isoformat()
            sent += 1
            time.sleep(2)
        else:
            log.warning("post failed for entry %s", entry["id"])

    _save_state(state)
    log.info("news_translator: posted %d tweet(s)", sent)
    return sent


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run()
