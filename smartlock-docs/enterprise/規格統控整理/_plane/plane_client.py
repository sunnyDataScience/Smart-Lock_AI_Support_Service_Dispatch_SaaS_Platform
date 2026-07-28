"""Plane REST client — 只用 stdlib，避免給規格統控管線加依賴。

所有寫入都走 `/api/v1`（X-API-Key）。此 fork 的兩個反直覺點已封裝在方法裡：
  - 專案關聯 work item type 的欄位名是 `type_id`，不是 `work_item_type_id`
  - 設定自訂欄位值是 PUT 到單一 property，POST 到 collection 會 404
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

TIMEOUT = 30
ID_MAP_DIR = Path(__file__).resolve().parent / "id_map"
RETRY_STATUS = {429, 500, 502, 503, 504}

# 後端 API_KEY_RATE_LIMIT 預設 60/minute，按 API key 計（含 GET）。
# 留安全邊際跑 55/min，撞到 429 時再依 Retry-After 退避。
RATE_PER_MIN = int(os.environ.get("PLANE_CLIENT_RATE_PER_MIN", "55"))


class _Pacer:
    """Rolling-window token bucket，確保 60 秒內不超過 RATE_PER_MIN 次呼叫。"""

    def __init__(self, per_min: int):
        self.per_min = max(1, per_min)
        self.stamps: list[float] = []

    def wait(self) -> None:
        now = time.monotonic()
        self.stamps = [t for t in self.stamps if now - t < 60.0]
        if len(self.stamps) >= self.per_min:
            sleep_for = 60.0 - (now - self.stamps[0]) + 0.05
            if sleep_for > 0:
                time.sleep(sleep_for)
            now = time.monotonic()
            self.stamps = [t for t in self.stamps if now - t < 60.0]
        self.stamps.append(time.monotonic())


class PlaneError(RuntimeError):
    def __init__(self, status: int, body: str, url: str):
        super().__init__(f"HTTP {status} on {url}: {body[:400]}")
        self.status = status
        self.body = body


class Plane:
    """薄封裝。方法名對應 README §3 的原語，不做額外抽象。"""

    def __init__(self, base: str | None = None, key: str | None = None,
                 slug: str | None = None, project_id: str | None = None):
        self.base = (base or os.environ["PLANE_URL"]).rstrip("/")
        self.key = key or os.environ["PLANE_API_KEY"]
        self.slug = slug or os.environ.get("PLANE_WORKSPACE_SLUG") or os.environ["PLANE_WORKSPACE"]
        self.project_id = project_id or os.environ["PLANE_PROJECT_ID"]
        self.pacer = _Pacer(RATE_PER_MIN)

    def state_file(self) -> Path:
        """id_map 是 per-target 的。

        UUID 只在單一 workspace+project 內有意義，同一份四書卻可能推到多個實例
        （本機 docker / 遠端 ngrok / 未來的正式站）。共用一個 id_map.json 會讓
        check-then-create 在換靶時全部假命中——查得到 key、拿到的卻是別的實例的
        UUID，於是不建卡、後續 relation/link 全打到不存在的物件。檔名帶上靶心是
        最笨也最不會錯的隔離方式。
        """
        return ID_MAP_DIR / f"{self.slug}__{self.project_id}.json"

    # -- transport ---------------------------------------------------------

    def _call(self, method: str, path: str, body: dict | None = None, retries: int = 6):
        url = f"{self.base}{path}"
        data = json.dumps(body).encode() if body is not None else None
        for attempt in range(retries + 1):
            self.pacer.wait()
            req = urllib.request.Request(url, data=data, method=method)
            req.add_header("X-API-Key", self.key)
            if data:
                req.add_header("Content-Type", "application/json")
            try:
                with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                    raw = resp.read().decode()
                    return json.loads(raw) if raw else None
            except urllib.error.HTTPError as exc:
                raw = exc.read().decode()
                if exc.code in RETRY_STATUS and attempt < retries:
                    if exc.code == 429:
                        # 被限流＝本地窗口估算偏樂觀，清空窗口並依 Retry-After 等待
                        self.pacer.stamps = []
                        delay = float(exc.headers.get("Retry-After") or 0) or 15.0 * (attempt + 1)
                    else:
                        delay = 2 ** attempt
                    time.sleep(delay)
                    continue
                raise PlaneError(exc.code, raw, url) from exc
            except urllib.error.URLError:
                if attempt < retries:
                    time.sleep(2 ** attempt)
                    continue
                raise
        raise RuntimeError("unreachable")

    def _ws(self, suffix: str) -> str:
        return f"/api/v1/workspaces/{self.slug}{suffix}"

    def _proj(self, suffix: str) -> str:
        return f"/api/v1/workspaces/{self.slug}/projects/{self.project_id}{suffix}"

    def paged(self, path: str) -> list[dict]:
        """走完所有分頁，回傳 results 串接。"""
        out: list[dict] = []
        cursor = None
        while True:
            url = path + (("&" if "?" in path else "?") + f"cursor={urllib.parse.quote(cursor)}" if cursor else "")
            page = self._call("GET", url)
            if page is None:
                break
            if isinstance(page, list):
                return page
            out.extend(page.get("results", []))
            if not page.get("next_page_results"):
                break
            cursor = page.get("next_cursor")
        return out

    # -- project -----------------------------------------------------------

    def list_projects(self) -> list[dict]:
        return self.paged(self._ws("/projects/"))

    def create_project(self, name: str, identifier: str, **fields) -> dict:
        return self._call("POST", self._ws("/projects/"),
                          {"name": name, "identifier": identifier, **fields})

    def get_project(self) -> dict:
        return self._call("GET", f"/api/v1/workspaces/{self.slug}/projects/{self.project_id}/")

    def update_project(self, **fields) -> dict:
        return self._call("PATCH", f"/api/v1/workspaces/{self.slug}/projects/{self.project_id}/",
                          fields)

    # -- work item types ---------------------------------------------------

    def list_types(self) -> list[dict]:
        return self.paged(self._ws("/work-item-types/"))

    def create_type(self, name: str, description: str = "", is_epic: bool = False) -> dict:
        return self._call("POST", self._ws("/work-item-types/"),
                          {"name": name, "description": description, "is_epic": is_epic})

    def attach_type(self, type_id: str) -> dict:
        # 此 fork 的欄位名是 type_id（不是 work_item_type_id）
        return self._call("POST", self._proj("/work-item-types/"), {"type_id": type_id})

    def update_type(self, type_id: str, **fields) -> dict:
        """改型別的 level / is_epic。

        階層語意靠這兩個欄位表達：Epic = level 0 + is_epic、Feature = level 1、
        Story 與 Quality requirement 同為 level 2。序列化器把 level 與 is_epic
        都列在可寫欄位（read_only 只有 id/workspace/時間戳），所以 PATCH 得動。
        """
        return self._call("PATCH", self._ws(f"/work-item-types/{type_id}/"), fields)

    # -- custom properties -------------------------------------------------

    def list_properties(self) -> list[dict]:
        return self.paged(self._proj("/work-item-properties/"))

    def create_property(self, name: str, kind: str, options: list[dict] | None = None,
                        description: str = "") -> dict:
        body: dict = {"name": name, "kind": kind, "description": description}
        if options:
            body["options"] = options
        return self._call("POST", self._proj("/work-item-properties/"), body)

    def set_property_value(self, issue_id: str, property_id: str, value):
        # PUT 到單一 property；POST 到 collection 會 404
        return self._call("PUT", self._proj(f"/work-items/{issue_id}/properties/{property_id}/"),
                          {"value": value})

    # -- containers --------------------------------------------------------

    def list_modules(self) -> list[dict]:
        return self.paged(self._proj("/modules/"))

    def create_module(self, name: str, description: str = "") -> dict:
        return self._call("POST", self._proj("/modules/"), {"name": name, "description": description})

    def add_module_issues(self, module_id: str, issue_ids: list[str]) -> dict:
        return self._call("POST", self._proj(f"/modules/{module_id}/module-issues/"), {"issues": issue_ids})

    def list_milestones(self) -> list[dict]:
        return self.paged(self._proj("/milestones/"))

    def create_milestone(self, name: str, description: str = "") -> dict:
        return self._call("POST", self._proj("/milestones/"), {"name": name, "description": description})

    def list_initiatives(self) -> list[dict]:
        return self.paged(self._ws("/initiatives/"))

    def create_initiative(self, name: str, description: str = "") -> dict:
        return self._call("POST", self._ws("/initiatives/"), {"name": name, "description": description})

    # -- work items --------------------------------------------------------

    def list_work_items(self) -> list[dict]:
        return self.paged(self._proj("/work-items/"))

    def create_work_item(self, **fields) -> dict:
        return self._call("POST", self._proj("/work-items/"), fields)

    def update_work_item(self, issue_id: str, **fields) -> dict:
        return self._call("PATCH", self._proj(f"/work-items/{issue_id}/"), fields)

    def add_relation(self, issue_id: str, relation_type: str, targets: list[str]) -> dict:
        return self._call("POST", self._proj(f"/work-items/{issue_id}/relations/"),
                          {"relation_type": relation_type, "issues": targets})

    # -- testing domain ----------------------------------------------------

    def list_folders(self) -> list[dict]:
        return self.paged(self._proj("/testing/folders/"))

    def create_folder(self, name: str, parent_id: str | None = None) -> dict:
        body: dict = {"name": name}
        if parent_id:
            body["parent_id"] = parent_id
        return self._call("POST", self._proj("/testing/folders/"), body)

    def list_test_cases(self) -> list[dict]:
        return self.paged(self._proj("/testing/test-cases/"))

    def create_test_case(self, **fields) -> dict:
        return self._call("POST", self._proj("/testing/test-cases/"), fields)

    def link_case_to_work_item(self, case_id: str, issue_id: str) -> dict:
        return self._call("POST", self._proj(f"/testing/test-cases/{case_id}/work-items/"),
                          {"issue_id": issue_id})

    def create_test_run(self, name: str, case_ids: list[str], **extra) -> dict:
        return self._call("POST", self._proj("/testing/test-runs/"),
                          {"name": name, "test_case_ids": case_ids, **extra})

    def list_test_runs(self) -> list[dict]:
        return self.paged(self._proj("/testing/test-runs/"))

    # -- 回復 ---------------------------------------------------------------
    # 對映 README §6 的「id_map 是我們建了什麼的完整紀錄」——回復就是倒著刪它記的東西，
    # 不需要第二套「哪些是我建的」判斷邏輯。

    def delete_work_item(self, issue_id: str) -> None:
        self._call("DELETE", self._proj(f"/work-items/{issue_id}/"))

    def delete_module(self, module_id: str) -> None:
        self._call("DELETE", self._proj(f"/modules/{module_id}/"))

    def delete_milestone(self, milestone_id: str) -> None:
        self._call("DELETE", self._proj(f"/milestones/{milestone_id}/"))

    def delete_property(self, property_id: str) -> None:
        self._call("DELETE", self._proj(f"/work-item-properties/{property_id}/"))

    def list_type_links(self) -> list[dict]:
        """專案↔type 的**關聯記錄**（不是 type 本身）。

        每筆有自己的 `id`，另以 `type.id` 指回 workspace 級的 type。解除關聯要 DELETE
        這個 `id`；拿 `type.id` 去打會 404（2026-07-28 踩過：rollback 把 404 當成
        「已經不在」，於是 5 次無效呼叫全被算成成功，帳面清乾淨了、關聯其實還在）。
        """
        return self.paged(self._proj("/work-item-types/"))

    def detach_type(self, link_id: str) -> None:
        self._call("DELETE", self._proj(f"/work-item-types/{link_id}/"))

    def requirement_coverage(self) -> dict:
        return self._call("GET", self._proj("/testing/requirement-coverage/"))

    def quality_overview(self) -> dict:
        return self._call("GET", self._proj("/testing/overview/"))


def doc(text: str) -> dict:
    """Web Testing UI 的渲染 helper 只認 {"text": ...}（library-view.tsx:18）。"""
    return {"text": (text or "").strip()}
