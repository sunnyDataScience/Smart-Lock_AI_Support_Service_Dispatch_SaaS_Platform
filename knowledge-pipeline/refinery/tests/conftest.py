"""refinery 測試共用設定 — package=false member 靠 sys.path 解析(比照 rag/tests)。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
