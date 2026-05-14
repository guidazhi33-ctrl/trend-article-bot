"""
generate_one_draft.py — 1 件のドラフトを生成するエントリポイント。

GitHub Actions の generate-draft.yml から呼ばれる。手順:
  0. cost_guard で日次/月次の API 予算が残っているか確認
  1. tier 判定(日中の何本目かで free/entry/premium を切り替え)
  2. trend_scanner でトレンドを 1 件取得
  3. article_generator で tier に応じた記事を生成
  4. affiliate/follow CTA/LINE CTA を挿入
  5. thumbnail_generator でサムネを生成
  6. draft_publisher で GitHub Issue として発行
"""

from __future__ import annotations

import logging
import os
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.trend_scanner import pick_one
from src.article_generator import generate as generate_article, Tier
from src.affiliate_inserter import insert as insert_affiliate
from src.thumbnail_generator import generate as generate_thumbnail
from src.draft_publisher import publish as publish_draft
from src.engagement_optimizer import inject_follow_ctas, next_topic_hint
from src import cost_guard


JST = timezone(timedelta(hours=9))


def _decide_tier_for_now() -> Tier:
    """JST の "今日 N 本目か" で tier を決める。

    cron は JST 06/07/08/12/14/17/19/21/22/23 時の計10回。
    そのうち
      - 2 本目(07時)  → entry  (¥100)
      - 5 本目(14時)  → premium (¥500)
      - 8 本目(21時)  → premium (¥500)
      - 残り 7 本     → free
    の配分にする。
    """
    h = datetime.now(JST).hour
    if h == 7:
        return "entry"
    if h in (14, 21):
        return "premium"
    return "free"


def _inject_line_cta(markdown: str) -> str:
    """全記事末尾(免責の前)に LINE 登録 CTA を挿入。"""
    line_url = os.environ.get("LINE_OFFICIAL_URL", "").strip()
    if not line_url:
        return markdown

    cta = (
        "\n\n---\n\n"
        "### 📱 公式 LINE で日次相場レポートを無料配信中\n\n"
        f"記事だけでは伝えきれない **当日の重要指標・要人発言の速報** を、"
        f"毎朝 7 時に LINE で配信しています(無料・解除自由)。\n\n"
        f"👉 **[LINE で友だち追加して受け取る]({line_url})**\n\n"
        "登録者特典: 『金融トレンド見極めチェックリスト(PDF)』を初回配信時にプレゼント\n\n"
        "---\n\n"
    )
    # 免責(末尾の「※本記事は」)の **直前** に差し込む
    marker = "※本記事は"
    if marker in markdown:
        return markdown.replace(marker, cta + marker, 1)
    return markdown.rstrip() + cta


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
    log = logging.getLogger("draft-pipeline")

    # 0. コスト上限チェック
    try:
        cost_guard.check_pre_run()
    except cost_guard.CostLimitExceeded as e:
        log.warning("cost limit hit: %s", e)
        # GitHub Actions の Summary に通知
        summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
        if summary_path:
            with open(summary_path, "a", encoding="utf-8") as f:
                f.write(f"## ⚠ コスト上限到達でスキップ\n\n{e}\n")
        return 0

    # 1. tier 判定
    tier = _decide_tier_for_now()
    log.info("tier for this run: %s", tier)

    # 2. トレンド取得
    seed = int(time.time())
    trend = pick_one(seed=seed)
    if not trend:
        log.error("no trend available; aborting")
        return 1
    log.info("selected trend: [%s] %s", trend.category, trend.keyword)

    # 3. 記事生成
    article = generate_article(trend, tier=tier)
    log.info("article: %s (%d chars, tier=%s, price=¥%d)",
             article.title, article.char_count, article.tier, article.price_jpy)

    # 4. CTA 挿入(フォロー → LINE → アフィリの順)
    hint = next_topic_hint(trend.category)  # type: ignore[arg-type]
    article.markdown = inject_follow_ctas(article.markdown, next_topic_hint=hint)
    article.markdown = _inject_line_cta(article.markdown)
    article.markdown = insert_affiliate(article.markdown)

    # 5. サムネ生成
    out_dir = ROOT / "output"
    out_dir.mkdir(exist_ok=True)
    thumb_path = out_dir / f"thumb_{seed}.png"
    generate_thumbnail(
        topic=trend.keyword,
        category=trend.category,  # type: ignore[arg-type]
        title=article.title,
        out_path=thumb_path,
    )

    # 6. Issue 発行
    issue_url = publish_draft(article, trend, thumb_path)
    log.info("DONE: %s", issue_url)

    # 7. Summary 出力
    daily_usd, monthly_usd = cost_guard.snapshot()
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        with open(summary_path, "a", encoding="utf-8") as f:
            f.write(f"## 📝 New draft published\n\n")
            f.write(f"- **Tier**: `{article.tier}` (¥{article.price_jpy})\n")
            f.write(f"- **Trend**: `{trend.category}` / {trend.keyword}\n")
            f.write(f"- **Title**: {article.title}\n")
            f.write(f"- **Chars**: {article.char_count:,}\n")
            f.write(f"- **Issue**: {issue_url}\n")
            f.write(f"- **API cost**: today $\\${daily_usd:.3f} / month $\\${monthly_usd:.3f}\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
