"""Bronze → Silver pipeline for website pages.

Reads Markdown files from storage/bronze/website/,
sends each to Gemini for semantic chunking and knowledge extraction,
and writes structured JSON to storage/silver/website/.
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
BRONZE_DIR = ROOT_DIR / "storage" / "bronze" / "website"
SILVER_DIR = ROOT_DIR / "storage" / "silver" / "website"

SYSTEM_PROMPT = """\
你是一位資深電子鎖知識編輯。你會收到一頁由爬蟲擷取的網頁 Markdown，內容可能包含電子鎖品牌「鎖市」的營業資訊、產品介紹、安裝流程、常見問題等。

請執行以下任務：

## 1. 資訊萃取與過濾
- 提取有價值的資訊：營業資訊（地址、營業時間、電話、服務項目）、技術知識（電子鎖 QA、規格、安裝流程、故障排除）
- 主動忽略以下雜訊：導覽列殘留文字、圖片連結 / alt text、行銷口號、社群媒體連結、頁尾版權聲明、空白或無意義的格式殘留

## 2. 語意切分與重寫
將內容切分為多個獨立的知識點，每個知識點必須：
- 自帶完整主語（例如：「鎖市的營業時間為...」、「Chatlock AI-99 的安裝步驟...」，不能只寫「營業時間為...」）
- 使用客觀敘述，保留所有具體細節（數字、型號、步驟）
- 使用正式書面中文

## 3. Metadata 推斷
根據檔名和內容推斷以下欄位：
- brand：品牌名稱（Dormakaba / Chatlock / Kaadas / 3E / Philips / Milre / general）
- model：型號（如 AI-99、A90、AS701、小島F(T7)、TX，無法確定則填 general）
- category：分類，從以下選擇一個：setup / troubleshoot / knowledge / specification

## 4. 空頁處理
若網頁內容經過濾後無任何有價值的資訊（例如純導覽列或純圖片頁），請回傳空的 chunks 陣列。
"""

RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "chunks": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "content": {
                        "type": "string",
                        "description": "客觀重寫後的知識內容（必須自帶主語「鎖市」或產品名稱）",
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
            "description": "獨立知識點陣列。若網頁無有價值資訊，則回傳空陣列。",
        }
    },
    "required": ["chunks"],
}

log = logging.getLogger(__name__)


# ── helpers ──────────────────────────────────────────────────────────

def load_pipeline_config() -> dict:
    """Read [pipelines.website] from config.toml."""
    config_path = ROOT_DIR / "config.toml"
    with open(config_path, "rb") as f:
        config = tomllib.load(f)
    return config["pipelines"]["website"]


def process_one_file(llm_func: Callable, filepath: Path) -> list[dict]:
    """Send a single webpage Markdown to the LLM and return a list of Document dicts."""
    content = filepath.read_text(encoding="utf-8")
    user_prompt = f"檔名：{filepath.name}\n\n網頁內容：\n{content}"

    result = llm_func(user_prompt, SYSTEM_PROMPT, RESPONSE_SCHEMA)

    if not isinstance(result, dict) or "chunks" not in result:
        raise ValueError("LLM response is not an object with 'chunks'")

    chunks = result["chunks"]
    if not isinstance(chunks, list):
        raise ValueError("'chunks' is not an array")

    if len(chunks) == 0:
        return []

    final_documents = []
    for i, item in enumerate(chunks):
        for field in ("content", "metadata"):
            if field not in item:
                raise ValueError(f"Chunk {i}: missing '{field}'")

        doc = {
            "content": item["content"],
            **item["metadata"],
            "source_type": "website",
            "source": filepath.name,
            "chunk_index": i + 1,
        }
        final_documents.append(doc)

    return final_documents


# ── main ─────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Process bronze website pages → silver JSON"
    )
    parser.add_argument(
        "--file",
        type=str,
        help="Process a single file (filename only, relative to bronze/website/)",
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
        files = sorted(BRONZE_DIR.glob("*.md"))
        if not files:
            sys.exit(f"No .md files found in {BRONZE_DIR}")

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
                log.info("OK → %s (%d chunks, attempt %d)", out_path.name, len(result), attempt + 1)
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
        if (SILVER_DIR / f.replace(".md", ".json")).exists():
            all_failures.pop(f)

    if all_failures:
        failures_path.write_text(json.dumps(all_failures, ensure_ascii=False, indent=2), encoding="utf-8")
        log.warning("Failures logged to %s (%d files)", failures_path, len(all_failures))
    elif failures_path.exists():
        failures_path.unlink()

    log.info("Done. success=%d  skipped=%d  failed=%d", success, skipped, failed)


if __name__ == "__main__":
    main()
