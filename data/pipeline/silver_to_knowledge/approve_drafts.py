"""審核並合併知識草稿到 agent 知識庫。

驗證 data/storage/knowledge_drafts/ 中的草稿檔案，
顯示差異摘要，需明確指定 --confirm 旗標才執行合併。

用法：
    cd data
    python pipeline/silver_to_knowledge/approve_drafts.py --dry-run --verbose
    python pipeline/silver_to_knowledge/approve_drafts.py --type fault_trees --confirm
    python pipeline/silver_to_knowledge/approve_drafts.py --confirm --verbose
"""

import argparse
import json
import re
import shutil
import sys
import time
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT_DIR))

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib  # type: ignore[no-redef]

from pipeline.silver_to_knowledge._loaders import (
    DRAFTS_DIR,
    KNOWLEDGE_DIR,
    load_symptoms_toml,
    load_fault_trees,
)

SYMPTOMS_TOML = KNOWLEDGE_DIR / "taxonomy" / "symptoms.toml"
FAULT_TREES_DIR = KNOWLEDGE_DIR / "knowledge" / "fault_trees"

# 症狀草稿必要欄位
_SYMPTOM_REQUIRED = {"proposed_id", "label", "aliases", "component", "severity", "category"}
# Fault tree 草稿必要欄位
_FT_REQUIRED = {"id", "title", "required_symptoms", "failure_modes", "verification_chain", "corrective_actions"}


# ── 驗證 ──

def validate_symptom_drafts() -> tuple[list[dict], list[dict], list[str]]:
    """驗證症狀草稿，回傳 (有效新症狀, 有效 alias enrichments, 錯誤清單)。"""
    draft_path = DRAFTS_DIR / "symptoms" / "new_symptoms_draft.json"
    if not draft_path.exists():
        return [], [], ["找不到症狀草稿: " + str(draft_path)]

    data = json.loads(draft_path.read_text(encoding="utf-8"))
    existing_symptoms, _ = load_symptoms_toml()
    existing_ids = set(existing_symptoms.keys())
    errors = []

    # 驗證新症狀
    valid_new = []
    for s in data.get("new_symptoms", []):
        missing = _SYMPTOM_REQUIRED - set(s.keys())
        if missing:
            errors.append(f"新症狀 {s.get('proposed_id', '?')} 缺少欄位: {missing}")
            continue
        if s["proposed_id"] in existing_ids:
            errors.append(f"新症狀 {s['proposed_id']} 已存在於 symptoms.toml")
            continue
        valid_new.append(s)

    # 驗證 alias enrichments
    valid_enrich = []
    for e in data.get("alias_enrichments", []):
        sid = e.get("existing_symptom_id", "")
        if sid not in existing_ids:
            errors.append(f"Alias enrichment 目標 {sid} 不存在於 symptoms.toml")
            continue
        if not e.get("new_aliases"):
            errors.append(f"Alias enrichment {sid} 缺少 new_aliases")
            continue
        valid_enrich.append(e)

    return valid_new, valid_enrich, errors


def validate_fault_tree_drafts() -> tuple[list[tuple[Path, dict, str]], list[str]]:
    """驗證 fault tree 草稿。

    回傳 ([(path, data, type)], errors)，type 為 "draft" 或 "enriched"。
    """
    ft_dir = DRAFTS_DIR / "fault_trees"
    if not ft_dir.exists():
        return [], ["找不到 fault tree 草稿目錄: " + str(ft_dir)]

    existing_trees = {ft["id"]: ft for ft in load_fault_trees()}
    errors = []
    valid = []

    for f in sorted(ft_dir.glob("*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            errors.append(f"{f.name} JSON 解析失敗: {e}")
            continue

        if f.name.endswith("_enriched.json"):
            ft_type = "enriched"
            base_id = data.get("id", "")
            if base_id not in existing_trees:
                errors.append(f"{f.name} 的 base tree {base_id} 不存在於現有知識庫")
                continue
        elif f.name.endswith("_draft.json"):
            ft_type = "draft"
            missing = _FT_REQUIRED - set(data.keys())
            if missing:
                errors.append(f"{f.name} 缺少必要欄位: {missing}")
                continue
        else:
            continue

        valid.append((f, data, ft_type))

    return valid, errors


# ── 差異顯示 ──

def show_symptom_diff(new_symptoms: list[dict], enrichments: list[dict]):
    """列印症狀草稿差異摘要。"""
    if new_symptoms:
        print(f"\n  === 新增症狀 ({len(new_symptoms)} 筆) ===")
        for s in new_symptoms:
            aliases_str = ", ".join(s.get("aliases", [])[:3])
            print(f"  [NEW] {s['proposed_id']}: {s['label']} "
                  f"(severity={s['severity']}, component={s['component']}) "
                  f"aliases: [{aliases_str}...]")

    if enrichments:
        print(f"\n  === Alias 擴充 ({len(enrichments)} 筆) ===")
        for e in enrichments:
            new_aliases = ", ".join(e.get("new_aliases", []))
            print(f"  [ALIAS] {e['existing_symptom_id']} += [{new_aliases}]")


def show_fault_tree_diff(valid_trees: list[tuple[Path, dict, str]]):
    """列印 fault tree 草稿差異摘要。"""
    drafts = [(p, d) for p, d, t in valid_trees if t == "draft"]
    enriched = [(p, d) for p, d, t in valid_trees if t == "enriched"]

    if drafts:
        print(f"\n  === 新增 Fault Tree ({len(drafts)} 棵) ===")
        for _, d in drafts:
            fm_count = len(d.get("failure_modes", []))
            vc_count = len(d.get("verification_chain", []))
            print(f"  [NEW TREE] {d['id']}: {d.get('title', '?')} "
                  f"({fm_count} failure_modes, {vc_count} verification_steps)")

    if enriched:
        print(f"\n  === Fault Tree 擴充 ({len(enriched)} 棵) ===")
        for _, d in enriched:
            # 計算新增項目
            new_vc = len(d.get("new_verification_steps", d.get("verification_chain", [])))
            new_dh = len(d.get("new_defect_hypotheses", []))
            print(f"  [ENRICH] {d['id']}: +{new_vc} verification steps, +{new_dh} defect hypotheses")


# ── 合併 ──

def _backup(path: Path):
    """建立備份 (.bak.{timestamp})。"""
    if path.exists():
        bak = path.with_suffix(f"{path.suffix}.bak.{int(time.time())}")
        shutil.copy2(path, bak)
        print(f"  [備份] {bak.name}")


def merge_symptoms(new_symptoms: list[dict], enrichments: list[dict]):
    """合併症狀草稿到 symptoms.toml。"""
    if not new_symptoms and not enrichments:
        return

    _backup(SYMPTOMS_TOML)
    content = SYMPTOMS_TOML.read_text(encoding="utf-8")

    # 追加新症狀到檔案末尾
    if new_symptoms:
        lines = ["\n"]
        for s in new_symptoms:
            lines.append(f"\n[symptoms.{s['proposed_id']}]")
            lines.append(f'label     = "{s["label"]}"')
            aliases_str = json.dumps(s["aliases"], ensure_ascii=False)
            # 轉為 TOML 陣列格式
            aliases_toml = aliases_str.replace('"', '"')
            lines.append(f"aliases   = {aliases_toml}")
            lines.append(f'component = "{s["component"]}"')
            lines.append(f'severity  = {s["severity"]}')
            lines.append(f'category  = "{s["category"]}"')
        content += "\n".join(lines) + "\n"

    # Alias enrichment：找到對應 section 的 aliases 行，追加新值
    for e in enrichments:
        sid = e["existing_symptom_id"]
        new_aliases = e["new_aliases"]
        # 找到 [symptoms.{sid}] section 的 aliases 行
        pattern = rf'(\[symptoms\.{re.escape(sid)}\].*?aliases\s*=\s*\[)([^\]]*?)(\])'
        match = re.search(pattern, content, re.DOTALL)
        if match:
            existing_part = match.group(2).rstrip().rstrip(",")
            new_part = ", ".join(f'"{a}"' for a in new_aliases)
            if existing_part.strip():
                replacement = f"{match.group(1)}{existing_part},\n    {new_part},\n{match.group(3)}"
            else:
                replacement = f"{match.group(1)}{new_part}{match.group(3)}"
            content = content[:match.start()] + replacement + content[match.end():]

    SYMPTOMS_TOML.write_text(content, encoding="utf-8")
    print(f"  [寫入] {SYMPTOMS_TOML}")


def merge_fault_trees(valid_trees: list[tuple[Path, dict, str]]):
    """合併 fault tree 草稿到知識庫。"""
    for src_path, data, ft_type in valid_trees:
        ft_id = data.get("id", src_path.stem.split("_")[0])

        if ft_type == "draft":
            # 新 tree：去掉 _draft 後綴，設定正式版本
            data["version"] = "1.0"
            data["updated_by"] = "silver_pipeline_approved"
            target = FAULT_TREES_DIR / f"{ft_id}.json"
            _backup(target)
            target.write_text(
                json.dumps(data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            print(f"  [寫入] {target.name} (新 fault tree)")

        elif ft_type == "enriched":
            # 擴充既有 tree：deep merge
            target = FAULT_TREES_DIR / f"{ft_id}.json"
            if not target.exists():
                print(f"  [跳過] {ft_id} 目標檔案不存在")
                continue

            _backup(target)
            existing = json.loads(target.read_text(encoding="utf-8"))

            # 合併 verification_chain（避免 order 重複）
            existing_orders = {v.get("order") for v in existing.get("verification_chain", [])}
            for step in data.get("new_verification_steps", data.get("verification_chain", [])):
                if step.get("order") not in existing_orders:
                    existing.setdefault("verification_chain", []).append(step)

            # 合併 corrective_actions（填空 + 擴展 dispatch_criteria）
            new_ca = data.get("new_corrective_actions", data.get("corrective_actions", {}))
            existing_ca = existing.setdefault("corrective_actions", {})
            for key in ("immediate_remote", "long_term_remote", "if_remote_fails"):
                if not existing_ca.get(key) and new_ca.get(key):
                    existing_ca[key] = new_ca[key]
            if new_ca.get("dispatch_criteria"):
                existing_list = existing_ca.setdefault("dispatch_criteria", [])
                for item in new_ca["dispatch_criteria"]:
                    if item not in existing_list:
                        existing_list.append(item)

            # 合併 defect_hypotheses
            for new_dh in data.get("new_defect_hypotheses", []):
                fm_id = new_dh.get("fm_id")
                for fm in existing.get("failure_modes", []):
                    if fm.get("fm_id") == fm_id:
                        existing_defects = [d.get("defect") for d in fm.get("defect_hypotheses", [])]
                        if new_dh.get("defect") not in existing_defects:
                            fm.setdefault("defect_hypotheses", []).append(new_dh)
                        break

            # Version bump
            old_ver = existing.get("version", "1.0")
            try:
                major, minor = old_ver.split(".")
                existing["version"] = f"{major}.{int(minor) + 1}"
            except (ValueError, AttributeError):
                existing["version"] = f"{old_ver}.1"
            existing["updated_by"] = "silver_pipeline_enriched"

            target.write_text(
                json.dumps(existing, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            print(f"  [寫入] {target.name} (enriched → v{existing['version']})")


# ── 主流程 ──

def main():
    parser = argparse.ArgumentParser(description="審核並合併知識草稿到 agent 知識庫")
    parser.add_argument("--type", choices=["symptoms", "fault_trees", "all"], default="all",
                        help="要處理的草稿類型")
    parser.add_argument("--dry-run", action="store_true", help="僅預覽，不寫入")
    parser.add_argument("--confirm", action="store_true", help="確認執行合併（必須明確指定）")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    all_errors = []
    has_changes = False

    # ── 症狀 ──
    if args.type in ("symptoms", "all"):
        print("\n[審核] 症狀草稿...")
        new_symptoms, enrichments, s_errors = validate_symptom_drafts()
        all_errors.extend(s_errors)

        if s_errors:
            for e in s_errors:
                print(f"  [錯誤] {e}")

        if new_symptoms or enrichments:
            has_changes = True
            show_symptom_diff(new_symptoms, enrichments)

            if not args.dry_run and args.confirm:
                merge_symptoms(new_symptoms, enrichments)
        else:
            print("  沒有有效的症狀草稿")

    # ── Fault Trees ──
    if args.type in ("fault_trees", "all"):
        print("\n[審核] Fault tree 草稿...")
        valid_trees, ft_errors = validate_fault_tree_drafts()
        all_errors.extend(ft_errors)

        if ft_errors:
            for e in ft_errors:
                print(f"  [錯誤] {e}")

        if valid_trees:
            has_changes = True
            show_fault_tree_diff(valid_trees)

            if not args.dry_run and args.confirm:
                merge_fault_trees(valid_trees)
        else:
            print("  沒有有效的 fault tree 草稿")

    # ── 摘要 ──
    print("\n" + "=" * 50)
    if args.dry_run:
        print("[預覽模式] 以上為草稿內容預覽，未執行任何寫入")
    elif not args.confirm and has_changes:
        print("[未確認] 請加上 --confirm 旗標以執行合併")
        print(f"  範例: python {Path(__file__).name} --confirm")
    elif args.confirm and has_changes:
        print("[完成] 草稿已合併到 agent 知識庫")
    else:
        print("[無變更] 沒有找到有效草稿")

    if all_errors:
        print(f"\n共 {len(all_errors)} 個驗證錯誤（已跳過對應草稿）")


if __name__ == "__main__":
    main()
