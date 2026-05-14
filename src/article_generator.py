"""
article_generator.py — Claude API で 1 万字の note 用記事を生成する。

長文化のコツ:
  Claude は単発呼び出しで 4000-6000 文字程度が安定上限なので、
  1) 構成決定 (Outline) 2) 本文生成 (Body) 3) 補強 (Expand) の
  3 段でチェーンして 1 万字を狙う。
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass
from pathlib import Path

from anthropic import Anthropic

from typing import Literal

from .trend_scanner import Trend
from . import cost_guard

Tier = Literal["free", "entry", "premium"]

log = logging.getLogger(__name__)

MODEL = "claude-sonnet-4-6"
PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"


@dataclass
class Article:
    title: str
    markdown: str   # 完成記事(Markdown, アフィリプレースホルダ込み)
    summary: str    # X 投稿用 100 文字以内の要約
    char_count: int
    tier: Tier = "free"
    price_jpy: int = 0   # 0 なら無料


def _load_system_prompt(tier: Tier = "free") -> str:
    base = (PROMPTS_DIR / "article_system.md").read_text(encoding="utf-8")
    if tier in ("entry", "premium"):
        addendum = (PROMPTS_DIR / "article_paid_addendum.md").read_text(encoding="utf-8")
        tier_marker = f"\n\n# 🎯 本記事の tier 指定\n本記事は tier=**{tier}** で生成されます。"
        return base + "\n\n" + addendum + tier_marker
    return base


_TIER_PRICE: dict[str, int] = {"free": 0, "entry": 100, "premium": 500}
_TIER_CHARS: dict[str, int] = {"free": 10000, "entry": 7000, "premium": 13000}


def _client() -> Anthropic:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set")
    return Anthropic(api_key=api_key)


def _ask(client: Anthropic, system: str, user: str, max_tokens: int = 8000) -> str:
    """Claude 単発呼び出し。コストを cost_guard に記録する。"""
    resp = client.messages.create(
        model=MODEL,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    # コスト記録
    try:
        usage = getattr(resp, "usage", None)
        if usage is not None:
            usd = cost_guard.claude_cost(
                input_tokens=getattr(usage, "input_tokens", 0),
                output_tokens=getattr(usage, "output_tokens", 0),
                model=MODEL,
            )
            cost_guard.record(usd)
    except Exception as e:
        log.warning("cost recording failed: %s", e)

    return "".join(b.text for b in resp.content if hasattr(b, "text"))


# ----------------------------------------------------------------------
# 3 段生成
# ----------------------------------------------------------------------

def _stage_outline(client: Anthropic, trend: Trend, system: str) -> str:
    """Outline 段階。各 H2 セクションのキーポイントを 200 字程度で列挙させる。"""
    user = f"""以下のトレンドについて、 note 記事の **構成案(各H2ごとのキーポイント箇条書き)** を作成してください。
本文は書かないでください。構成案のみを出力すること。

# 入力トレンド
- カテゴリ: {trend.category}
- キーワード: {trend.keyword}
- 見出し: {trend.headline}
- 情報源: {trend.source}

# 出力フォーマット
- まず「タイトル候補(3 案)」を提示
- 続いて H2 1〜まとめまでのキーポイントを各 200 字程度で
"""
    return _ask(client, system, user, max_tokens=3000)


def _stage_body(client: Anthropic, trend: Trend, outline: str, system: str) -> str:
    """Body 段階。アウトラインを元に本文を書く。"""
    user = f"""以下の構成案をもとに、note 記事の **本文を最後まで完成形** で書いてください。
アウトライン中の3つのタイトル案からもっとも興味喚起力の高いものを 1 つ選んで使うこと。

# 入力トレンド
- カテゴリ: {trend.category}
- キーワード: {trend.keyword}
- 見出し: {trend.headline}

# 構成案
{outline}

# 出力ルール
- システムプロンプトの「必達要件」と「スタイルガイド」を厳守すること
- アフィリエイトプレースホルダ `[[AFFILIATE_INTRO]]` `[[AFFILIATE_BODY_1]]` `[[AFFILIATE_BODY_2]]` `[[AFFILIATE_OUTRO]]` を所定の位置に必ず挿入
- Markdown 1ファイルで完結する形で出力
"""
    return _ask(client, system, user, max_tokens=8000)


def _stage_expand(client: Anthropic, draft: str, system: str, target_chars: int = 10000) -> str:
    """draft が target_chars に届かなければ各セクションを補強する。"""
    current = _count_chars(draft)
    if current >= target_chars:
        return draft

    shortage = target_chars - current
    user = f"""以下の note 記事の文字数を増やしたいです。本文の意味は変えず、
**各 H2 セクションに具体例・数値・体験談的なエピソード・補足解説を追加** して、
合計で **{shortage} 文字以上** 増やしてください。

新しいセクションは追加しないこと。既存セクションの中身を厚くするだけにすること。
アフィリエイトプレースホルダの位置は絶対に動かさないこと。

# 元の記事
{draft}

# 出力
増補後の完成版 Markdown 全文のみを出力すること(差分やコメントは不要)。
"""
    return _ask(client, system, user, max_tokens=8000)


# ----------------------------------------------------------------------
# 後処理
# ----------------------------------------------------------------------

_TITLE_RE = re.compile(r"^#\s+(.+?)$", re.MULTILINE)


def _extract_title(markdown: str) -> str:
    m = _TITLE_RE.search(markdown)
    if not m:
        return "金融トレンド最新解説"
    return m.group(1).strip()


def _count_chars(markdown: str) -> int:
    """Markdown 記法を取り除いた本文文字数の概算。"""
    # コードブロックを除外
    body = re.sub(r"```.*?```", "", markdown, flags=re.DOTALL)
    # 記号類を除外
    body = re.sub(r"[#*_>`\-|\[\]()!]", "", body)
    body = re.sub(r"\s+", "", body)
    return len(body)


def _make_summary(client: Anthropic, article_md: str, trend: Trend) -> str:
    """X ツイート本文(中盤)用のフック要約を作る。
    フォロワー獲得のため、続きが気になる構造に。70〜90 文字を目安に。"""
    user = f"""以下の note 記事の **本文の "核心"** を、X のフォロワー獲得目的で
**70〜90 文字** にまとめてください。

# 必須要件
- **続きが気になる "途中で切る" 構造** にする(全部書ききらない)
- 具体的な数字を 1 つは必ず含める
- 「実は」「3 つあって」「核心は」のような分解語を使う
- ハッシュタグ・絵文字・URL は不要(別途付与される)
- 「↓詳細は note で」など定型 CTA は禁止(別途付与される)
- 「私は AI」等の自己言及禁止

# 記事タイトル
{_extract_title(article_md)}

# 記事冒頭(参考)
{article_md[:800]}

# 良い出力例
- 「結論から言うと、半減期後に上がるのは "ある条件" が揃った時だけ。過去 3 回のデータで判明した共通点が 1 つあります。」
- 「新 NISA で年 50 万円差がつく口座選び 3 原則。99% の人が見落とすのは "つみたて枠の○○" です。」
"""
    text = _ask(client, "あなたは X のフォロワー獲得に特化したコピーライターです。",
                user, max_tokens=400)
    text = text.strip().strip("「」\"'`")
    # 改行を取り除き 1 段落に
    text = " ".join(line.strip() for line in text.splitlines() if line.strip())
    return text[:130]


# ----------------------------------------------------------------------
# 公開関数
# ----------------------------------------------------------------------

def generate(trend: Trend, tier: Tier = "free",
             target_chars: int | None = None) -> Article:
    """1 件のトレンドから tier に応じた記事を生成して Article を返す。"""
    client = _client()
    system = _load_system_prompt(tier)
    target_chars = target_chars or _TIER_CHARS.get(tier, 10000)

    log.info("Stage 1/3 outline: tier=%s keyword=%s", tier, trend.keyword)
    outline = _stage_outline(client, trend, system)

    log.info("Stage 2/3 body")
    draft = _stage_body(client, trend, outline, system)

    log.info("Stage 3/3 expand (target=%d chars)", target_chars)
    final_md = _stage_expand(client, draft, system, target_chars)

    title = _extract_title(final_md)
    summary = _make_summary(client, final_md, trend)
    char_count = _count_chars(final_md)

    log.info("Article generated: %d chars (tier=%s)", char_count, tier)
    return Article(
        title=title,
        markdown=final_md,
        summary=summary,
        char_count=char_count,
        tier=tier,
        price_jpy=_TIER_PRICE.get(tier, 0),
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    from .trend_scanner import pick_one

    t = pick_one()
    if t:
        art = generate(t)
        print(f"=== {art.title} ===")
        print(f"chars: {art.char_count}")
        print(f"summary: {art.summary}")
        print(art.markdown[:1200])
