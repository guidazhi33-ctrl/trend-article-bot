"""smoke_local.py — Anthropicキーだけでの最小動作確認スクリプト。

DALL-E のサムネ生成と GitHub Issue 発行はスキップし、
- トレンド取得
- Claude による記事生成(3段)
- アフィリ挿入

までを行って、生成された Markdown をローカルに保存する。

Usage:
    cp .env.example .env  # ANTHROPIC_API_KEY を実値に
    .venv/bin/python scripts/smoke_local.py
"""

from __future__ import annotations

import logging
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

from src.trend_scanner import pick_one
from src.article_generator import generate as generate_article
from src.affiliate_inserter import insert as insert_affiliate


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
    log = logging.getLogger("smoke")

    seed = int(time.time())
    trend = pick_one(seed=seed)
    if not trend:
        log.error("no trend found"); return 1
    log.info("trend: [%s] %s — %s", trend.category, trend.keyword, trend.headline)

    article = generate_article(trend, tier="free")
    article.markdown = insert_affiliate(article.markdown)

    out = ROOT / "output" / f"smoke_{seed}"
    out.mkdir(parents=True, exist_ok=True)
    (out / "article.md").write_text(article.markdown, encoding="utf-8")

    print()
    print("=" * 50)
    print(f"Title:   {article.title}")
    print(f"Chars:   {article.char_count}")
    print(f"Summary: {article.summary}")
    print(f"Saved:   {out / 'article.md'}")
    print("=" * 50)
    return 0


if __name__ == "__main__":
    sys.exit(main())
