"""GitHub Actions から呼ばれる news_translator のエントリポイント。"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.news_translator import run


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")
    sent = run()
    sys.exit(0 if sent >= 0 else 1)
