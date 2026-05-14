"""
cost_guard.py — API コストを日次/月次で追跡し、上限超過時に処理を停止する。

GitHub Actions 内では state は `cost-state` ブランチに JSON で保存される。
本モジュールは以下を担う:
  - 各 API 呼び出しの推定コスト計算
  - 日次/月次累積コストの読み書き
  - 上限到達時の CostLimitExceeded 例外送出

環境変数:
  - DAILY_COST_LIMIT_USD  (default: 5.0)   約 750 円/日 → 月 2.2万円
  - MONTHLY_COST_LIMIT_USD (default: 100.0) 約 1.5 万円 → 安全側

価格は 2026 年 5 月時点の公開料金(USD/1Mトークン)を埋め込み。
変動するので requirements.txt 更新時に見直すこと。
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from pathlib import Path

log = logging.getLogger(__name__)

# 価格表(USD per 1M tokens / USD per image)— 2026年5月時点
_PRICING = {
    # Anthropic Claude
    "claude-sonnet-4-6": {"input": 3.00, "output": 15.00},  # USD/1M
    # OpenAI DALL-E 3 standard 1792x1024
    "dall-e-3-standard-1792": 0.080,  # USD/image
}

JST = timezone(timedelta(hours=9))
STATE_DIR = Path(__file__).resolve().parent.parent / "state"
STATE_FILE = STATE_DIR / "cost.json"


class CostLimitExceeded(RuntimeError):
    """日次/月次コスト上限を超えた時に投げる。"""


@dataclass
class CostState:
    daily: dict[str, float]   # "YYYY-MM-DD" -> USD
    monthly: dict[str, float] # "YYYY-MM"    -> USD


# ----------------------------------------------------------------------
# state I/O
# ----------------------------------------------------------------------

def _load() -> CostState:
    if not STATE_FILE.exists():
        return CostState(daily={}, monthly={})
    try:
        data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        return CostState(daily=data.get("daily", {}),
                         monthly=data.get("monthly", {}))
    except Exception:
        return CostState(daily={}, monthly={})


def _save(state: CostState) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(
        json.dumps({"daily": state.daily, "monthly": state.monthly},
                   ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _today_key() -> str:
    return datetime.now(JST).strftime("%Y-%m-%d")


def _month_key() -> str:
    return datetime.now(JST).strftime("%Y-%m")


# ----------------------------------------------------------------------
# コスト計算
# ----------------------------------------------------------------------

def claude_cost(input_tokens: int, output_tokens: int,
                model: str = "claude-sonnet-4-6") -> float:
    p = _PRICING.get(model)
    if not p:
        return 0.0
    return (input_tokens * p["input"] + output_tokens * p["output"]) / 1_000_000


def dalle_cost(images: int = 1, model: str = "dall-e-3-standard-1792") -> float:
    return images * _PRICING.get(model, 0.0)


# ----------------------------------------------------------------------
# ガード(呼び出し前後で挟む)
# ----------------------------------------------------------------------

def check_pre_run() -> None:
    """生成パイプライン開始前に呼ぶ。既に上限超なら CostLimitExceeded."""
    state = _load()
    today = state.daily.get(_today_key(), 0.0)
    month = state.monthly.get(_month_key(), 0.0)

    daily_limit = float(os.environ.get("DAILY_COST_LIMIT_USD", "5.0"))
    monthly_limit = float(os.environ.get("MONTHLY_COST_LIMIT_USD", "100.0"))

    log.info("cost state: daily=$%.3f / $%.2f, monthly=$%.3f / $%.2f",
             today, daily_limit, month, monthly_limit)

    if today >= daily_limit:
        raise CostLimitExceeded(
            f"daily cost ${today:.3f} already at limit ${daily_limit:.2f}; "
            f"skipping run. Adjust DAILY_COST_LIMIT_USD if intentional."
        )
    if month >= monthly_limit:
        raise CostLimitExceeded(
            f"monthly cost ${month:.3f} already at limit ${monthly_limit:.2f}; "
            f"skipping run."
        )


def record(usd: float) -> None:
    """1 回の API 呼び出しの USD コストを記録。"""
    if usd <= 0:
        return
    state = _load()
    state.daily[_today_key()] = state.daily.get(_today_key(), 0.0) + usd
    state.monthly[_month_key()] = state.monthly.get(_month_key(), 0.0) + usd
    _save(state)


def snapshot() -> tuple[float, float]:
    """(今日, 今月)の累積 USD を返す(GitHub Actions の Summary 用)."""
    state = _load()
    return (state.daily.get(_today_key(), 0.0),
            state.monthly.get(_month_key(), 0.0))


def reset_stale(days_to_keep: int = 95) -> None:
    """古いエントリを掃除(state ファイル肥大化防止)."""
    state = _load()
    cutoff_d = (datetime.now(JST) - timedelta(days=days_to_keep)).strftime("%Y-%m-%d")
    cutoff_m = (datetime.now(JST) - timedelta(days=days_to_keep)).strftime("%Y-%m")
    state.daily = {k: v for k, v in state.daily.items() if k >= cutoff_d}
    state.monthly = {k: v for k, v in state.monthly.items() if k >= cutoff_m}
    _save(state)
