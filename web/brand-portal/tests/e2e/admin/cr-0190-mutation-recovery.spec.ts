import { expect, test, type Page, type Route } from "@playwright/test";

const TENANT_ID = "00000000-0000-0000-0000-000000000001";
const NOTIFICATION_ID = "11111111-1111-1111-1111-111111111111";
const ITEM = {
  id: NOTIFICATION_ID,
  type: "system",
  severity: "info",
  title: "CR-0190 測試通知",
  body: "驗證 optimistic rollback 與穩定重試鍵",
  source: "system",
  created_at: "2026-07-27T12:00:00Z",
  read_at: null,
};

async function authenticatedPage(page: Page) {
  const claims = encodeURIComponent(
    JSON.stringify({
      userId: "22222222-2222-2222-2222-222222222222",
      role: "admin",
      tenantId: TENANT_ID,
      email: "admin@example.com",
    }),
  );
  await page.addInitScript(
    ({ value }) => {
      document.cookie = `smartlock_claims_app=${value}; path=/; samesite=lax`;
      document.cookie = `smartlock_claims_dispatch=${value}; path=/; samesite=lax`;
    },
    { value: claims },
  );
}

async function fulfillList(route: Route) {
  await route.fulfill({
    status: 200,
    contentType: "application/json",
    body: JSON.stringify({
      items: [ITEM],
      next_cursor: null,
      has_more: false,
      unread_count: 1,
    }),
  });
}

async function openDrawer(page: Page) {
  await page.goto("/dashboard");
  await page.getByRole("button", { name: /通知中心/ }).first().click();
  await expect(page.getByText(ITEM.title)).toBeVisible();
}

test.describe("ADR-034 mutation recovery", () => {
  test.beforeEach(async ({ page }) => {
    await authenticatedPage(page);
  });

  test("offline rollback 後 retry 沿用同一 Idempotency-Key", async ({ page }) => {
    const actionIds: string[] = [];
    let patchAttempts = 0;
    await page.route("**/*", async (route) => {
      const request = route.request();
      if (
        !request.url().startsWith("http://localhost:8001") &&
        !request.url().includes("/api-proxy/")
      ) {
        return route.continue();
      }
      if (request.url().includes("/notifications")) {
        if (request.method() === "GET") return fulfillList(route);
        if (request.method() === "PATCH") {
          patchAttempts += 1;
          actionIds.push(request.headers()["idempotency-key"] ?? "");
          if (patchAttempts === 1) {
            await new Promise((resolve) => setTimeout(resolve, 150));
            return route.abort("failed");
          }
          return route.fulfill({
            status: 200,
            contentType: "application/json",
            body: JSON.stringify({ id: NOTIFICATION_ID, read_at: "2026-07-27T13:00:00Z" }),
          });
        }
      }
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: "{}",
      });
    });

    await openDrawer(page);
    await page.getByRole("button", { name: "標為已讀", exact: true }).click();
    await expect(page.getByText(ITEM.title)).toBeHidden();
    await expect(page.getByText(ITEM.title)).toBeVisible();
    await page.getByRole("button", { name: "重試" }).click();
    await expect(page.getByText(ITEM.title)).toBeHidden();

    expect(actionIds).toHaveLength(2);
    expect(actionIds[0]).toBeTruthy();
    expect(actionIds[1]).toBe(actionIds[0]);
  });

  for (const scenario of [
    { name: "5xx", status: 503, errorCode: "DB_UNAVAILABLE" },
    { name: "409", status: 409, errorCode: "CONCURRENT_MODIFICATION" },
  ]) {
    test(`${scenario.name} 會 rollback，不留下假成功 UI`, async ({ page }) => {
      await page.route("**/*", async (route) => {
        const request = route.request();
        if (
          !request.url().startsWith("http://localhost:8001") &&
          !request.url().includes("/api-proxy/")
        ) {
          return route.continue();
        }
        if (request.url().includes("/notifications")) {
          if (request.method() === "GET") return fulfillList(route);
          if (request.method() === "PATCH") {
            await new Promise((resolve) => setTimeout(resolve, 150));
            return route.fulfill({
              status: scenario.status,
              contentType: "application/problem+json",
              body: JSON.stringify({
                type: `urn:smartlock:error:${scenario.errorCode.toLowerCase()}`,
                status: scenario.status,
                detail: `${scenario.name} simulated`,
                error_code: scenario.errorCode,
                details:
                  scenario.status === 409
                    ? [{ current_version: 4, current: { read_at: null } }]
                    : [],
              }),
            });
          }
        }
        return route.fulfill({
          status: 200,
          contentType: "application/json",
          body: "{}",
        });
      });

      await openDrawer(page);
      await page.getByRole("button", { name: "標為已讀", exact: true }).click();
      await expect(page.getByText(ITEM.title)).toBeHidden();
      await expect(page.getByText(ITEM.title)).toBeVisible();
      await expect(page.getByRole("button", { name: "重試" })).toBeVisible();
    });
  }
});
