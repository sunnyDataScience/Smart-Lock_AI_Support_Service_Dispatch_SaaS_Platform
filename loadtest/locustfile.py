"""CR-0019 Locust 場景 — 100 技師併發 MVP 壓測（HD-1=b Locust / HD-3=a 100VU 30min）。

業務 mix（對齊 CIA §3.3）：
  40% GET  /api/v1/work-orders/pool      (technician polling pool)
  25% POST :accept / :assign              (接案 / 派工)
  15% POST subflows                       (material-request / delay /
                                          scope-change / door-check)
  10% PATCH 排班 / 改期
   5% POST :complete                     (完工回報)
   5% 雜項 (GET 詳情 / media upload)

使用方式：
  # mini smoke (PR-level, HD-5=b a 段)
  locust -f loadtest/locustfile.py --headless -u 10 -r 2 -t 60s \\
      --host https://api-staging.example.com --csv loadtest/results/mini

  # full run (pre-release, HD-5=b b 段)
  locust -f loadtest/locustfile.py --headless -u 100 -r 5 -t 30m \\
      --host https://api-staging.example.com --csv loadtest/results/full

SLA 門檻於 sla.py（HD-2 保守）：
  - p95 GET 500ms / p95 POST 1000ms
  - error rate 1%
  - throughput 100 req/s
  - WS 連線穩定 99%
"""

from __future__ import annotations

import os
import random
import uuid

from locust import HttpUser, between, task

DEFAULT_TENANT_ID = os.getenv(
    "LOADTEST_TENANT_ID", "00000000-0000-0000-0000-000000000001",
)
# 預先 seed 的 token pool（避開壓測時還跑 /auth/login 增加 latency 雜訊）
# 由 staging 部署時注入：LOADTEST_TECH_TOKENS="t1,t2,..." 100 個 token
_TOKEN_POOL = [
    t.strip()
    for t in os.getenv("LOADTEST_TECH_TOKENS", "").split(",")
    if t.strip()
]


def _pick_token() -> str | None:
    """從 token pool 隨機抽一個（每 user 啟動時 hold 一個）。"""
    if not _TOKEN_POOL:
        return None
    return random.choice(_TOKEN_POOL)


class TechnicianUser(HttpUser):
    """模擬一個技師日常行為。100 個 user instance = 100 技師。"""

    # 業務 polling 間隔 30s ±10s（HD-3 真實 polling cadence）
    wait_time = between(20, 40)

    def on_start(self) -> None:
        """每個 VU 啟動時抽 token + 預備 wo_id pool。"""
        self.token = _pick_token()
        self.wo_pool: list[str] = []
        # 先撈一次 pool 累積 wo_id 供後續 task 用
        if self.token:
            self._refresh_pool()

    def _auth_headers(self, *, write: bool = False) -> dict:
        h = {"Authorization": f"Bearer {self.token}"} if self.token else {}
        if write:
            h["X-Initiator"] = f"tech-{uuid.uuid4().hex[:8]}"
            h["Idempotency-Key"] = uuid.uuid4().hex
            h["Content-Type"] = "application/json"
        return h

    def _refresh_pool(self) -> None:
        """GET pool 並把 wo_id 寫入本 user pool（供 accept/subflow/complete 用）。"""
        with self.client.get(
            "/api/v1/work-orders/pool",
            headers=self._auth_headers(),
            name="GET pool",
            catch_response=True,
        ) as resp:
            if resp.status_code == 200:
                try:
                    items = resp.json().get("items") or []
                    self.wo_pool = [
                        it["work_order_id"] for it in items if "work_order_id" in it
                    ][:20]
                except Exception:  # noqa: BLE001
                    pass

    def _pick_wo(self) -> str | None:
        if not self.wo_pool:
            return None
        return random.choice(self.wo_pool)

    # ─────────────────────────────────────────────────────────────────────
    # 40% — GET pool
    # ─────────────────────────────────────────────────────────────────────

    @task(40)
    def get_pool(self) -> None:
        self._refresh_pool()

    # ─────────────────────────────────────────────────────────────────────
    # 25% — POST :accept / :assign
    # ─────────────────────────────────────────────────────────────────────

    @task(25)
    def accept_work_order(self) -> None:
        wo = self._pick_wo()
        if not wo:
            return
        self.client.post(
            f"/api/v1/work-orders/{wo}:accept",
            headers=self._auth_headers(write=True),
            name="POST :accept",
            json={},
        )

    # ─────────────────────────────────────────────────────────────────────
    # 15% — POST subflows (4 種等比抽)
    # ─────────────────────────────────────────────────────────────────────

    @task(15)
    def post_subflow(self) -> None:
        wo = self._pick_wo()
        if not wo:
            return
        subflow = random.choice([
            "material-request", "delay", "scope-change", "door-check",
        ])
        body: dict = {"note": f"loadtest {subflow}"}
        if subflow == "material-request":
            body["items"] = [{"name": "螺絲", "quantity": 1, "unit_price": "10"}]
        elif subflow == "delay":
            body["estimated_delay_minutes"] = 30
        elif subflow == "scope-change":
            body["reason"] = "現場勘查發現額外需求"
            body["items"] = [{"name": "新項", "quantity": 1, "unit_price": "100"}]
        self.client.post(
            f"/api/v1/work-orders/{wo}:{subflow}",
            headers=self._auth_headers(write=True),
            name=f"POST :{subflow}",
            json=body,
        )

    # ─────────────────────────────────────────────────────────────────────
    # 10% — PATCH 排班 / 改期
    # ─────────────────────────────────────────────────────────────────────

    @task(10)
    def patch_schedule(self) -> None:
        wo = self._pick_wo()
        if not wo:
            return
        # 用 reschedule_proposal endpoint (CR-0017 鏈路內)
        self.client.post(
            f"/api/v1/work-orders/{wo}:propose-reschedule",
            headers=self._auth_headers(write=True),
            name="POST :propose-reschedule",
            json={
                "proposed_slots": [
                    {"start": "2026-06-20T10:00:00+08:00"},
                    {"start": "2026-06-21T14:00:00+08:00"},
                ],
                "send_via": "line",
            },
        )

    # ─────────────────────────────────────────────────────────────────────
    # 5% — POST :complete
    # ─────────────────────────────────────────────────────────────────────

    @task(5)
    def complete_work_order(self) -> None:
        wo = self._pick_wo()
        if not wo:
            return
        self.client.post(
            f"/api/v1/work-orders/{wo}:complete",
            headers=self._auth_headers(write=True),
            name="POST :complete",
            json={
                "service_report": "loadtest completion",
                "completed_at": "2026-06-20T15:00:00+08:00",
            },
        )

    # ─────────────────────────────────────────────────────────────────────
    # 5% — 雜項 GET 詳情
    # ─────────────────────────────────────────────────────────────────────

    @task(5)
    def get_work_order_detail(self) -> None:
        wo = self._pick_wo()
        if not wo:
            return
        self.client.get(
            f"/api/v1/work-orders/{wo}",
            headers=self._auth_headers(),
            name="GET /work-orders/{id}",
        )
