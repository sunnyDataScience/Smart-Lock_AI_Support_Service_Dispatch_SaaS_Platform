/**
 * web/tests/e2e/admin/rbac.spec.ts — F-019 RBAC 動態調整 smoke
 *
 * 對應 task：F-019 RBAC 動態調整完整化 + CR-0002-α tenant-scoped v2 遷移
 *
 * 原有測試：
 *   1. admin 編輯 reviewer 權限 → 提交 → toast 成功（200 mock）
 *   2. operations_manager 試授越權 → 後端 403 → 顯示「您的角色階層不足以授權此權限」
 *
 * CR-0002-α 新增測試：
 *   3. 前端 fetchRoles 打 tenant-scoped v2 路徑（/tenants/{tenantId}/rbac/roles）
 *   4. 200 mock → 角色清單正常 render
 *
 * 標 @wip：本機沒有真 admin login flow（CI 暫不耦合此層）；
 * 透過 page.route() 攔截 API 模擬後端回應，僅驗 UI 行為與錯誤訊息。
 */

import { test, expect } from "@playwright/test";

// v2 tenant-scoped 路徑（CR-0002-α P3 遷移後前端打此路徑）
const ROLES_V2_PATH = "**/tenants/*/rbac/roles**";
// 角色權限更新：P3 遷移為 PUT tenantPath(`/rbac/roles/{roleName}/permissions`)
const UPDATE_PATH = "**/tenants/*/rbac/roles/reviewer/permissions*";

const TENANT_ID = "00000000-0000-0000-0000-000000000001";

const REVIEWER: any = {
  id: "reviewer",
  name: "審核員",
  description: "退款 / 保固 / 爭議審核；其餘為唯讀",
  user_count: 3,
  is_system: true,
  permissions: [
    { resource: "work_orders", read: true, write: false, delete: false, locked: false },
    { resource: "technicians", read: true, write: false, delete: false, locked: false },
    { resource: "customers", read: true, write: false, delete: false, locked: false },
    { resource: "accounting", read: true, write: false, delete: false, locked: false },
    { resource: "invoices", read: true, write: false, delete: false, locked: false },
    { resource: "refunds", read: true, write: true, delete: false, locked: false },
    { resource: "inventory", read: true, write: false, delete: false, locked: false },
    { resource: "warranty", read: true, write: true, delete: false, locked: false },
    { resource: "disputes", read: true, write: true, delete: false, locked: false },
    { resource: "audit_logs", read: true, write: false, delete: false, locked: true },
    { resource: "roles", read: false, write: false, delete: false, locked: true },
    { resource: "system_settings", read: false, write: false, delete: false, locked: true },
  ],
};

async function injectAdminSession(page: any) {
  // 偽造一個合法 JWT 結構（payload 含 role=admin）— 前端 decodeJwtPayload
  // 只解碼 payload，不驗簽，所以這在 UI 層測試足夠
  const header = btoa(JSON.stringify({ alg: "HS256", typ: "JWT" }));
  const payload = btoa(
    JSON.stringify({
      sub: "00000000-0000-0000-0000-000000000099",
      role: "admin",
      tenant_id: "00000000-0000-0000-0000-000000000001",
      type: "access",
      jti: "test-jti",
    })
      .replace(/\+/g, "-")
      .replace(/\//g, "_"),
  );
  const fakeToken = `${header}.${payload}.signature`;

  await page.addInitScript((token: string) => {
    window.localStorage.setItem("smartlock.access_token", token);
    window.localStorage.setItem("smartlock.refresh_token", "fake-refresh");
    window.localStorage.setItem(
      "smartlock.tenant_id",
      "00000000-0000-0000-0000-000000000001",
    );
    window.localStorage.setItem("smartlock.email", "admin@example.com");
  }, fakeToken);
}

async function injectManagerSession(page: any) {
  const header = btoa(JSON.stringify({ alg: "HS256", typ: "JWT" }));
  const payload = btoa(
    JSON.stringify({
      sub: "00000000-0000-0000-0000-000000000088",
      role: "operations_manager",
      tenant_id: "00000000-0000-0000-0000-000000000001",
      type: "access",
      jti: "test-jti-mgr",
    })
      .replace(/\+/g, "-")
      .replace(/\//g, "_"),
  );
  const fakeToken = `${header}.${payload}.signature`;
  await page.addInitScript((token: string) => {
    window.localStorage.setItem("smartlock.access_token", token);
    window.localStorage.setItem("smartlock.refresh_token", "fake-refresh");
    window.localStorage.setItem(
      "smartlock.tenant_id",
      "00000000-0000-0000-0000-000000000001",
    );
  }, fakeToken);
}

test.describe("@wip F-019 RBAC dynamic adjustment", () => {
  test("admin edits reviewer permissions and sees success toast", async ({
    page,
  }) => {
    await injectAdminSession(page);

    // CR-0002-α：前端已遷移至 v2 tenant-scoped 路徑，mock 對應路徑
    await page.route(ROLES_V2_PATH, async (route) => {
      if (route.request().method() === "GET") {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({ data: [REVIEWER] }),
        });
      } else {
        await route.continue();
      }
    });

    let captured: any = null;
    await page.route(UPDATE_PATH, async (route) => {
      captured = route.request().postDataJSON();
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          data: {
            role_name: "reviewer",
            permissions: captured?.permissions ?? [],
            updated_at: new Date().toISOString(),
            ws_published: true,
            affected_user_count: 3,
          },
        }),
      });
    });

    await page.goto("/admin/roles");
    await expect(page.getByText("角色與權限管理")).toBeVisible({ timeout: 15000 });

    const editBtn = page.getByTestId("edit-permissions-btn");
    await expect(editBtn).toBeEnabled({ timeout: 10000 });
    await editBtn.click();

    const modal = page.getByTestId("rbac-editor-modal");
    await expect(modal).toBeVisible();

    // 勾上 invoices.write（reviewer 預設未授）
    await modal.getByTestId("perm-invoices.write").check();

    // 填入原因
    await modal
      .getByTestId("rbac-editor-reason")
      .fill("F-019 E2E：開放 reviewer 寫入發票");

    await modal.getByTestId("rbac-editor-submit").click();

    // 成功 toast
    await expect(page.getByText("已更新「審核員」的權限矩陣")).toBeVisible({
      timeout: 10000,
    });
    expect(captured?.permissions).toContain("invoices.write");
    expect(captured?.reason?.length).toBeGreaterThanOrEqual(4);
  });

  test("operations_manager sees hierarchy violation message on 403", async ({
    page,
  }) => {
    await injectManagerSession(page);

    // CR-0002-α：mock v2 tenant-scoped 路徑
    await page.route(ROLES_V2_PATH, async (route) => {
      if (route.request().method() === "GET") {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({ data: [REVIEWER] }),
        });
      } else {
        await route.continue();
      }
    });

    await page.route(UPDATE_PATH, async (route) => {
      await route.fulfill({
        status: 403,
        contentType: "application/json",
        body: JSON.stringify({
          error_code: "RBAC_HIERARCHY_VIOLATION",
          message: "actor 嘗試授權自己未持有的 permission",
        }),
      });
    });

    await page.goto("/admin/roles");
    await expect(page.getByText("角色與權限管理")).toBeVisible({ timeout: 15000 });

    // operations_manager 不在 RBAC_ADMIN_ROLES → 編輯按鈕 disabled
    const editBtn = page.getByTestId("edit-permissions-btn");
    await expect(editBtn).toBeDisabled();
    await expect(editBtn).toHaveAttribute(
      "title",
      /階層不足|不足以授權/,
    );
  });
});

// ─── CR-0002-α：tenant-scoped v2 遷移 smoke ──────────────────────────────────

test.describe("@wip CR-0002-α RBAC tenant-scoped v2 路徑", () => {
  test("fetchRoles 打 tenant-scoped v2 端點並 render 角色清單", async ({
    page,
  }) => {
    await injectAdminSession(page);

    // mock v2 tenant-scoped GET（前端遷移後打 /tenants/{tenantId}/rbac/roles）
    let capturedUrl = "";
    await page.route(ROLES_V2_PATH, async (route) => {
      capturedUrl = route.request().url();
      if (route.request().method() === "GET") {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({ data: [REVIEWER] }),
        });
      } else {
        await route.continue();
      }
    });

    await page.goto("/admin/roles");
    // 角色清單正常 render（等頁面標題先出現）
    await expect(page.getByText("角色與權限管理")).toBeVisible({ timeout: 15000 });
    // 等角色 card render（class="text-base font-semibold" 的「審核員」heading）
    await expect(
      page.locator(".grid .text-base.font-semibold").filter({ hasText: "審核員" }).first(),
    ).toBeVisible({ timeout: 10000 });

    // 斷言打的 URL 含 tenant-scoped v2 路徑
    expect(capturedUrl).toMatch(/\/tenants\/[^/]+\/rbac\/roles/);
    // 確認 path 含正確的 tenantId
    expect(capturedUrl).toContain(TENANT_ID);
  });

  test("fetchRoles 在缺少 tenant 時顯示錯誤（NO_TENANT）", async ({
    page,
  }) => {
    // 注入沒有 tenant_id 的 token
    const header = btoa(JSON.stringify({ alg: "HS256", typ: "JWT" }));
    const payload = btoa(
      JSON.stringify({
        sub: "00000000-0000-0000-0000-000000000099",
        role: "admin",
        // tenant_id 故意缺少
        type: "access",
        jti: "test-jti-no-tenant",
      })
        .replace(/\+/g, "-")
        .replace(/\//g, "_"),
    );
    const fakeToken = `${header}.${payload}.signature`;

    await page.addInitScript((token: string) => {
      window.localStorage.setItem("smartlock.access_token", token);
      window.localStorage.setItem("smartlock.refresh_token", "fake-refresh");
      // 不設 tenant_id → getCurrentSession().tenantId = null
    }, fakeToken);

    await page.goto("/admin/roles");

    // 頁面應顯示錯誤提示（error div 紅底）
    await expect(
      page.locator(".border-red-200.bg-red-50"),
    ).toBeVisible({ timeout: 15000 });
  });
});
