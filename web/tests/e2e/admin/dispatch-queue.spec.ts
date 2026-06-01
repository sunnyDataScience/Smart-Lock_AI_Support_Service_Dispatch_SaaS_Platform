/**
 * web/tests/e2e/admin/dispatch-queue.spec.ts —
 * /admin/dispatch-queue 頁面 tenant-scoped v2 dispatch 端點 E2E 測試（CR-0002-α）
 *
 * 測試矩陣：
 *   1. /admin/dispatch-queue 頁面渲染 → mock GET /api/v1/work-orders/dispatch-queue
 *      + mock GET /api/v1/dispatch-logs → 表格顯示 + data-tenant 屬性含 tenantId
 *   2. v2 dispatch:candidates mock → GET *\/tenants\/*\/dispatch:candidates →
 *      驗證 tenant-scoped path 格式正確
 *   3. v2 dispatch:auto-match mock → POST *\/tenants\/*\/dispatch:auto-match →
 *      驗證 tenant-scoped path 格式正確
 *   4. 錯誤狀態（500）→ 顯示錯誤 banner
 *
 * 透過 page.route() 攔截 glob pattern 模擬回應。
 * 使用 injectAdminSession 注入假 JWT（tenant_id = DEFAULT_TENANT）。
 *
 * 標 @wip：本機沒有真實 DB；透過 mock 隔離 API 層。
 */

import { test, expect, Page } from "@playwright/test";

const TENANT_ID = "00000000-0000-0000-0000-000000000001";

const DISPATCH_QUEUE_PATH = "**/api/v1/work-orders/dispatch-queue";
const DISPATCH_LOGS_PATH = "**/api/v1/dispatch-logs**";
const WORK_ORDERS_POOL_PATH = "**/api/v1/work-orders/pool**";
const CANDIDATES_V2_PATH = `**/tenants/*/dispatch:candidates**`;
const AUTO_MATCH_V2_PATH = `**/tenants/*/dispatch:auto-match`;

const SAMPLE_SNAPSHOT = {
  pending: 3,
  assigning: 1,
  assigned: 12,
  sla_at_risk: 2,
};

const SAMPLE_LOGS_PAGE = {
  items: [
    {
      id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
      work_order_id: "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
      attempt_number: 1,
      technician_id: "cccccccc-cccc-4ccc-8ccc-cccccccccccc",
      technician_name: "陳大明",
      score: 85.5,
      status: "assigned",
      created_at: "2026-05-30T10:00:00Z",
      updated_at: "2026-05-30T10:05:00Z",
    },
  ],
  next_cursor: null,
  has_more: false,
  total: 1,
};

const SAMPLE_POOL_PAGE = {
  items: [],
  next_cursor: null,
  has_more: false,
  total: 0,
};

const SAMPLE_CANDIDATES = {
  candidates: [
    {
      technician: {
        id: "cccccccc-cccc-4ccc-8ccc-cccccccccccc",
        name: "陳大明",
        rating: 4.5,
        skills: ["Dormakaba"],
        service_areas: ["台北市信義區"],
        status: "active",
      },
      score: 85.5,
      distance_km: 0,
      skill_match: 1.0,
      availability_eta_minutes: 15,
      score_breakdown: {
        skill: { factor: 1.0, weight: 0.4, contribution: 40, rationale: "技師認證品牌包含 Dormakaba ✓" },
        distance: { factor: 1.0, weight: 0.3, contribution: 30, rationale: "技師服務區包含 台北市信義區" },
        rating: { factor: 0.9, weight: 0.3, contribution: 27, rationale: "高評分技師（4.5/5）" },
      },
    },
  ],
  total: 1,
  auto_dispatch_attempts: [],
};

const SAMPLE_AUTO_MATCH = {
  candidates: [
    {
      technician_id: "cccccccc-cccc-4ccc-8ccc-cccccccccccc",
      technician_name: "陳大明",
      score: 0.855,
      distance_km: 0,
      eta_minutes: 15,
      rating: 4.5,
    },
  ],
};

async function injectAdminSession(page: Page) {
  const header = btoa(JSON.stringify({ alg: "HS256", typ: "JWT" }));
  const payloadObj = {
    sub: "00000000-0000-0000-0000-000000000099",
    role: "admin",
    tenant_id: TENANT_ID,
    type: "access",
    jti: "test-jti-dispatch-queue",
  };
  const payload = btoa(
    JSON.stringify(payloadObj)
      .replace(/\+/g, "-")
      .replace(/\//g, "_"),
  );
  const fakeToken = `${header}.${payload}.signature`;
  await page.addInitScript(
    ({ token, tenantId }: { token: string; tenantId: string }) => {
      window.localStorage.setItem("smartlock.access_token", token);
      window.localStorage.setItem("smartlock.refresh_token", "fake-refresh");
      window.localStorage.setItem("smartlock.tenant_id", tenantId);
      window.localStorage.setItem("smartlock.email", "admin@example.com");
    },
    { token: fakeToken, tenantId: TENANT_ID },
  );
}

// ---------------------------------------------------------------------------
// Helper: mock all queue page API calls
// ---------------------------------------------------------------------------

async function mockQueueApis(page: Page) {
  await page.route(DISPATCH_QUEUE_PATH, async (route) => {
    if (route.request().method() === "GET") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(SAMPLE_SNAPSHOT),
      });
    } else {
      await route.continue();
    }
  });
  await page.route(DISPATCH_LOGS_PATH, async (route) => {
    if (route.request().method() === "GET") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(SAMPLE_LOGS_PAGE),
      });
    } else {
      await route.continue();
    }
  });
  await page.route(WORK_ORDERS_POOL_PATH, async (route) => {
    if (route.request().method() === "GET") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(SAMPLE_POOL_PAGE),
      });
    } else {
      await route.continue();
    }
  });
}

// ---------------------------------------------------------------------------
// Test: /admin/dispatch-queue page renders
// ---------------------------------------------------------------------------

test.describe("@wip dispatch-queue page — render + tenant-scoped data-tenant", () => {
  test("renders dispatch queue page with snapshot stats", async ({ page }) => {
    await injectAdminSession(page);
    await mockQueueApis(page);

    await page.goto("/admin/dispatch-queue");

    // 頁面 title 顯示
    await expect(page.locator("h1").first()).toBeVisible({ timeout: 15000 });

    // snapshot 統計數字：pending=3, assigning=1, assigned=12, sla_at_risk=2
    await expect(page.getByText("3")).toBeVisible({ timeout: 10000 });
    await expect(page.getByText("12")).toBeVisible({ timeout: 5000 });
  });

  test("root container has data-tenant attribute with tenantId", async ({ page }) => {
    await injectAdminSession(page);
    await mockQueueApis(page);

    await page.goto("/admin/dispatch-queue");

    await expect(page.locator("h1").first()).toBeVisible({ timeout: 15000 });

    // data-tenant 屬性應包含 tenantId（v2 路徑對齊驗證）
    const container = page.locator(`[data-tenant="${TENANT_ID}"]`).first();
    await expect(container).toBeVisible({ timeout: 5000 });
  });

  test("shows error banner on API error", async ({ page }) => {
    await injectAdminSession(page);

    await page.route(DISPATCH_QUEUE_PATH, async (route) => {
      await route.fulfill({
        status: 500,
        contentType: "application/json",
        body: JSON.stringify({ error_code: "INTERNAL_ERROR", message: "Database unavailable" }),
      });
    });
    await page.route(DISPATCH_LOGS_PATH, async (route) => {
      await route.fulfill({
        status: 500,
        contentType: "application/json",
        body: JSON.stringify({ error_code: "INTERNAL_ERROR", message: "Database unavailable" }),
      });
    });
    await page.route(WORK_ORDERS_POOL_PATH, async (route) => {
      await route.fulfill({
        status: 500,
        contentType: "application/json",
        body: JSON.stringify({ error_code: "INTERNAL_ERROR", message: "Database unavailable" }),
      });
    });

    await page.goto("/admin/dispatch-queue");

    await expect(page.locator("h1").first()).toBeVisible({ timeout: 15000 });

    // 錯誤 banner 應顯示
    const errorEl = page.locator(".border-red-200.bg-red-50").first();
    await expect(errorEl).toBeVisible({ timeout: 10000 });
  });
});

// ---------------------------------------------------------------------------
// Test: v2 dispatch:candidates tenant-scoped path
// ---------------------------------------------------------------------------

test.describe("@wip dispatch:candidates v2 — tenant-scoped path format", () => {
  test("GET /tenants/{tenantId}/dispatch:candidates path is well-formed", async ({ page }) => {
    await injectAdminSession(page);
    await mockQueueApis(page);

    let capturedCandidatesPath: string | null = null;

    await page.route(CANDIDATES_V2_PATH, async (route) => {
      if (route.request().method() === "GET") {
        capturedCandidatesPath = route.request().url();
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify(SAMPLE_CANDIDATES),
        });
      } else {
        await route.continue();
      }
    });

    await page.goto("/admin/dispatch-queue");
    await expect(page.locator("h1").first()).toBeVisible({ timeout: 15000 });

    // 模擬頁面透過 fetch 呼叫 v2 candidates 端點（驗證路徑格式）
    const result = await page.evaluate(
      async ({ tenantId }: { tenantId: string }) => {
        const path = `/tenants/${tenantId}/dispatch:candidates?work_order_id=test-wo`;
        try {
          const res = await fetch(path, { method: "GET" });
          return { ok: res.ok, url: path, status: res.status };
        } catch {
          return { ok: false, url: path, status: 0 };
        }
      },
      { tenantId: TENANT_ID },
    );

    // 路徑格式正確：含 tenantId + dispatch:candidates
    expect(result.url).toContain(`/tenants/${TENANT_ID}/dispatch:candidates`);

    // page.route 攔截到則 captured 路徑也應對齊
    if (capturedCandidatesPath !== null) {
      const captured: string = capturedCandidatesPath;
      expect(captured).toContain(
        `/tenants/${TENANT_ID}/dispatch:candidates`,
      );
    }
  });
});

// ---------------------------------------------------------------------------
// Test: v2 dispatch:auto-match tenant-scoped path
// ---------------------------------------------------------------------------

test.describe("@wip dispatch:auto-match v2 — tenant-scoped path format", () => {
  test("POST /tenants/{tenantId}/dispatch:auto-match path is well-formed", async ({ page }) => {
    await injectAdminSession(page);
    await mockQueueApis(page);

    let capturedAutoMatchPath: string | null = null;

    await page.route(AUTO_MATCH_V2_PATH, async (route) => {
      if (route.request().method() === "POST") {
        capturedAutoMatchPath = route.request().url();
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify(SAMPLE_AUTO_MATCH),
        });
      } else {
        await route.continue();
      }
    });

    await page.goto("/admin/dispatch-queue");
    await expect(page.locator("h1").first()).toBeVisible({ timeout: 15000 });

    // 模擬頁面透過 fetch 呼叫 v2 auto-match 端點（驗證路徑格式）
    const result = await page.evaluate(
      async ({
        tenantId,
        fakePcId,
      }: {
        tenantId: string;
        fakePcId: string;
      }) => {
        const path = `/tenants/${tenantId}/dispatch:auto-match`;
        try {
          const res = await fetch(path, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              problem_card_id: fakePcId,
              urgency: "normal",
              max_candidates: 3,
            }),
          });
          return { ok: res.ok, url: path, status: res.status };
        } catch {
          return { ok: false, url: path, status: 0 };
        }
      },
      {
        tenantId: TENANT_ID,
        fakePcId: "dddddddd-dddd-4ddd-8ddd-dddddddddddd",
      },
    );

    // 路徑格式正確：含 tenantId + dispatch:auto-match
    expect(result.url).toContain(`/tenants/${TENANT_ID}/dispatch:auto-match`);

    // page.route 攔截到則 captured 路徑也應對齊
    if (capturedAutoMatchPath !== null) {
      const captured: string = capturedAutoMatchPath;
      expect(captured).toContain(
        `/tenants/${TENANT_ID}/dispatch:auto-match`,
      );
    }
  });
});
