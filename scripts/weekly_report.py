"""
weekly_report.py — 週次の運用レポート Issue を発行する。

毎週日曜 22:00 JST に GitHub Actions から呼ばれる。

集計内容:
  - 今週ドラフトされた本数(tier 別)
  - 公開済み記事(Issue がクローズされたもの)の本数と成約率
  - 今週の API コスト総額(USD)
  - 月初からの累積コスト
  - Claude による「来週の改善提案」(プロンプトで生成)

GitHub Issue の検索 API で過去 7 日の `auto-draft` Issue を取得して集計。
"""

from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from github import Auth, Github
from anthropic import Anthropic

from src import cost_guard

log = logging.getLogger(__name__)
JST = timezone(timedelta(hours=9))


def _gh() -> Github:
    return Github(auth=Auth.Token(os.environ["GITHUB_TOKEN"]))


def _repo():
    return _gh().get_repo(os.environ["GITHUB_REPOSITORY"])


def _claude() -> Anthropic:
    return Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])


def _collect_stats() -> dict:
    """過去 7 日の auto-draft Issue を集計。"""
    repo = _repo()
    since = datetime.now(timezone.utc) - timedelta(days=7)

    by_tier: dict[str, int] = {"free": 0, "entry": 0, "premium": 0}
    by_cat: dict[str, int] = {"stock": 0, "fx": 0, "crypto": 0}
    closed_count = 0
    open_count = 0

    issues = repo.get_issues(
        state="all", labels=["auto-draft"], since=since,
    )
    for issue in issues:
        if issue.pull_request:
            continue
        labels = {l.name for l in issue.labels}
        for t in by_tier:
            if f"tier:{t}" in labels:
                by_tier[t] += 1
        for c in by_cat:
            if f"cat:{c}" in labels:
                by_cat[c] += 1
        if issue.state == "closed":
            closed_count += 1
        else:
            open_count += 1

    return {
        "by_tier": by_tier,
        "by_cat": by_cat,
        "closed": closed_count,
        "open": open_count,
        "total": closed_count + open_count,
    }


def _suggestion_prompt(stats: dict, daily_usd: float, monthly_usd: float) -> str:
    return f"""あなたは note + X のフォロワー獲得運用を改善するコンサルタントです。
以下の 1 週間の実績を見て、**来週試すべき改善案 3 つ** を簡潔に提示してください。

# 今週の実績
- ドラフト総数: {stats['total']}
- 公開済(close): {stats['closed']}
- 未公開(open):  {stats['open']}
- tier 内訳:    {stats['by_tier']}
- カテゴリ内訳: {stats['by_cat']}
- API コスト:   本日累計 ${daily_usd:.2f} / 月累計 ${monthly_usd:.2f}

# 出力フォーマット
1. **{{改善案 1 の見出し}}**
   - なぜ: {{理由 1 行}}
   - どう: {{具体的アクション 1 行}}

2. ... (同じ形式で 3 つ)

簡潔に。各案 3 行以内。
"""


def _build_issue_body(stats: dict, daily_usd: float, monthly_usd: float,
                      suggestion: str) -> str:
    week_start = (datetime.now(JST) - timedelta(days=7)).strftime("%Y-%m-%d")
    week_end = datetime.now(JST).strftime("%Y-%m-%d")
    return f"""## 📊 週次レポート ({week_start} 〜 {week_end})

### 📈 ドラフト実績
| 指標 | 値 |
|---|---:|
| 総ドラフト数 | {stats['total']} |
| 公開済(Issue クローズ済) | {stats['closed']} |
| 未公開(Issue オープン中) | {stats['open']} |
| 公開率 | {stats['closed'] / max(stats['total'], 1) * 100:.1f} % |

### 💎 tier 別
| Tier | 本数 |
|---|---:|
| 無料 (free) | {stats['by_tier']['free']} |
| ¥100 (entry) | {stats['by_tier']['entry']} |
| ¥500 (premium) | {stats['by_tier']['premium']} |

### 📂 カテゴリ別
| Category | 本数 |
|---|---:|
| 株式 | {stats['by_cat']['stock']} |
| FX | {stats['by_cat']['fx']} |
| 暗号資産 | {stats['by_cat']['crypto']} |

### 💰 API コスト
- 今日: ${daily_usd:.3f}
- 今月: ${monthly_usd:.3f}
- 想定月額(現行ペース×4.3): ${(daily_usd * 30):.2f}

---

### 🎯 来週の改善提案(AI 生成)

{suggestion}

---

### 📝 手動で記入してほしい指標
| 指標 | 今週の値 | 先週の値 | 増減 |
|---|---:|---:|---:|
| note フォロワー数 |  |  |  |
| X フォロワー数 |  |  |  |
| 記事平均スキ数 |  |  |  |
| 記事平均 PV |  |  |  |
| ツイート平均インプ |  |  |  |
| アフィリエイト成約数 |  |  |  |

→ 上記を埋めて運用に反映してください。 次週同曜日に新しいレポートが届きます。

---
🤖 このIssueは `weekly-report.yml` workflow によって自動生成されました。
"""


def main() -> int:
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")

    stats = _collect_stats()
    daily_usd, monthly_usd = cost_guard.snapshot()

    suggestion = "(AI 提案の生成に失敗しました)"
    try:
        client = _claude()
        resp = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1500,
            system="あなたは note/X のフォロワー獲得コンサルタントです。",
            messages=[{"role": "user",
                       "content": _suggestion_prompt(stats, daily_usd, monthly_usd)}],
        )
        suggestion = "".join(
            b.text for b in resp.content if hasattr(b, "text")
        ).strip()
    except Exception as e:
        log.warning("suggestion generation failed: %s", e)

    body = _build_issue_body(stats, daily_usd, monthly_usd, suggestion)
    repo = _repo()
    week_end = datetime.now(JST).strftime("%Y-%m-%d")
    issue = repo.create_issue(
        title=f"📊 週次レポート ({week_end})",
        body=body,
        labels=["weekly-report"],
    )
    log.info("weekly report issue: %s", issue.html_url)
    return 0


if __name__ == "__main__":
    sys.exit(main())
