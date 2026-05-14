"""
affiliate_inserter.py — 記事中のプレースホルダを内容適合アフィリリンクに置換。

article_generator が残した
    [[AFFILIATE_INTRO]]  [[AFFILIATE_BODY_1]]  [[AFFILIATE_BODY_2]]  [[AFFILIATE_OUTRO]]
の 4 つのプレースホルダを以下のルールで実リンクに置換する:

  INTRO  : 上位カテゴリの A8 案件(口座開設系)
  BODY_1 : 同上(別 URL)
  BODY_2 : AMAZON_AFFILIATE_ID が設定されていて Amazon 書籍が定義されていれば
           書籍リコメンドを優先採用。それ以外は A8。
  OUTRO  : 上位カテゴリの A8 案件(別 URL)

Amazon リンクには規約・景表法対応の開示文(`amazon_disclosure`)を自動付与。
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Iterable

import yaml

log = logging.getLogger(__name__)

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "affiliate_links.yaml"

PLACEHOLDERS = (
    "[[AFFILIATE_INTRO]]",
    "[[AFFILIATE_BODY_1]]",
    "[[AFFILIATE_BODY_2]]",
    "[[AFFILIATE_OUTRO]]",
)


def _load_config() -> dict:
    return yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))


def _score_category(markdown: str, keywords: Iterable[str]) -> int:
    return sum(markdown.count(kw) for kw in keywords)


def _rank_categories(markdown: str, categories: dict) -> list[str]:
    scored = [
        (cat, _score_category(markdown, conf.get("keywords", [])))
        for cat, conf in categories.items()
    ]
    scored.sort(key=lambda x: x[1], reverse=True)
    log.info("category scores: %s", scored)
    return [c for c, s in scored if s > 0] or ["stock"]


def _substitute_amazon_id(url: str) -> str | None:
    """URL 内の `{AMAZON_ID}` を env var で置換。ID 未設定なら None。"""
    amazon_id = os.environ.get("AMAZON_AFFILIATE_ID", "").strip()
    if "{AMAZON_ID}" not in url:
        return url
    if not amazon_id:
        return None
    return url.replace("{AMAZON_ID}", amazon_id)


def _pick_amazon_book(category: str, config: dict) -> dict | None:
    """指定カテゴリの Amazon 書籍リンクを 1 件返す(ID 置換済み)."""
    for book in _amazon_books_for(category, config):
        return book
    return None


def _amazon_books_for(category: str, config: dict) -> list[dict]:
    """指定カテゴリの Amazon 書籍リンクを全件返す(ID 置換済み)."""
    books_by_cat = config.get("amazon_books", {})
    result: list[dict] = []
    for book in books_by_cat.get(category) or []:
        url = _substitute_amazon_id(book.get("url", ""))
        if url:
            result.append({**book, "url": url, "_is_amazon": True})
    return result


def _format_link(link: dict, position: str, rules: dict) -> str:
    """アフィリリンクを note Markdown 形式の埋め込みブロックに整形。"""
    style = {
        "intro": "💡 **記事を読み進める前に**\n\n",
        "body":  "📌 **おすすめサービス**\n\n",
        "outro": "🎯 **今すぐ始めるなら**\n\n",
    }[position]

    # Amazon リンクには開示文を付与
    disclosure = ""
    if link.get("_is_amazon"):
        text = rules.get(
            "amazon_disclosure",
            "※Amazonのアソシエイトとして、当アカウントは適格販売により収入を得ています。",
        )
        disclosure = f"\n\n<small>{text}</small>"

    return (
        f"\n\n---\n\n"
        f"{style}"
        f"### [{link['title']}]({link['url']})\n\n"
        f"> {link['cta']}"
        f"{disclosure}\n\n"
        f"---\n\n"
    )


def insert(markdown: str) -> str:
    """プレースホルダ 4 個を実リンクに置換して返す。"""
    config = _load_config()
    categories: dict = config["categories"]
    rules: dict = config.get("insertion_rules", {})

    ranked = _rank_categories(markdown, categories)
    primary_cat = ranked[0]

    # A8 系プール(上位 2 カテゴリ)+ education
    a8_pool: list[dict] = []
    for cat in ranked[:2]:
        a8_pool.extend(categories[cat].get("links", []))
    if "education" in categories:
        a8_pool.extend(categories["education"].get("links", []))

    # 🛡 A8 未承認(YOUR_A8_xxx プレースホルダのまま)の案件は除外。
    # これにより A8 審査待ちの段階で稼働開始しても壊れたリンクが入らない。
    before_filter = len(a8_pool)
    a8_pool = [l for l in a8_pool if "YOUR_A8" not in l.get("url", "")]
    skipped = before_filter - len(a8_pool)
    if skipped > 0:
        log.info("skipped %d placeholder A8 link(s) (未承認案件)", skipped)

    # 💰 報酬単価で降順ソート(高単価案件を優先採用)
    a8_pool.sort(key=lambda link: link.get("payout_jpy", 0), reverse=True)
    log.info("a8_pool sorted by payout: %s",
             [(l.get("title", "")[:20], l.get("payout_jpy", 0)) for l in a8_pool])

    # Amazon プール(主カテゴリ→次点カテゴリ で複数集める)。
    # A8 が未承認のまま稼働開始しても挿入できるよう、複数候補を持っておく。
    amazon_pool: list[dict] = []
    if rules.get("prefer_amazon_in_body2", True):
        for cat in ranked[:2]:
            amazon_pool.extend(_amazon_books_for(cat, config))

    if not a8_pool and not amazon_pool:
        log.warning("no affiliate links available; removing placeholders")
        for ph in PLACEHOLDERS:
            markdown = markdown.replace(ph, "")
        return markdown

    # 4 スロットを埋める
    seen_urls: set[str] = set()
    chosen: list[dict] = []
    # 規約スパム判定を避けるため Amazon は 1 記事 2 個まで
    MAX_AMAZON_PER_ARTICLE = 2
    amazon_used = 0

    def _pick_a8() -> dict | None:
        if not a8_pool:
            return None
        for link in a8_pool:
            if rules.get("dedupe", True) and link["url"] in seen_urls:
                continue
            seen_urls.add(link["url"])
            return link
        return None  # 全部使い切ったらフォールバックしない

    def _pick_amazon() -> dict | None:
        nonlocal amazon_used
        if amazon_used >= MAX_AMAZON_PER_ARTICLE:
            return None
        for book in amazon_pool:
            if book["url"] in seen_urls:
                continue
            seen_urls.add(book["url"])
            amazon_used += 1
            return book
        return None

    # INTRO: A8 高単価優先
    link = _pick_a8()
    if link:
        chosen.append(link)

    # BODY_1: A8 次点
    link = _pick_a8()
    if link:
        chosen.append(link)

    # BODY_2: Amazon 書籍 (note 規約上、文脈適合の書籍は OK)
    link = _pick_amazon() or _pick_a8()
    if link:
        chosen.append(link)

    # OUTRO: A8、なければ Amazon 2 個目
    link = _pick_a8() or _pick_amazon()
    if link:
        chosen.append(link)

    # 不足分(A8 もプレースホルダだった場合)は埋めない → 空のまま記事に出る
    # ← note 規約上「リンク無し」のほうが「同じ URL の 4 連発」よりはるかに安全

    positions = ("intro", "body", "body", "outro")
    for placeholder, link, pos in zip(PLACEHOLDERS, chosen, positions):
        block = _format_link(link, pos, rules)
        markdown = markdown.replace(placeholder, block, 1)

    # 残り(あれば)を除去
    for ph in PLACEHOLDERS:
        markdown = markdown.replace(ph, "")

    return markdown


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    sample = """# ビットコイン半減期後の戦略

[[AFFILIATE_INTRO]]

ビットコインは過去最高値を更新しています。

[[AFFILIATE_BODY_1]]

イーサリアムも連動高となっています。

[[AFFILIATE_BODY_2]]

## まとめ

暗号資産市場は引き続き活況です。

[[AFFILIATE_OUTRO]]
"""
    print(insert(sample))
