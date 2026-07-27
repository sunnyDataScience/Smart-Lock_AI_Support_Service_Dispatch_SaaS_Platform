"""把某個靶心上「由本管線建立的東西」刪乾淨，回到匯入前的狀態。

Plane 沒有批次刪除，也沒有寫入冪等，所以推錯靶心是會發生的事（本檔的存在原因：
2026-07-28 先把規格脊椎推進了活的交付看板 LOCK，業主決定改掛新專案，需要還原）。

**刪什麼由 id_map 決定，不做任何啟發式比對。** id_map 記的就是本管線建過的每一個
物件；不在裡面的一律不碰。這條規則讓「別人手開的卡會不會被誤刪」不需要靠判斷來
保證——它們從來不在 id_map 裡。唯一例外是 `adopted`（步驟 ⑥a 認領的既有人工卡）：
那些卡不是我們建的，只是被登記進來，所以**只退出登記、不刪卡**。

不刪 workspace 級的 work item type 與 initiative：它們跨專案共用，新靶心會沿用。
只把 type 從本專案解除關聯（--detach-types）。

用法：
    cd smartlock-docs/enterprise/規格統控整理
    PLANE_PROJECT_ID=<uuid> python3 _plane/rollback_target.py [--dry-run] [--detach-types]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from _plane.plane_client import Plane, PlaneError  # noqa: E402

DRY = "--dry-run" in sys.argv
DETACH_TYPES = "--detach-types" in sys.argv


def _sweep(label: str, items: list[tuple[str, str]], delete, state_bucket: dict | None,
           save) -> int:
    """items = [(顯示名, uuid)]。刪掉就從 state 移除並落盤，中斷可續跑。"""
    if not items:
        return 0
    print(f"\n=== {label}（{len(items)}）", flush=True)
    gone = 0
    for i, (key, uid) in enumerate(items, 1):
        if DRY:
            print(f"    [dry] {key}")
            continue
        try:
            delete(uid)
        except PlaneError as exc:
            if exc.status != 404:
                print(f"    ! {key}: {exc}", file=sys.stderr)
                continue
            # 404 視同已刪，但要印出來——若是「打錯端點／打錯 ID」也會回 404，
            # 靜默計入成功會產出一份帳面乾淨、實際沒刪到的回復報告（踩過）。
            print(f"    ~ {key}: 404，視為已不存在")
        if state_bucket is not None:
            state_bucket.pop(key, None)
        gone += 1
        if gone % 20 == 0 or i == len(items):
            print(f"    {gone}/{len(items)}", flush=True)
            save()
    save()
    return gone


def main() -> int:
    p = Plane()
    path = p.state_file()
    if not path.exists():
        print(f"找不到 {path} —— 這個靶心沒有本管線的紀錄，無需回復", file=sys.stderr)
        return 2
    state = json.loads(path.read_text(encoding="utf-8"))

    def save() -> None:
        if not DRY:
            path.write_text(json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                            encoding="utf-8")

    adopted = set(state.get("adopted") or [])
    work_items = {k: v["id"] for k, v in state.get("work_items", {}).items() if k not in adopted}

    print(f"靶心 {p.base} / {p.slug} / {p.project_id}")
    print(f"id_map {path.name}")
    print(f"待刪 work_items={len(work_items)} modules={len(state.get('modules') or {})} "
          f"milestones={len(state.get('milestones') or {})} "
          f"properties={len(state.get('properties') or {})}"
          + (f"（另有 {len(adopted)} 張認領卡只退出登記、不刪）" if adopted else ""))

    total = 0
    # 先卡後容器：卡還在時刪 module/milestone 只是解除歸屬，順序反了會留下孤兒關聯。
    total += _sweep("work items", sorted(work_items.items()), p.delete_work_item,
                    state.get("work_items"), save)
    total += _sweep("modules", sorted((state.get("modules") or {}).items()), p.delete_module,
                    state.get("modules"), save)
    total += _sweep("milestones", sorted((state.get("milestones") or {}).items()),
                    p.delete_milestone, state.get("milestones"), save)
    total += _sweep("自訂欄位", sorted((k, v["id"]) for k, v in
                                       (state.get("properties") or {}).items()),
                    p.delete_property, state.get("properties"), save)
    if DETACH_TYPES:
        # 解除關聯要 DELETE「關聯記錄」的 id，不是 type 的 id——所以先列出關聯、
        # 用 type.id 反查，只解除本管線建的那幾個 type，不動專案原有的關聯。
        ours = set((state.get("types") or {}).values())
        links = [(link["type"]["name"], link["id"]) for link in p.list_type_links()
                 if (link.get("type") or {}).get("id") in ours] if not DRY else []
        total += _sweep("解除 type 關聯", sorted(links), p.detach_type, None, save)
        state["types"] = {}
        save()

    for key in ("props_done", "relations_done", "links_done", "adopted"):
        if key in state:
            state[key] = [] if key != "adopted" else state[key]
    # 認領的卡沒被刪，但也不再由本管線登記，避免下次匯入誤以為已建。
    for key in list(adopted):
        state.get("work_items", {}).pop(key, None)
    state["adopted"] = []
    save()

    print(f"\n回復完成，共處理 {total} 個物件。{path.name} 已更新。")
    if not DETACH_TYPES:
        print("note: workspace 級的 work item type / initiative 保留（跨專案共用）。"
              "要從本專案解除 type 關聯請加 --detach-types。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
