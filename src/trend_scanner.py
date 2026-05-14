"""
trend_scanner.py — 株/FX/暗号資産のリアルタイムトレンドを収集する。

データソース:
  - CoinGecko Trending API  ... 直近24h で検索回数が急増した暗号資産
  - Yahoo Finance RSS       ... 米株式・FX のニュース見出し
  - Google Trends (pytrends) ... 日本語で急上昇している金融キーワード
  - newsdata.io (optional)   ... 任意の金融キーワードで世界中のニュース

すべて無料 API もしくは RSS で構成し、API キー無しでも最低限のトレンドが取れる。
"""

from __future__ import annotations

import os
import logging
import random
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Iterable

import feedparser
import requests

log = logging.getLogger(__name__)


@dataclass
class Trend:
    """検出された 1 件のトレンド。"""
    category: str            # "fx" / "stock" / "crypto"
    keyword: str             # 主題キーワード(例: "ビットコイン")
    headline: str            # ニュース見出し or 1 行要約
    source: str              # データソース名
    url: str = ""            # 参照URL
    score: float = 0.0       # トレンド強度(0-100)。比較・ソート用
    detected_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> dict:
        return asdict(self)


# ----------------------------------------------------------------------
# 個別ソース
# ----------------------------------------------------------------------

def fetch_coingecko_trending() -> list[Trend]:
    """CoinGecko の Trending API (無料・キー不要)."""
    url = "https://api.coingecko.com/api/v3/search/trending"
    try:
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        log.warning("CoinGecko trending fetch failed: %s", e)
        return []

    trends: list[Trend] = []
    for i, item in enumerate(data.get("coins", [])[:10]):
        coin = item.get("item", {})
        name_ja = _crypto_name_ja(coin.get("name", ""), coin.get("symbol", ""))
        trends.append(Trend(
            category="crypto",
            keyword=name_ja,
            headline=f"{name_ja} ({coin.get('symbol','').upper()}) が検索急上昇中",
            source="CoinGecko Trending",
            url=f"https://www.coingecko.com/en/coins/{coin.get('id','')}",
            score=100 - i * 8,
        ))
    return trends


def _crypto_name_ja(name_en: str, symbol: str) -> str:
    """主要銘柄の英語名 → 日本語通称マッピング。マップに無いものは英語そのまま。"""
    mapping = {
        "Bitcoin": "ビットコイン",
        "Ethereum": "イーサリアム",
        "Ripple": "リップル",
        "Solana": "ソラナ",
        "Cardano": "カルダノ",
        "Dogecoin": "ドージコイン",
        "Polkadot": "ポルカドット",
        "Avalanche": "アバランチ",
        "Polygon": "ポリゴン",
        "Chainlink": "チェーンリンク",
        "Litecoin": "ライトコイン",
        "Shiba Inu": "柴犬コイン(SHIB)",
    }
    return mapping.get(name_en, f"{name_en}({symbol.upper()})" if symbol else name_en)


def fetch_yahoo_finance_rss() -> list[Trend]:
    """Yahoo Finance の主要RSS から株式・FXのニュースを取得。"""
    feeds = [
        # 米国・グローバル株式
        ("stock", "https://finance.yahoo.com/news/rssindex"),
        # 為替・通貨
        ("fx",    "https://finance.yahoo.com/topic/currencies/rss"),
    ]
    trends: list[Trend] = []
    for category, feed_url in feeds:
        try:
            parsed = feedparser.parse(feed_url)
        except Exception as e:
            log.warning("Yahoo Finance RSS fetch failed (%s): %s", feed_url, e)
            continue

        for i, entry in enumerate(parsed.entries[:8]):
            keyword = _extract_keyword(entry.title, category)
            trends.append(Trend(
                category=category,
                keyword=keyword,
                headline=entry.title,
                source="Yahoo Finance",
                url=getattr(entry, "link", ""),
                score=80 - i * 5,
            ))
    return trends


def _extract_keyword(headline: str, category: str) -> str:
    """見出しからメインキーワードを大雑把に抽出。"""
    if category == "fx":
        for pair in ("USD/JPY", "EUR/USD", "GBP/USD", "USD/CNH",
                     "ドル円", "ユーロドル", "ポンドドル"):
            if pair.lower() in headline.lower():
                return pair
        return "為替市場"
    if category == "stock":
        for sym in ("Nvidia", "Apple", "Tesla", "Microsoft", "Amazon",
                    "Google", "Meta", "S&P 500", "Nasdaq", "Dow"):
            if sym.lower() in headline.lower():
                return sym
        return "米国株"
    return "金融市場"


def fetch_google_trends_jp() -> list[Trend]:
    """Google Trends から日本の金融カテゴリで急上昇しているクエリを取得。

    pytrends は非公式 API のため失敗することが多い。失敗時は空リストを返す。
    """
    try:
        from pytrends.request import TrendReq
    except ImportError:
        log.warning("pytrends not installed; skipping Google Trends")
        return []

    try:
        pytrends = TrendReq(hl="ja-JP", tz=540)
        # daily_trending は地域指定で日本の急上昇キーワード上位を返す
        df = pytrends.trending_searches(pn="japan")
        if df is None or df.empty:
            return []
        trends: list[Trend] = []
        finance_words = ("円", "ドル", "株", "FX", "ビットコイン", "暗号",
                         "投資", "日経", "金利", "為替")
        for i, kw in enumerate(df[0].tolist()[:20]):
            if not any(w in kw for w in finance_words):
                continue
            category = _guess_category(kw)
            trends.append(Trend(
                category=category,
                keyword=kw,
                headline=f"{kw} がGoogle急上昇ワード入り",
                source="Google Trends Japan",
                url=f"https://www.google.com/search?q={kw}",
                score=70 - i * 3,
            ))
        return trends
    except Exception as e:
        log.warning("Google Trends fetch failed: %s", e)
        return []


def _guess_category(keyword: str) -> str:
    """キーワード文字列からカテゴリを推定。"""
    kw = keyword.lower()
    if any(w in kw for w in ("ビットコイン", "イーサ", "暗号", "btc", "eth",
                              "仮想通貨")):
        return "crypto"
    if any(w in kw for w in ("ドル", "円", "ユーロ", "為替", "fx")):
        return "fx"
    return "stock"


def fetch_newsdata_io(api_key: str | None = None) -> list[Trend]:
    """newsdata.io の無料枠 (200req/日) から金融ニュースを取得。
    API キー未指定なら空。"""
    api_key = api_key or os.environ.get("NEWSDATA_API_KEY")
    if not api_key:
        return []

    url = "https://newsdata.io/api/1/news"
    params = {
        "apikey": api_key,
        "category": "business",
        "language": "en",
        "size": 10,
    }
    try:
        r = requests.get(url, params=params, timeout=15)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        log.warning("newsdata.io fetch failed: %s", e)
        return []

    trends: list[Trend] = []
    for i, art in enumerate(data.get("results", [])):
        title = art.get("title", "")
        cat = _guess_category_en(title)
        trends.append(Trend(
            category=cat,
            keyword=_extract_keyword(title, cat),
            headline=title,
            source=art.get("source_id", "newsdata.io"),
            url=art.get("link", ""),
            score=60 - i * 3,
        ))
    return trends


def _guess_category_en(headline: str) -> str:
    h = headline.lower()
    if any(w in h for w in ("bitcoin", "ethereum", "crypto", "btc", "eth",
                            "blockchain")):
        return "crypto"
    if any(w in h for w in ("dollar", "yen", "euro", "forex", "fx",
                            "currency", "exchange rate")):
        return "fx"
    return "stock"


# ----------------------------------------------------------------------
# 集約 & ランキング
# ----------------------------------------------------------------------

ALL_SOURCES = (
    fetch_coingecko_trending,
    fetch_yahoo_finance_rss,
    fetch_google_trends_jp,
    fetch_newsdata_io,
)


def scan(top_n: int = 10, seed: int | None = None) -> list[Trend]:
    """全ソースを横断して上位 top_n 件のトレンドを返す。

    環境変数 `FOCUS_CATEGORY` が `stock` / `fx` / `crypto` のいずれかに
    設定されているとそのカテゴリに集中(初期 30 日の専門家認識フェーズ用)。
    未設定なら従来通り stock/fx/crypto を 4:3:3 で均等配分。
    """
    if seed is not None:
        random.seed(seed)

    pool: list[Trend] = []
    for fn in ALL_SOURCES:
        try:
            pool.extend(fn())
        except Exception as e:
            log.warning("source %s raised: %s", fn.__name__, e)

    if not pool:
        log.error("no trends collected from any source")
        return []

    # 重複キーワードのマージ
    by_key: dict[tuple[str, str], Trend] = {}
    for t in pool:
        k = (t.category, t.keyword.lower())
        if k not in by_key or t.score > by_key[k].score:
            by_key[k] = t

    deduped = list(by_key.values())

    # 集中カテゴリモード
    focus = os.environ.get("FOCUS_CATEGORY", "").strip().lower()
    if focus in ("stock", "fx", "crypto"):
        log.info("FOCUS_CATEGORY mode: %s", focus)
        focused = [t for t in deduped if t.category == focus]
        focused.sort(key=lambda x: x.score, reverse=True)
        # フォーカスカテゴリが不足したら他カテゴリで補完するが優先度は下げる
        others = [t for t in deduped if t.category != focus]
        others.sort(key=lambda x: x.score * 0.5, reverse=True)
        result = focused + others
        return result[:top_n]

    # 通常モード: stock/fx/crypto = 4:3:3
    target_quota = {"stock": 4, "fx": 3, "crypto": 3}
    result: list[Trend] = []
    by_cat: dict[str, list[Trend]] = {"stock": [], "fx": [], "crypto": []}
    for t in deduped:
        if t.category in by_cat:
            by_cat[t.category].append(t)
    for cat, lst in by_cat.items():
        lst.sort(key=lambda x: x.score, reverse=True)
        result.extend(lst[: target_quota[cat]])

    if len(result) < top_n:
        remainder = sorted(
            (t for t in deduped if t not in result),
            key=lambda x: x.score, reverse=True,
        )
        result.extend(remainder[: top_n - len(result)])

    result.sort(key=lambda x: x.score, reverse=True)
    return result[:top_n]


def pick_one(seed: int | None = None) -> Trend | None:
    """単発のトレンドを 1 つ返す(GitHub Actions の 1 ジョブ用)."""
    top = scan(top_n=10, seed=seed)
    if not top:
        return None
    # 上位 10 件から重み付きランダム選択(score 比例)
    weights = [t.score for t in top]
    return random.choices(top, weights=weights, k=1)[0]


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    for t in scan():
        print(f"[{t.category}] {t.keyword} — {t.headline} ({t.source}, score={t.score})")
