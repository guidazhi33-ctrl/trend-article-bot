"""最低限のスモークテスト。API キー無しで実行できる純ロジック部分のみ。"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.affiliate_inserter import insert
from src.trend_scanner import Trend


def test_affiliate_insertion_replaces_all_placeholders():
    md = (
        "# t\n[[AFFILIATE_INTRO]]\nビットコインの話\n"
        "[[AFFILIATE_BODY_1]]\nFXの話\n[[AFFILIATE_BODY_2]]\n"
        "## まとめ\n[[AFFILIATE_OUTRO]]\n"
    )
    out = insert(md)
    for ph in ("[[AFFILIATE_INTRO]]", "[[AFFILIATE_BODY_1]]",
               "[[AFFILIATE_BODY_2]]", "[[AFFILIATE_OUTRO]]"):
        assert ph not in out, f"placeholder {ph} not replaced"
    assert out.count("http") >= 4, "expected at least 4 affiliate URLs"


def test_trend_dataclass_roundtrip():
    t = Trend(category="crypto", keyword="BTC", headline="x", source="s")
    d = t.to_dict()
    assert d["category"] == "crypto"
    assert "detected_at" in d


if __name__ == "__main__":
    test_affiliate_insertion_replaces_all_placeholders()
    test_trend_dataclass_roundtrip()
    print("smoke OK")
