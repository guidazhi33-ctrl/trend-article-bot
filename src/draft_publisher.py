"""
draft_publisher.py — 生成した記事を GitHub Issue として「ドラフト」発行する。

運用フロー:
  1. cron で記事+サムネが生成される
  2. このモジュールが Issue を立て、本文 (Markdown 全文) と
     サムネ画像をブランチに commit し、Issue 本文中で参照する
  3. 人間が Issue を見て、本文を note にコピペ投稿
  4. 完成した note URL を Issue に `note: https://note.com/...` 形式で
     コメントすると、別 workflow が走って X に投稿する
  5. Issue は自動でクローズ

Issue タイトル先頭に `[DRAFT]` を付ける(他 workflow のフィルタ用)。
"""

from __future__ import annotations

import base64
import logging
import os
import subprocess
from pathlib import Path

from github import Github, Auth

import json

from .article_generator import Article
from .trend_scanner import Trend
from .engagement_optimizer import build_article_tweet, build_article_thread

log = logging.getLogger(__name__)

ISSUE_LABEL = "auto-draft"


def _gh_client() -> Github:
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not token:
        raise RuntimeError("GITHUB_TOKEN / GH_TOKEN is not set")
    return Github(auth=Auth.Token(token))


def _repo_full_name() -> str:
    name = os.environ.get("GITHUB_REPOSITORY") or os.environ.get("GH_REPO")
    if not name:
        raise RuntimeError("GITHUB_REPOSITORY / GH_REPO is not set (owner/repo)")
    return name


def _commit_artifacts(
    repo, branch: str, article_path: str, thumb_path: str,
    article_md: str, thumb_bytes: bytes, message: str,
) -> tuple[str, str]:
    """ブランチに article.md とサムネ画像を commit。raw URL を返す。"""
    # ブランチが無ければ default branch から作る
    default_branch = repo.default_branch
    try:
        repo.get_branch(branch)
    except Exception:
        src = repo.get_branch(default_branch)
        repo.create_git_ref(ref=f"refs/heads/{branch}", sha=src.commit.sha)
        log.info("created branch: %s", branch)

    # 既存ファイルがあれば update、無ければ create
    def _put(path: str, content_bytes: bytes):
        try:
            existing = repo.get_contents(path, ref=branch)
            repo.update_file(path, message, content_bytes, existing.sha, branch=branch)
        except Exception:
            repo.create_file(path, message, content_bytes, branch=branch)

    _put(article_path, article_md.encode("utf-8"))
    _put(thumb_path, thumb_bytes)

    raw_base = f"https://raw.githubusercontent.com/{repo.full_name}/{branch}"
    return f"{raw_base}/{article_path}", f"{raw_base}/{thumb_path}"


def publish(article: Article, trend: Trend, thumbnail_path: Path) -> str:
    """Issue を立てて URL を返す。"""
    gh = _gh_client()
    repo = gh.get_repo(_repo_full_name())

    # サムネ画像読み込み
    thumb_bytes = Path(thumbnail_path).read_bytes()

    # ブランチ & パス
    slug = _slugify(article.title)[:40]
    timestamp = _utc_stamp()
    branch = f"draft/{timestamp}-{slug}"
    article_path = f"drafts/{timestamp}-{slug}/article.md"
    thumb_path = f"drafts/{timestamp}-{slug}/thumbnail.png"

    article_raw_url, thumb_raw_url = _commit_artifacts(
        repo, branch, article_path, thumb_path,
        article.markdown, thumb_bytes,
        message=f"draft: {article.title}",
    )

    body = _build_issue_body(article, trend, article_raw_url, thumb_raw_url)
    labels = [ISSUE_LABEL, f"cat:{trend.category}", f"tier:{article.tier}"]
    issue = repo.create_issue(
        title=f"[DRAFT][{article.tier.upper()}] {article.title}",
        body=body,
        labels=labels,
    )
    log.info("issue created: %s", issue.html_url)
    return issue.html_url


def _build_issue_body(article: Article, trend: Trend,
                      article_url: str, thumb_url: str) -> str:
    # tier に応じてツイート文を組み立てる。
    # premium 記事はスレッド(5連投)で露出最大化。free/entry は単発。
    if article.tier == "premium":
        thread_tweets = build_article_thread(
            title=article.title,
            summary=article.summary,
            keyword=trend.keyword,
            category=trend.category,  # type: ignore[arg-type]
            note_url_placeholder="{NOTE_URL}",
        )
        tweet_template = "```thread_json\n" + json.dumps(
            thread_tweets, ensure_ascii=False, indent=2
        ) + "\n```"
        tweet_mode_label = f"🧵 スレッド ({len(thread_tweets)} 連投)"
    else:
        tweet_template = build_article_tweet(
            title=article.title,
            summary=article.summary,
            keyword=trend.keyword,
            category=trend.category,  # type: ignore[arg-type]
            note_url_placeholder="{NOTE_URL}",
        )
        tweet_template = f"```\n{tweet_template}\n```"
        tweet_mode_label = "📝 単発ツイート"
    # tier に応じた公開手順
    tier_block = _build_tier_block(article)

    return f"""## 📝 ドラフト生成完了

**Tier**: `{article.tier}` {'(無料)' if article.tier == 'free' else f'(¥{article.price_jpy} 有料)'}
**カテゴリ**: `{trend.category}`
**主題**: {trend.keyword}
**情報源**: {trend.source}
**文字数**: {article.char_count:,} 文字

{tier_block}

### 🖼 サムネイル
![thumbnail]({thumb_url})

### 📄 本文 (Markdown)
- [📥 article.md を開く]({article_url})

下の `<details>` を展開すると本文が表示されます。 note 編集画面にコピペしてください。

<details>
<summary>本文を表示 / 折りたたむ</summary>

{article.markdown}

</details>

---

### 🐦 ツイート文(自動投稿される文面) — {tweet_mode_label}
{tweet_template}

---

### ✅ 公開後の手順
1. 上記本文を note にコピペして投稿(サムネは画像をダウンロードして使用)
2. **(有料記事の場合のみ)** 本文中の `<!-- PAYWALL -->` の位置で note の有料境界を設定し、価格を **¥{article.price_jpy}** に
3. 完成した note 記事の URL を **このIssue にコメント** してください
4. コメント形式: `note: https://note.com/...`
5. 自動で X に投稿され、Issue は自動クローズされます

---
🤖 このIssueは `generate-draft.yml` workflow によって自動生成されました。
"""


def _build_tier_block(article: Article) -> str:
    """tier に応じた追加ガイドブロック。"""
    if article.tier == "free":
        return "> 🆓 **無料記事** として公開してください。"
    if article.tier == "entry":
        return (
            f"> 💰 **有料記事(¥{article.price_jpy} / 入口)** として公開してください。\n"
            "> - 本文中の `<!-- PAYWALL -->` の位置で note 有料境界を設定\n"
            "> - note の販売価格を **¥100** に設定\n"
            "> - 紹介文(無料閲覧部分)は冒頭〜PAYWALLマーカーまでが該当\n"
            "> - マガジン『金融トレンド徹底解剖』に **必ず** 追加(連載化で買い増しを誘発)"
        )
    if article.tier == "premium":
        return (
            f"> 💎 **有料記事(¥{article.price_jpy} / 主力)** として公開してください。\n"
            "> - 本文中の `<!-- PAYWALL -->` の位置で note 有料境界を設定\n"
            "> - note の販売価格を **¥500** に設定\n"
            "> - 紹介文(無料閲覧部分)は冒頭〜PAYWALLマーカーまでが該当\n"
            "> - **無料記事3本+本記事のリンク** を末尾に並べて回遊を強化\n"
            "> - マガジン『金融トレンド徹底解剖』に **必ず** 追加"
        )
    return ""


def _slugify(text: str) -> str:
    import re
    text = re.sub(r"[^\w\-ぁ-んァ-ヶ一-龠]+", "-", text)
    return text.strip("-").lower()


def _utc_stamp() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
