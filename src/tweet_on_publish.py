"""
tweet_on_publish.py — Issue コメントから note URL を抽出し、X に投稿する。

GitHub Actions の `issue_comment` イベントから呼び出される。
コメント本文に `note: https://note.com/...` 形式の行があれば
その URL を使ってツイートを投稿し、Issue をクローズする。

GitHub Actions 環境変数:
  - GITHUB_TOKEN         (自動付与)
  - GITHUB_REPOSITORY    (自動付与, "owner/repo")
  - GITHUB_EVENT_PATH    (event payload JSON のパス)
"""

from __future__ import annotations

import json
import logging
import os
import re
import sys

from github import Auth, Github

from .x_poster import post, post_thread, trim_to_limit

log = logging.getLogger(__name__)

NOTE_URL_RE = re.compile(r"note\s*:\s*(https?://note\.com/\S+)", re.IGNORECASE)
# 単発ツイート用
TWEET_BLOCK_RE = re.compile(
    r"### 🐦 ツイート文.*?\n```\n(.*?)\n```", re.DOTALL
)
# スレッド用(json 配列)
THREAD_BLOCK_RE = re.compile(
    r"### 🐦 ツイート文.*?\n```thread_json\n(.*?)\n```", re.DOTALL
)
NOTE_URL_PLACEHOLDER = "{NOTE_URL}"


def main() -> int:
    logging.basicConfig(level=logging.INFO)

    event_path = os.environ.get("GITHUB_EVENT_PATH")
    if not event_path:
        log.error("GITHUB_EVENT_PATH not set — must run inside GitHub Actions")
        return 1

    with open(event_path, encoding="utf-8") as f:
        event = json.load(f)

    comment_body = event.get("comment", {}).get("body", "")
    issue_number = event.get("issue", {}).get("number")
    if not comment_body or not issue_number:
        log.info("not an issue_comment with a body — skipping")
        return 0

    m = NOTE_URL_RE.search(comment_body)
    if not m:
        log.info("no `note: <url>` pattern in comment — skipping")
        return 0

    note_url = m.group(1).strip().rstrip(").,;")
    log.info("found note URL: %s", note_url)

    # Issue 本文からテンプレ済みのツイート文を取り出す
    gh = Github(auth=Auth.Token(os.environ["GITHUB_TOKEN"]))
    repo = gh.get_repo(os.environ["GITHUB_REPOSITORY"])
    issue = repo.get_issue(issue_number)

    # スレッド版(premium)か単発(free/entry)かを Issue 本文で判定
    thread_tweets = _extract_thread_template(issue.body or "")

    if thread_tweets:
        # スレッド投稿
        finalized = [_finalize_tweet(t, note_url) for t in thread_tweets]
        log.info("posting thread (%d tweets)", len(finalized))
        ids = post_thread(finalized)
        if not ids:
            issue.create_comment("⚠ X スレッドの自動投稿に失敗しました。手動で投稿してください。")
            return 2
        head_url = f"https://x.com/i/web/status/{ids[0]}"
        issue.create_comment(
            f"✅ X スレッドを投稿しました({len(ids)} 連投): {head_url}"
        )
    else:
        # 単発投稿
        tweet_text = _extract_tweet_template(issue.body or "")
        if not tweet_text:
            title = issue.title.removeprefix("[DRAFT] ").strip()
            tweet_text = f"{title}\n\n↓詳細はnoteで\n{NOTE_URL_PLACEHOLDER}"

        final_tweet = _finalize_tweet(tweet_text, note_url)
        log.info("tweet payload (%d chars):\n%s", len(final_tweet), final_tweet)
        tweet_id = post(final_tweet)
        if not tweet_id:
            issue.create_comment("⚠ X への自動投稿に失敗しました。手動で投稿してください。")
            return 2
        issue.create_comment(f"✅ X に投稿しました: https://x.com/i/web/status/{tweet_id}")

    issue.edit(state="closed")
    log.info("issue closed: #%d", issue_number)
    return 0


def _extract_tweet_template(issue_body: str) -> str | None:
    m = TWEET_BLOCK_RE.search(issue_body)
    return m.group(1).strip() if m else None


def _extract_thread_template(issue_body: str) -> list[str] | None:
    m = THREAD_BLOCK_RE.search(issue_body)
    if not m:
        return None
    try:
        data = json.loads(m.group(1).strip())
        if isinstance(data, list) and all(isinstance(t, str) for t in data):
            return data
    except json.JSONDecodeError as e:
        log.warning("failed to parse thread_json: %s", e)
    return None


def _finalize_tweet(template: str, note_url: str) -> str:
    """Issue 本文中のテンプレに含まれる `{NOTE_URL}` を実 URL に差し替える。

    engagement_optimizer.build_article_tweet が
    URL を含めて 280 文字以内に収まるよう既にトリム済み。
    フォールバック経路用に最終的な長さチェックだけ行う。
    """
    if NOTE_URL_PLACEHOLDER in template:
        final = template.replace(NOTE_URL_PLACEHOLDER, note_url)
    else:
        final = f"{template.rstrip()}\n{note_url}"

    # 万一 280 超えなら本文をトリム(URL/ハッシュタグは温存)
    if len(final) > 280:
        # URL より上を縮める
        head, _, tail = final.rpartition(note_url)
        head = head.rstrip()
        overshoot = len(final) - 280 + 1
        if overshoot < len(head):
            head = head[: -overshoot].rstrip() + "…"
        final = f"{head}\n{note_url}"
    return final


if __name__ == "__main__":
    sys.exit(main())
