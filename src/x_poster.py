"""
x_poster.py — X (Twitter) API v2 で投稿する薄いラッパー。

Free tier (月500投稿) 想定。tweepy を使う。
画像添付は v1.1 API media/upload が必要だが Free tier では使えないため、
本システムではテキスト+URL のみで運用する(note の og:image が
Twitter Card として展開されるので結果的にサムネは表示される)。
"""

from __future__ import annotations

import logging
import os

import tweepy

log = logging.getLogger(__name__)

MAX_TWEET_LEN = 280


def _client() -> tweepy.Client:
    return tweepy.Client(
        bearer_token=os.environ.get("X_BEARER_TOKEN"),
        consumer_key=os.environ["X_API_KEY"],
        consumer_secret=os.environ["X_API_SECRET"],
        access_token=os.environ["X_ACCESS_TOKEN"],
        access_token_secret=os.environ["X_ACCESS_TOKEN_SECRET"],
    )


def post(text: str, in_reply_to: str | None = None) -> str | None:
    """1 件のツイートを投稿。スレッド継続は in_reply_to を指定。"""
    if len(text) > MAX_TWEET_LEN:
        log.warning("text too long (%d), truncating", len(text))
        text = text[: MAX_TWEET_LEN - 1] + "…"

    try:
        client = _client()
        kwargs = {"text": text}
        if in_reply_to:
            kwargs["in_reply_to_tweet_id"] = in_reply_to
        resp = client.create_tweet(**kwargs)
        tweet_id = resp.data["id"]
        log.info("tweeted: %s (reply_to=%s)", tweet_id, in_reply_to)
        return tweet_id
    except Exception as e:
        log.error("tweet failed: %s", e)
        return None


def post_thread(tweets: list[str], delay_seconds: float = 2.0) -> list[str]:
    """連続ツイートをスレッドとして投稿。返り値は tweet ID のリスト。

    Free tier 月 500 投稿の天井を意識して 3〜5 件程度の "薄いスレッド" を推奨。
    """
    import time
    ids: list[str] = []
    prev: str | None = None
    for i, text in enumerate(tweets):
        tid = post(text, in_reply_to=prev)
        if not tid:
            log.warning("thread broken at tweet %d/%d", i + 1, len(tweets))
            break
        ids.append(tid)
        prev = tid
        if i < len(tweets) - 1:
            time.sleep(delay_seconds)  # レート制限回避
    return ids


def trim_to_limit(text: str, reserved_for_url: int = 24) -> str:
    """t.co URL は一律 23 文字に短縮されるので URL 込みで 280 に収まるよう調整。"""
    limit = MAX_TWEET_LEN - reserved_for_url - 1
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"
