"""Bronze → Silver pipeline for video transcripts.

Reads raw speech-recognition transcripts from storage/bronze/video/,
sends each to Gemini for correction / structuring, and writes
structured JSON to storage/silver/video/.
"""

import argparse
import json
import logging
import sys
import time
import tomllib
from pathlib import Path
from typing import Callable

MAX_RETRIES = 3
RETRY_BACKOFF = [2, 5, 10]  # seconds

# ── paths ────────────────────────────────────────────────────────────
ROOT_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT_DIR))

from llms import get_llm
BRONZE_DIR = ROOT_DIR / "storage" / "bronze" / "video"
SILVER_DIR = ROOT_DIR / "storage" / "silver" / "video"

SYSTEM_PROMPT = """\
你是一位資深電子鎖技術編輯。你會收到一段由語音辨識自動產生的影片逐字稿，內容關於電子鎖的安裝、維修、客服或產品知識。

請執行以下任務：

## 1. 語音辨識糾錯
常見錯誤對照表（請一併修正其他明顯的語音辨識錯誤）：
| 錯誤 | 正確 |
|------|------|
| 鞋舌 / 鞋匠 | 鎖舌 |
| 掌機賣 / 掌進麥 | 掌靜脈 |
| 收口 | 受口 |
| 連提鎖 | 連體鎖 |
| 密碼版 | 密碼面板 |
| 鎖匠 | 鎖箱 |
| 屍體 | 實體 |
| 卡順 | 卡榫 |
| 坑客人 | 坑（此處應刪除整句不相關口語） |

## 2. 去噪
- 移除口頭禪：然後、就是、對、好、那、嗯、齁、OK 等
- 移除重複句、假啟動、語句中斷後重說的片段
- 移除非內容段落（如「要錄喔？」「暫停」「等一下」等拍攝指令）
- 移除時間戳 [MM:SS]

## 3. 語意切分與重寫
將逐字稿切分為多個獨立的知識點，每個知識點必須：
- 自帶完整主語（例如：「Dormakaba 鎖舌卡住時，應...」，不能只寫「卡住時應...」）
- 包含該知識點的完整描述，保留所有技術細節
- 使用正式書面中文

## 4. Metadata 推斷
根據檔名和內容推斷以下欄位：
- brand：品牌名稱（Dormakaba / Chatlock / Kaadas / 3E / Philips / Milre / general）
- model：型號（如 AI-99、A90、AS701、小島F(T7)、TX，無法確定則填 general）
- category：分類，從以下選擇一個：setup / troubleshoot / knowledge / specification
"""

RESPONSE_SCHEMA = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "content": {
                "type": "string",
                "description": "結構化重寫後的獨立知識內容（必須包含品牌與型號等主語）",
            },
            "metadata": {
                "type": "object",
                "properties": {
                    "brand": {"type": "string"},
                    "model": {"type": "string"},
                    "category": {"type": "string"},
                },
                "required": ["brand", "model", "category"],
            },
        },
        "required": ["content", "metadata"],
    },
}

log = logging.getLogger(__name__)


# ── helpers ──────────────────────────────────────────────────────────

def load_pipeline_config() -> dict:
    """Read [pipelines.video] from config.toml."""
    config_path = ROOT_DIR / "config.toml"
    with open(config_path, "rb") as f:
        config = tomllib.load(f)
    return config["pipelines"]["video"]


def process_one_file(llm_func: Callable, filepath: Path) -> list[dict]:
    """Send a single transcript to the LLM and return a list of Document dicts."""
    transcript = filepath.read_text(encoding="utf-8")
    user_prompt = f"檔名：{filepath.name}\n\n逐字稿內容：\n{transcript}"

    chunks = llm_func(user_prompt, SYSTEM_PROMPT, RESPONSE_SCHEMA)

    if not isinstance(chunks, list) or len(chunks) == 0:
        raise ValueError("LLM response is not a non-empty array")

    final_documents = []
    for i, item in enumerate(chunks):
        for field in ("content", "metadata"):
            if field not in item:
                raise ValueError(f"Chunk {i}: missing '{field}'")

        doc = {
            "content": item["content"],
            **item["metadata"],
            "source_type": "video",
            "source": filepath.name,
            "chunk_index": i + 1,
        }
        final_documents.append(doc)

    return final_documents


# ── main ─────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Process bronze video transcripts → silver JSON"
    )
    parser.add_argument(
        "--file",
        type=str,
        help="Process a single file (filename only, relative to bronze/video/)",
    )
    parser.add_argument("--force", action="store_true", help="Overwrite existing silver files")
    parser.add_argument("--retry-failed", action="store_true", help="Only retry previously failed files")
    parser.add_argument("--verbose", action="store_true", help="Enable debug logging")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s: %(message)s",
    )

    SILVER_DIR.mkdir(parents=True, exist_ok=True)

    pipeline_cfg = load_pipeline_config()
    llm_func = get_llm(
        provider=pipeline_cfg["llm_provider"],
        model=pipeline_cfg["llm_model"],
        temperature=pipeline_cfg.get("temperature", 0.3),
    )

    # Failure log for tracking
    failures_path = SILVER_DIR / "_failures.json"
    prev_failures: dict = {}
    if failures_path.exists():
        prev_failures = json.loads(failures_path.read_text(encoding="utf-8"))

    # Determine which files to process
    if args.file:
        files = [BRONZE_DIR / args.file]
        if not files[0].exists():
            sys.exit(f"File not found: {files[0]}")
    elif args.retry_failed:
        files = [BRONZE_DIR / f for f in prev_failures if (BRONZE_DIR / f).exists()]
        if not files:
            sys.exit("No previously failed files to retry")
    else:
        files = sorted(BRONZE_DIR.glob("*.txt"))
        if not files:
            sys.exit(f"No .txt files found in {BRONZE_DIR}")

    log.info("Found %d file(s) to process", len(files))

    success = 0
    skipped = 0
    failed = 0
    current_failures: dict = {}

    for filepath in files:
        out_path = SILVER_DIR / f"{filepath.stem}.json"

        # Idempotency check
        if out_path.exists() and not args.force and not args.retry_failed:
            log.info("SKIP (already exists): %s", filepath.name)
            skipped += 1
            continue

        log.info("Processing: %s", filepath.name)

        # Retry loop
        last_error = None
        for attempt in range(MAX_RETRIES):
            try:
                result = process_one_file(llm_func, filepath)
                out_path.write_text(
                    json.dumps(result, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                log.info("OK → %s (attempt %d)", out_path.name, attempt + 1)
                success += 1
                prev_failures.pop(filepath.name, None)
                last_error = None
                break
            except (OSError, RuntimeError, ValueError, TimeoutError, ConnectionError) as e:
                last_error = str(e)
                if attempt < MAX_RETRIES - 1:
                    wait = RETRY_BACKOFF[attempt]
                    log.warning("RETRY %d/%d for %s (wait %ds): %s", attempt + 1, MAX_RETRIES, filepath.name, wait, e)
                    time.sleep(wait)

        if last_error:
            log.error("FAILED after %d attempts: %s — %s", MAX_RETRIES, filepath.name, last_error)
            current_failures[filepath.name] = last_error
            failed += 1

        # Rate-limit between files
        if filepath != files[-1]:
            time.sleep(1)

    # Update failure log
    all_failures = {**prev_failures, **current_failures}
    for f in list(all_failures):
        if (SILVER_DIR / f.replace(".txt", ".json")).exists():
            all_failures.pop(f)

    if all_failures:
        failures_path.write_text(json.dumps(all_failures, ensure_ascii=False, indent=2), encoding="utf-8")
        log.warning("Failures logged to %s (%d files)", failures_path, len(all_failures))
    elif failures_path.exists():
        failures_path.unlink()

    log.info("Done. success=%d  skipped=%d  failed=%d", success, skipped, failed)


if __name__ == "__main__":
    main()
