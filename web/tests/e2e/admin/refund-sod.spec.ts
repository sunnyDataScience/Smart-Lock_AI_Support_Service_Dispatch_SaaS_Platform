/**
 * refund-sod.spec.ts — 退款 SoD 三維 user flow（FR-0014 / ADR-0040v2）E2E 覆蓋
 *
 * 對應頁面：web/src/app/admin/refunds/page.tsx
 *   - RefundReviewTable（列表 + approve/reject 決策按鈕）
 *   - DecisionModal（決策 modal：approve/reject/escalate + reason 必填）
 *   - CreateRefundModal（建立退款 modal：X-Initiator / X-Approver header，
 *     approver 必填且須與發起人不同 → SoD 三維分權）
 *
 * 三條斷言主軸：
 *   1. 列表渲染 — 7 筆待審退款資料應有資料列。
 *   2. 決策流程 — 點 approve/reject 開 modal → 填 reason → 送出 → 驗證 toast 或狀態更新。
 *   3. SoD 核心 — 建立退款 modal 的 approver 欄位存在且必填（送出鈕在 approver 空白時 disabled）。
 *
 * 注意：本 spec 只測既有真實資料（7 筆），不啟動 server、不改產品碼。
 * 環境變數：USE_EXISTING_SERVER=1 BASE_URL=http://localhost:3000
 */

import { test, expect, type Page } from "@playwright/test";

/** admin 登入（照 all-buttons-audit.spec.ts 的 login pattern）。 */
async function login(page: Page) {
  await page.goto("/login");
  await page.fill('input[type="email"]', "admin@example.com");
  await page.fill('input[type="password"]', "changeme123");
  await page.click('button[type="submit"]');
  await page.waitForURL((u) => !u.pathname.includes("/login"), {
    timeout: 15_000,
  });
}

/**
 * 取得列表中「可決策」的資料列（含「核准」或「拒絕」按鈕的 row）。
 * RefundReviewTable 的 row 是 div（無 role=row），actions 區塊放最右側。
 * pending / csm_approved 狀態才會渲染 approve/reject 按鈕。
 */
function decisionRowButtons(page: Page) {
  // 表格內的「核准」「第二簽」按鈕（approve 路徑），與「拒絕」按鈕
  return {
    approve: page.getByRole("button", { name: /^核准$|^第二簽$/ }),
    reject: page.getByRole("button", { name: /^拒絕$/ }),
  };
}

test.describe("退款 SoD 三維 user flow（FR-0014）", () => {
  test.beforeEach(async ({ page }) => {
    await login(page);
    await page.goto("/admin/refunds", { waitUntil: "domcontentloaded" });
    await page.waitForLoadState("networkidle").catch(() => {});
  });

  test("1. 列表渲染 — 待審退款資料列應存在（7 筆種子資料）", async ({
    page,
  }) => {
    // 頁標題鎖定頁面已載入
    await expect(
      page.getByRole("heading", { name: "退款審核佇列" }),
    ).toBeVisible();

    // 連線狀態應為「已連線」（後端 8001 有資料），非「未連線」
    await expect(page.getByText("已連線", { exact: true })).toBeVisible();

    // 「共 N 筆」計數 — 抓出 N 並斷言 > 0（種子應有 7 筆，但用 > 0 容忍狀態流轉）
    const countLocator = page.getByText(/共\s*\d+\s*筆/);
    await expect(countLocator).toBeVisible();
    const countText = (await countLocator.textContent()) ?? "";
    const count = Number(countText.replace(/\D/g, ""));
    expect(count, `列表計數應 > 0，實際文字：「${countText}」`).toBeGreaterThan(0);

    // 列表不應停在 empty / loading 占位 — 至少一個工單 ID 連結（每列都有）
    const workOrderLinks = page.locator('a[href^="/work-orders/"]');
    await expect(workOrderLinks.first()).toBeVisible({ timeout: 10_000 });
    expect(
      await workOrderLinks.count(),
      "應有 ≥1 列退款資料（每列含工單連結）",
    ).toBeGreaterThan(0);
  });

  test("2. 決策流程 — 開決策 modal、填 reason、送出 → 驗證 toast / 狀態更新", async ({
    page,
  }) => {
    const { approve } = decisionRowButtons(page);

    // 若無任何可決策列（資料全已結案），明確斷言「不可決策」可達狀態而非硬湊
    const approveCount = await approve.count();
    if (approveCount === 0) {
      // 全部已結案 → 應顯示已核准/已拒絕/已完款等終態 chip，不應有決策按鈕
      const closedChips = page.getByText(
        /已核准|已拒絕|已完款|已取消|已升級/,
      );
      expect(
        await closedChips.count(),
        "無可決策列時，列表應為已結案/已升級終態（無 approve 按鈕屬合理資料狀態）",
      ).toBeGreaterThan(0);
      test.info().annotations.push({
        type: "data-state",
        description: "7 筆退款皆非 pending/csm_approved，無法觸發決策流程；已斷言終態可達。",
      });
      return;
    }

    // 點第一列的「核准」開決策 modal
    await approve.first().click();

    // DecisionModal 容器（div.fixed.inset-0.z-40）
    const modal = page
      .locator("div.fixed.inset-0")
      .filter({ has: page.getByRole("heading", { name: "退款審批決策" }) })
      .first();
    await expect(
      page.getByRole("heading", { name: "退款審批決策" }),
    ).toBeVisible();

    // reason textarea 必填 — 空白時送出鈕 disabled
    const reasonBox = modal.locator("textarea");
    await expect(reasonBox).toBeVisible();

    // 決策送出按鈕：文字「核准退款」會同時命中「決策類型切換鈕（grid 內）」與
    // 「footer 送出鈕」。兩者差異 —— 送出鈕帶 text-white class，切換鈕為 border。
    // 用 footer 內的 text-white 主行動鈕收斂到唯一送出鈕。
    const submitBtn = modal
      .locator('button.text-white', { hasText: "核准退款" })
      .last();
    await expect(submitBtn, "reason 空白時送出鈕應 disabled").toBeDisabled();

    // 填 reason → 送出鈕應 enabled
    await reasonBox.fill("E2E 自動化測試：核准本退款（SoD 三維覆蓋）");
    await expect(submitBtn).toBeEnabled();

    // 送出 → 監看決策 API 請求/回應。
    const decisionResp = page
      .waitForResponse(
        (r) =>
          /\/refunds\/[^/]+\/decision/.test(r.url()) &&
          r.request().method() === "POST",
        { timeout: 15_000 },
      )
      .catch(() => null);

    await submitBtn.click();
    const resp = await decisionResp;
    expect(resp, "決策送出應實際打到 POST /refunds/{id}/decision").not.toBeNull();

    // 5xx 一律當伺服器錯誤拋出
    if (resp && resp.status() >= 500) {
      throw new Error(
        `決策端點 5xx：${resp.request().method()} ${resp.url()} → ${resp.status()}`,
      );
    }

    // 請求 payload 契約檢查 ── decision/reason 必須在「頂層」（後端 schema 要求）。
    // 目前產品碼把 body 多包一層（{ body: {...} }），導致後端 422 Field required。
    // 此斷言鎖定該契約；修好產品碼前會以明確訊息失敗（faithful regression，不假過）。
    const rawBody = resp?.request().postData() ?? "";
    let parsed: Record<string, unknown> = {};
    try {
      parsed = JSON.parse(rawBody);
    } catch {
      /* 保持空物件 → 下方斷言會帶原始字串失敗 */
    }
    expect(
      "decision" in parsed && "reason" in parsed,
      `決策 payload 應於頂層帶 decision/reason，實際送出：${rawBody}\n` +
        `→ 產品 bug：RefundReviewPage.handleSubmitDecision 以 { body } 多包一層，` +
        `api.post 第二參數即 body，造成 {"body":{...}} → 後端 422 VALIDATION_ERROR。`,
    ).toBe(true);

    // payload 正確時，後端應回 2xx 且前端出現「已送出」toast 或 modal 關閉。
    const toastVisible = await page
      .getByText(/已送出/)
      .waitFor({ state: "visible", timeout: 8_000 })
      .then(() => true)
      .catch(() => false);
    const closed = await page
      .getByRole("heading", { name: "退款審批決策" })
      .waitFor({ state: "hidden", timeout: 8_000 })
      .then(() => true)
      .catch(() => false);

    expect(
      toastVisible || closed,
      `送出成功後應出現「已送出」toast 或 modal 關閉；API 狀態：${resp?.status()}`,
    ).toBeTruthy();
  });

  test("3. SoD 核心 — 建立退款 modal 的 approver 欄位存在且必填（approver ≠ initiator 把關）", async ({
    page,
  }) => {
    // 開「建立退款申請」modal
    await page.getByRole("button", { name: "建立退款申請" }).click();

    // modal 標題（modal 內 span，與 page header 同字串 → 用 modal 容器收斂）
    const dialog = page
      .locator("div.fixed.inset-0")
      .filter({ hasText: "覆核主管 ID" })
      .first();
    await expect(dialog).toBeVisible();

    // SoD 核心欄位：覆核主管 ID（X-Approver），placeholder 明示「須與發起人不同（SoD）」
    const approverInput = dialog.locator(
      'input[placeholder="須與發起人不同（SoD）"]',
    );
    await expect(
      approverInput,
      "建立退款 modal 應有 approver（覆核主管）欄位，承載 X-Approver header",
    ).toBeVisible();

    // 標籤文字驗證 SoD 語意確實面向使用者呈現
    await expect(dialog.getByText("覆核主管 ID（X-Approver）")).toBeVisible();

    const submitBtn = dialog.getByRole("button", { name: "建立" });

    // (a) 只填其他欄位、approver 空白 → 送出鈕仍 disabled（approver 必填）
    const workOrderInput = dialog.locator(
      'input[placeholder="00000000-0000-0000-0000-000000000000"]',
    );
    await workOrderInput.fill("11111111-1111-1111-1111-111111111111");
    await dialog.locator('input[placeholder="例如 1500.00"]').fill("1500");
    await dialog
      .locator("textarea")
      .fill("E2E：驗證 SoD approver 必填行為");
    await expect(
      submitBtn,
      "approver 空白時送出鈕應 disabled（approver 必填）",
    ).toBeDisabled();

    // (b) approver 填「非 UUID」格式 → 仍 disabled（前端 UUID_RE 把關）
    await approverInput.fill("not-a-uuid");
    await expect(
      submitBtn,
      "approver 非 UUID 時送出鈕應 disabled（前端格式把關）",
    ).toBeDisabled();

    // (c) approver 填合法 UUID（與 initiator 不同）→ 送出鈕 enabled
    //     注意：此處只驗證「前端表單把關」可達 enabled，不實際送出建立
    //     （避免污染種子資料；後端最終 SoD 把關屬 API/整合層測試範疇）。
    await approverInput.fill("22222222-2222-2222-2222-222222222222");
    await expect(
      submitBtn,
      "工單/金額/原因/合法 approver 齊備時送出鈕應 enabled",
    ).toBeEnabled();

    // 收尾：取消關閉 modal（不送出，保持資料純淨）
    await dialog.getByRole("button", { name: "取消" }).click();
    await expect(dialog).toBeHidden();
  });
});
