"""
run_local.py — ローカル環境でフルパイプラインを試すデバッグ用スクリプト。

GitHub に push せず、Issue 発行もスキップして、生成物をローカルに保存する。

Usage:
    cp .env.example .env   # APIキーを記入
    python scripts/run_local.py
"""

from __future__ import annotations

import logging
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# .env を読み込む(あれば)
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

from src.trend_scanner import pick_one
from src.article_generator import generate as generate_article
from src.affiliate_inserter import insert as insert_affiliate
from src.thumbnail_generator import generate as generate_thumbnail


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
    log = logging.getLogger("local-pipeline")

    seed = int(time.time())
    trend = pick_one(seed=seed)
    if not trend:
        log.error("no trend"); return 1
    log.info("trend: %s / %s", trend.category, trend.keyword)

    article = generate_article(trend)
    article.markdown = insert_affiliate(article.markdown)

    out = ROOT / "output" / f"local_{seed}"
    out.mkdir(parents=True, exist_ok=True)
    (out / "article.md").write_text(article.markdown, encoding="utf-8")
    log.info("article saved: %s", out / "article.md")

    generate_thumbnail(
        topic=trend.keyword,
        category=trend.category,  # type: ignore[arg-type]
        title=article.title,
        out_path=out / "thumbnail.png",
    )
    log.info("thumbnail saved: %s", out / "thumbnail.png")

    print("\n========== SUMMARY ==========")
    print(f"Title:   {article.title}")
    print(f"Chars:   {article.char_count}")
    print(f"Summary: {article.summary}")
    print(f"Outdir:  {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
