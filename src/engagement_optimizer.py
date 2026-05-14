"""
engagement_optimizer.py — フォロワー獲得最適化のための補助モジュール。

責務:
  1. 時間帯×カテゴリ で適切なハッシュタグを動的に組み立てる
  2. フックパターン(1 行目テンプレ)とフォロー CTA を提供
  3. note 本文中の `[[FOLLOW_CTA_INTRO]]` / `[[FOLLOW_CTA_OUTRO]]` を実テキストに置換

X の文字数(140 全角=280 半角)制限内で「フック+本文+CTA+ハッシュタグ+URL」を
収めるためのトリミング関数もここに置く。

参考: 日本人の SNS 利用ピークは JST 7-9 / 12-13 / 18-22。本モジュールは
JST の hour を見て曜日とともにタグを切り替える。
"""

from __future__ import annotations

import random
from datetime import datetime, timezone, timedelta
from typing import Literal

Category = Literal["stock", "fx", "crypto"]

JST = timezone(timedelta(hours=9))


# ----------------------------------------------------------------------
# ハッシュタグ
# ----------------------------------------------------------------------

# カテゴリ別の基本タグ(常時候補)
_BASE_TAGS: dict[str, list[str]] = {
    "stock":  ["#株式投資", "#新NISA", "#日本株", "#米国株", "#高配当株",
               "#投資初心者", "#資産形成"],
    "fx":     ["#FX", "#FX初心者", "#ドル円", "#為替", "#トレード",
               "#スキャルピング", "#デイトレ"],
    "crypto": ["#暗号資産", "#ビットコイン", "#仮想通貨", "#BTC", "#ETH",
               "#Web3", "#暗号資産投資"],
}

# 時間帯別の「気分」タグ(差別化用)
_TIME_TAGS: dict[str, list[str]] = {
    "morning":   ["#おはようVtuber", "#今日の戦略", "#朝活", "#マーケットオープン"],
    "noon":      ["#昼休み読書", "#今日のマーケット"],
    "evening":   ["#相場振り返り", "#今日の値動き", "#NY市場"],
    "night":     ["#相場分析", "#明日の戦略", "#夜活"],
}


def _time_slot(now_jst: datetime) -> str:
    h = now_jst.hour
    if 5 <= h < 11:
        return "morning"
    if 11 <= h < 14:
        return "noon"
    if 14 <= h < 20:
        return "evening"
    return "night"


def pick_hashtags(category: Category, n: int = 3,
                  now_jst: datetime | None = None) -> list[str]:
    """カテゴリ+時間帯から n 個のハッシュタグを選ぶ。"""
    now_jst = now_jst or datetime.now(JST)
    base = list(_BASE_TAGS.get(category, _BASE_TAGS["stock"]))
    time = list(_TIME_TAGS.get(_time_slot(now_jst), []))

    random.shuffle(base)
    random.shuffle(time)
    # 基本タグから 2, 時間帯タグから 1 を基本構成にする(n に応じて調整)
    picked: list[str] = []
    picked.extend(base[: max(1, n - 1)])
    if time and len(picked) < n:
        picked.append(time[0])
    return picked[:n]


# ----------------------------------------------------------------------
# ツイートのフック(1 行目)パターン
# ----------------------------------------------------------------------

_HOOK_PATTERNS: list[str] = [
    "🚨 {keyword} で今、知らないと損する話を 1 本書きました。",
    "📊 {keyword} の『本当の動き』を 3 つの数字で整理しました ↓",
    "❓ {keyword} って結局どこまで上がる/下がる? 個人投資家目線で整理:",
    "💡 {keyword} に乗り遅れた人へ。『今から取れる戦略』を 1 万字でまとめました。",
    "⚠ {keyword} で 9 割が見落としている『あの数字』について書きました。",
    "🔥 {keyword} がトレンド入り。プロが今チェックしている指標は?",
    "📈 {keyword} を初心者向けに 5 分で理解できるよう書きました。",
    "👀 {keyword} の今後 30 日『3 つのシナリオ』を本気で予想:",
]


def pick_hook(keyword: str) -> str:
    return random.choice(_HOOK_PATTERNS).format(keyword=keyword)


# ----------------------------------------------------------------------
# フォロー CTA(X 用 / note 用)
# ----------------------------------------------------------------------

_X_CTA_PATTERNS: list[str] = [
    "👉 フォローで「金融トレンドの裏側」を毎日キャッチ",
    "✅ 役立ったらフォロー&リポストで応援お願いします",
    "📌 株/FX/暗号資産のトレンド解説、毎日更新中→フォロー推奨",
    "🔔 通知ON+フォローで最新トレンドを取りこぼし無し",
]


def pick_x_cta() -> str:
    return random.choice(_X_CTA_PATTERNS)


_NOTE_FOLLOW_INTRO_TEMPLATES: list[str] = [
    "> 🔔 **このアカウントについて**\n> 株 / FX / 暗号資産の **市場トレンドを毎日 10 本の深掘り記事** にしてお届けしています。\n> 「フォロー」しておくと、相場の節目で必ず役立つ記事が届きます。\n",

    "> 👉 **連載シリーズの一環です**\n> 本記事は『金融トレンド徹底解剖』シリーズの一本です。\n> 過去の人気回や次回予告は **プロフィールから一覧で見られます** → ぜひフォローを。\n",

    "> 📩 **記事をストックしてくれる方へ**\n> 毎週・各カテゴリで反響の大きかった記事を選んで配信しています。\n> 見逃し防止には **フォロー + スキ** が最強です。よろしくお願いします。\n",
]

_NOTE_FOLLOW_OUTRO_TEMPLATES: list[str] = [
    "---\n\n### 🎁 最後まで読んでくださってありがとうございます\n\nこの記事が役に立ったら、ぜひ **♡(スキ)** とフォローをお願いします。\n金融トレンドの裏側を毎日深掘りでお届けしています。\n\n**次回予告**: {{NEXT_TOPIC_HINT}} について書きます。フォローしておくと通知が届きます。\n\n---\n",

    "---\n\n### 📣 ここまで読んだあなたに 3 つのお願い\n\n1. 役に立ったら **スキ(♡)** をお願いします(投稿継続のモチベになります)\n2. 「金融トレンドの解説をもっと読みたい」と思ったら **フォロー** をお願いします\n3. このテーマで聞きたいことがあれば **コメント** で教えてください\n\n次回もお楽しみに。\n\n---\n",

    "---\n\n### ✍ 著者より\n\nこのアカウントでは **株 / FX / 暗号資産のトレンドを 1 日 10 本ペースで深掘り** しています。\nあなたの投資判断の解像度を上げる記事を毎日届けるので、ぜひ **フォロー** をお願いします。\n\n💬 質問・要望はコメント欄へどうぞ。\n\n---\n",
]


def render_follow_cta_intro() -> str:
    return random.choice(_NOTE_FOLLOW_INTRO_TEMPLATES)


def render_follow_cta_outro(next_topic_hint: str = "為替市場の重要イベント") -> str:
    return (random.choice(_NOTE_FOLLOW_OUTRO_TEMPLATES)
            .replace("{{NEXT_TOPIC_HINT}}", next_topic_hint))


def inject_follow_ctas(markdown: str, next_topic_hint: str | None = None) -> str:
    """`[[FOLLOW_CTA_INTRO]]` / `[[FOLLOW_CTA_OUTRO]]` を実テキストに置換。"""
    intro = render_follow_cta_intro()
    outro = render_follow_cta_outro(next_topic_hint or "為替市場の次の節目")
    markdown = markdown.replace("[[FOLLOW_CTA_INTRO]]", intro, 1)
    markdown = markdown.replace("[[FOLLOW_CTA_OUTRO]]", outro, 1)
    # 残ったら消す
    markdown = markdown.replace("[[FOLLOW_CTA_INTRO]]", "")
    markdown = markdown.replace("[[FOLLOW_CTA_OUTRO]]", "")
    return markdown


# ----------------------------------------------------------------------
# ツイート組み立て
# ----------------------------------------------------------------------

# t.co の URL は一律 23 文字に短縮される
_T_CO_URL_LEN = 23
_TWEET_LIMIT = 280


def build_article_tweet(
    title: str,
    summary: str,
    keyword: str,
    category: Category,
    note_url_placeholder: str = "{NOTE_URL}",
) -> str:
    """記事公開時のツイート文を組み立てる(URL は後で差し込み前提)."""
    hook = pick_hook(keyword)
    cta = pick_x_cta()
    tags = " ".join(pick_hashtags(category, n=3))

    # 構造: フック \n\n 要約 \n\n CTA \n\n hashtags \n URL(後で置換)
    body = f"{hook}\n\n{summary}\n\n{cta}\n\n{tags}\n{note_url_placeholder}"

    # URL placeholder 部分は実 URL に置換されると 23 文字になる前提で
    # 残りを計算
    reserved = _T_CO_URL_LEN + 1  # URL + 改行
    text_budget = _TWEET_LIMIT - reserved

    placeholder_len = len(note_url_placeholder)
    overshoot = (len(body) - placeholder_len + _T_CO_URL_LEN) - _TWEET_LIMIT
    if overshoot > 0:
        # summary を削る
        new_summary_len = max(20, len(summary) - overshoot - 2)
        summary = summary[:new_summary_len].rstrip() + "…"
        body = f"{hook}\n\n{summary}\n\n{cta}\n\n{tags}\n{note_url_placeholder}"
    return body


def build_article_thread(
    title: str,
    summary: str,
    keyword: str,
    category: Category,
    note_url_placeholder: str = "{NOTE_URL}",
    body_chunks: list[str] | None = None,
) -> list[str]:
    """記事連動の **5 ツイート程度のミニスレッド** を組み立てる。

    構成:
      1) フック+疑問形 (続きを読みたくさせる)
      2) 結論 1 行(数字)
      3) 補足 (背景)
      4) 補足 (落とし穴)
      5) CTA + note URL + ハッシュタグ
    """
    tags = " ".join(pick_hashtags(category, n=2))
    hook = pick_hook(keyword)
    cta = pick_x_cta()

    # body_chunks が無ければ summary を1チャンク扱い
    chunks = body_chunks or [summary]

    tweets: list[str] = []
    # 1) フック
    tweets.append(f"{hook}\n\n👇 結論からスレッドで解説します。")
    # 2-4) 各 body chunk(最大3個)
    for i, ch in enumerate(chunks[:3], start=2):
        prefix = f"{i}/"
        body = f"{prefix} {ch}"
        if len(body) > _TWEET_LIMIT - 5:
            body = body[: _TWEET_LIMIT - 6] + "…"
        tweets.append(body)
    # 5) CTA + URL
    final = f"{len(tweets) + 1}/ 詳しくは note の本記事で👇\n\n{cta}\n\n{tags}\n{note_url_placeholder}"
    # URL 占有 23 文字を考慮
    if len(final) - len(note_url_placeholder) + _T_CO_URL_LEN > _TWEET_LIMIT:
        # tags を削る
        final = f"{len(tweets) + 1}/ 詳しくは note の本記事で👇\n\n{cta}\n{note_url_placeholder}"
    tweets.append(final)
    return tweets


def build_news_tweet(
    translated_block: str,
    category: Category,
    source_url: str,
) -> str:
    """Claude が news_translate プロンプトに従って生成した翻訳済みブロック
    (見出し+本文+反応誘発質問)に、ハッシュタグと URL を結合して
    280 文字以内に収める。"""
    tags = " ".join(pick_hashtags(category, n=2))
    block = translated_block.rstrip()

    # ハッシュタグ込みでも URL(t.co 短縮 23 文字)を足して 280 以内になるよう調整
    reserved_for_url = _T_CO_URL_LEN + 1  # URL 行
    tag_block = f"\n{tags}"
    budget = _TWEET_LIMIT - reserved_for_url - len(tag_block)

    if len(block) > budget:
        block = block[: budget - 1].rstrip() + "…"

    return f"{block}{tag_block}\n{source_url}"


# ----------------------------------------------------------------------
# 「次回ヒント」生成 — 連載示唆用
# ----------------------------------------------------------------------

_NEXT_HINTS_BY_CATEGORY: dict[str, list[str]] = {
    "stock":  ["新 NISA 攻略の落とし穴", "次の決算シーズンの注目銘柄",
               "高配当株ポートフォリオの組み方", "米国株 vs 日本株の最新リターン比較"],
    "fx":     ["次回 FOMC のシナリオ分析", "ドル円のテクニカル節目",
               "為替介入ラインの読み方", "クロス円トレードの最新戦略"],
    "crypto": ["次の半減期サイクルの読み方", "イーサリアム ETF の影響分析",
               "ステーブルコイン規制の最新動向", "アルトコイン投資の注意点"],
}


def next_topic_hint(category: Category) -> str:
    return random.choice(_NEXT_HINTS_BY_CATEGORY.get(category, ["金融市場の重要イベント"]))
