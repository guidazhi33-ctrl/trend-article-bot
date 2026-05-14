"""GitHub Actions の issue_comment イベントから呼ばれるエントリポイント。"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.tweet_on_publish import main


if __name__ == "__main__":
    sys.exit(main())
