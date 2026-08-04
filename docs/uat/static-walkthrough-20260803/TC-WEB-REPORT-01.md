# TC-WEB-REPORT-01 — 儀表板與報表匯出

## 結果

| 項目 | 內容 |
|---|---|
| **判定** | **部分實作** |
| **本判定以原始碼走查為主，並補實跑證據** | 未啟動應用服務與前端；報表 API 側既有測試 31 項全數通過（見步驟 5）。**畫面呈現的數字正確性、匯出檔內容、timeout 當下的畫面狀態屬執行期觀測，本次未取得** |
| 走查時間 | 2026-08-03（UTC+8） |
| 走查基準 | commit `17aa40c5` |
| 走查範圍 | `api/routers/reports_v2.py:1-198`、`api/routers/reports_kpi.py:24-48`、`api/routers/reports_export.py:26-50`、`api/routers/reports_operational_kpi.py:24-33`、`api/routers/reports_customer_satisfaction.py:25-40`、`api/routers/dashboard_v2.py:28-41`、`api/routers/scheduled_reports_v2.py:31-95`、`api/services/kpi_service.py:32-53/262-320`、`api/services/report_export_service.py:67/192-236`、`api/core/deps.py:290-336`、`web/brand-portal/src/app/admin/reports/kpi/page.tsx:116-139`、`web/brand-portal/src/app/admin/reports/revenue/page.tsx:150-178/506-513`、`web/brand-portal/src/components/admin/reports/ReportExportModal.tsx:81-115`、`web/brand-portal/src/lib/rolePolicy.ts:56`、`web/brand-portal/src/lib/api.ts:447-475/803-819`、`web/brand-portal/src/lib/cache.ts:42-76` |
| 優先級 / 路徑類型 | P0 / failure＋recovery |
| 事實結論 | 三條判定基準逐條狀況不同。「低權角色 403」有對應：報表端點閘門為 `OPS_ROLES`（`admin` / `operations_manager`），`customer_service` 不在內（`api/core/deps.py:293-299`），前端路由政策同樣只放行該兩角色（`rolePolicy.ts:56`）。「篩選一致」部分不成立：匯出服務收下 `from` / `to` 後不傳給任何下游查詢，只在標題附加一行提示（`report_export_service.py:192-209`），而營收頁的畫面查詢確實會送 `start_date` / `end_date`（`reports_v2.py:107-112`）。「時區」在 api 與 brand-portal 原始碼中無任何時區正規化，`Asia/Taipei` 零命中。「失敗時不顯示舊租戶資料」：GET 快取鍵含 tenant 且失敗不入快取（`api.ts:471-473`、`cache.ts:70-73`），但 KPI 頁的 `catch` 只設 error 不清空既有 `report` state（`kpi/page.tsx:126-129`）。 |

**TC 原文**｜前置：固定 KPI/API fixture、admin/ops/cs token｜步驟：比對 dashboard/API 值、匯出報表、令 API 403/timeout、低權角色讀敏感報表｜判定基準：數字、時區與篩選一致；低權角色 403；失敗時不顯示舊租戶資料｜需求：FR-WEB-04｜旅程：SC-08、SC-09

整體判定 `部分實作` 由以下逐條狀態合成（各條依據見對應步驟）：

| 判定基準逐條 | 本條狀態 | 步驟 |
|---|---|---|
| 數字一致 | 無法靜態判定（畫面呈現屬執行期觀測） | 步驟 1 |
| 篩選一致 | 不一致（匯出路徑不套用日期區間） | 步驟 2 |
| 時區一致 | 無法靜態判定（無時區正規化程式碼，取決於 DB session 與瀏覽器時區的執行期設定） | 步驟 3 |
| 低權角色 403 | 一致 | 步驟 4 |
| 失敗時不顯示舊租戶資料 | 部分實作（快取層有隔離，KPI 頁 `catch` 不清空既有 state） | 步驟 5 |

---

## 事件風暴分解

| Actor | Command | 預期 Domain Event | Policy | 程式碼落點 | 程式碼實際行為 |
|---|---|---|---|---|---|
| admin | 開 KPI 儀表板 | `KpiReportRead` | 數字取自單一 service | `web/.../kpi/page.tsx:120-125` → `api/routers/reports_v2.py:65-70` | 呼 `kpi_service.get_kpi_report` |
| admin | 匯出 KPI 報表 | `ReportExported` | 與畫面同口徑 | `api/services/report_export_service.py:222-229` | 同呼 `kpi_service.get_kpi_report(period=period or "30d")` |
| admin | 匯出時帶日期區間 | `ReportExported(篩選一致)` | 篩選一致 | `api/services/report_export_service.py:192-209` | 參數收下不傳下游，改在 subtitle 附提示並記 warning |
| cs | 讀 `/reports/kpi` | `RequestRejected(403)` | 低權 403 | `api/routers/reports_v2.py:55` + `api/core/deps.py:319-325` | `FORBIDDEN`，403 |
| cs | 開 `/admin/reports` 頁 | `RouteBlocked` | 前端對齊 | `web/brand-portal/src/lib/rolePolicy.ts:56` | roles 僅 `admin` / `operations_manager` |
| 系統 | API 回 403 / 逾時 | `StaleDataCleared` | 不顯示舊資料 | `web/.../kpi/page.tsx:126-132` | 設 error，`report` state 保持前次值 |
| 使用者 | 登出後換帳號 | `CacheCleared` | 租戶隔離 | `web/brand-portal/src/lib/api.ts:809-812` | `auth.clear()` + `cacheClear()` |

---

## 走查紀錄

### 步驟 1 — dashboard 值與 API 值的來源

- **動作**：追畫面與匯出各自呼叫的資料來源
- **預期**：同一口徑
- **實際**：KPI 兩者同呼 `kpi_service.get_kpi_report`；營收兩者傳入參數不同

畫面（`web/brand-portal/src/app/admin/reports/kpi/page.tsx:116-133`）：

```tsx
  async function fetchReport(p: Period) {
    setLoading(true);
    setError(null);
    try {
      // v2 tenant-scoped path（FR-0021 / CR-0003 P2-W1）
      const tenantId = auth.getTenantId();
      const res = await api.get<KpiReport>(
        `/tenants/${encodeURIComponent(tenantId)}/reports/kpi?period=${p}`,
      );
      setReport(res);
    } catch (e) {
      setError(
        friendlyError(e),
      );
    } finally {
      setLoading(false);
    }
  }
```

API（`api/routers/reports_v2.py:65-71`）：

```python
    report = await kpi_service.get_kpi_report(
        tenant_id=tenantId,
        period=period.value,
        start_date=start_date,
        end_date=end_date,
    )
    return KpiReport(**report).model_dump(mode="json")
```

匯出（`api/services/report_export_service.py:222-229`）：

```python
    if report_type == "kpi":
        report = await kpi_service.get_kpi_report(
            tenant_id=tenant_id, period=period or "30d"
        )
        return _kpi_to_rows(report), {
            "title": "KPI 報表 (KPI Report)",
            "subtitle": f"period: {report.get('period', '')}" + _notice,
        }
```

營收匯出（`api/services/report_export_service.py:231-236`）不傳 `granularity` 與日期：

```python
    if report_type == "revenue":
        report = await revenue_service.get_revenue_summary(tenant_id=tenant_id)
```

而營收畫面（`web/brand-portal/src/app/admin/reports/revenue/page.tsx:155-164`）會送：

```tsx
      const query: Record<string, string> = { granularity };
      if (range.from && range.to) {
        query.start_date = toDateOnly(range.from);
        query.end_date = toDateOnly(range.to);
      }
      const res = await api.get<RevenueSummary>(
        tenantPath("/reports/revenue"),
        { query },
      );
```

### 步驟 2 — 匯出報表與篩選

- **動作**：追前端傳給匯出端點的 filter 與後端的處理
- **預期**：畫面篩選帶入匯出
- **實際**：前端會帶，後端 KPI 只用 `period`，`from` / `to` 全部四種報表都不進查詢

`web/brand-portal/src/components/admin/reports/ReportExportModal.tsx:84-93` 把父頁 filters 展開進 query string：

```tsx
    const query: Record<string, string> = {
      report_type: reportType,
      format,
    };
    for (const [key, value] of Object.entries(filters)) {
      if (value === undefined || value === null) continue;
      const str = String(value);
      if (str.length === 0) continue;
      query[key] = str;
    }
```

KPI 頁傳的是 `{ period }`（`kpi/page.tsx:395-400`）；營收頁傳 `{ granularity, from, to }`（`revenue/page.tsx:506-512`）。

後端（`api/services/report_export_service.py:192-209`）：

```python
def _date_range_notice(from_date: str | None, to_date: str | None) -> str:
    """呼叫端傳了日期區間但本服務不支援時的可見標注（2026-08-02 掃描）。

    `from` / `to` 在 openapi 宣告為 `format: date`，前端的 ReportExportModal 也真的
    會把它們帶進 query string，但四種報表的下游（kpi / revenue / technician_ranking /
    accounting）**沒有任何一個吃日期區間**——參數收下即丟，匯出的一直是全期間資料。
    ...
    """
    if not from_date and not to_date:
        return ""
    logger.warning(
        "report export 收到未支援的日期區間 from=%s to=%s——匯出的是全期間資料",
        from_date, to_date,
    )
    return f"　⚠ 日期區間（{from_date or '不限'}～{to_date or '不限'}）尚未支援，本報表為全期間"
```

TC 判定基準寫「數字、時區與**篩選**一致」（出處：`smartlock-docs/enterprise/20_Test_Cases.md:430`）／程式碼在匯出路徑不套用日期區間篩選（`report_export_service.py:196-201` 自述）。此處僅並陳，不裁定。

另一項與篩選有關的事實：KPI 頁的自訂日期區間會被折回 enum（`kpi/page.tsx:135-139`）：

```tsx
  useEffect(() => {
    // TODO[E7x §4.3]: 後端 reports/kpi 尚未支援 from/to 參數，
    // 目前透過 mapRangeToDashboardPeriod 折回 enum 觸發 fetch。
    fetchReport(period);
  }, [period]);
```

而 `api/routers/reports_v2.py:47-54` 的 `getReportKpi` 實際上有宣告 `start_date` / `end_date` 兩個 query 參數，`api/services/kpi_service.py:48-53` 也有對應的 `_date_range_clause`。

### 步驟 3 — 時區

- **動作**：搜尋時區正規化
- **預期**：畫面、API、匯出採同一時區基準
- **實際**：api 與 brand-portal 原始碼、SQL 內 `Asia/Taipei` 零命中

```
git grep -rn "Asia/Taipei" -- api web/brand-portal/src SQL
（無輸出）
```

觀測到的三個各自獨立的時間基準：

1. 期間過濾用 DB 的 `NOW()`（`api/services/kpi_service.py:40-45`）：

```python
def _period_clause(alias: str) -> str:
    return (
        f"{alias}.created_at >= "
        f"CASE WHEN %s = '0 days' THEN date_trunc('day', NOW()) "
        f"ELSE NOW() - %s::interval END"
    )
```

2. `generated_at` 為 UTC（`api/services/kpi_service.py` 之 `get_kpi_report` 回傳字典）：

```python
        "generated_at": datetime.now(timezone.utc).isoformat(),
```

匯出檔名時間戳同樣為 UTC（`api/services/report_export_service.py:67-68`）：

```python
def now_utc() -> datetime:
    return datetime.now(timezone.utc)
```

3. 前端以瀏覽器本地時區渲染（`web/brand-portal/src/app/admin/reports/kpi/page.tsx:42-46`）：

```tsx
function formatGeneratedAt(iso: string | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")} ${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
}
```

日期區間亦以瀏覽器本地日曆日產生（`web/brand-portal/src/lib/dateRange.ts:11`「『日』是 calendar day（local timezone）」、`:49-51` `startOfDay`）。

三者是否一致取決於 DB session 時區與瀏覽器時區的實際設定，原始碼中無明示；`api/core/db.py` 對 `TimeZone` / `timezone` 零命中。此項**無法靜態判定**。

### 步驟 4 — 低權角色讀敏感報表

- **動作**：比對各報表端點的角色閘門與前端路由政策
- **預期**：cs 403
- **實際**：報表端點閘門為 `OPS_ROLES`，不含 `customer_service`

`api/core/deps.py:293-299`

```python
FULL_ACCESS_ROLES: tuple[str, ...] = ("admin",)
#: 營運後台寫入（accounting / billing / pricing / vendor-mgmt / warranty / 結算）
OPS_ROLES: tuple[str, ...] = FULL_ACCESS_ROLES + ("operations_manager",)
#: 派工寫入（dispatch / 自動媒合 / 技師生命週期管理）
DISPATCH_ROLES: tuple[str, ...] = OPS_ROLES + ("dispatcher",)
#: 後台唯讀／一般後台操作（含客服）
BACKOFFICE_ROLES: tuple[str, ...] = DISPATCH_ROLES + ("customer_service",)
```

`api/core/deps.py:319-325`

```python
        user = await require_tenant(request, authorization, x_tenant_id)
        if roles and user.role not in roles:
            raise ApiError(
                error_code="FORBIDDEN",
                message=f"Requires one of roles: {', '.join(roles)}",
                status_code=403,
            )
```

各報表相關端點的閘門：

| 端點 | operation_id | 閘門 | 程式碼落點 |
|---|---|---|---|
| `GET /tenants/{id}/reports/kpi` | `getReportKpi` | `OPS_ROLES` | `api/routers/reports_v2.py:55` |
| `GET /tenants/{id}/reports/revenue` | `getReportRevenue` | `OPS_ROLES` | `api/routers/reports_v2.py:97` |
| `GET /tenants/{id}/reports/export` | `exportReportV2` | `admin` / `operations_manager` / `accountant` | `api/routers/reports_v2.py:29`、`:144` |
| `GET /reports/kpi`（legacy） | `getKpiReport` | `OPS_ROLES` | `api/routers/reports_kpi.py:40` |
| `GET /reports/export`（legacy） | `exportReport` | `admin` / `operations_manager` / `accountant` | `api/routers/reports_export.py:26`、`:50` |
| 營運 KPI | `getOperationalKpiReport` | `OPS_ROLES` | `api/routers/reports_operational_kpi.py:33` |
| 客戶滿意度 | `getCustomerSatisfactionReport` | `OPS_ROLES` | `api/routers/reports_customer_satisfaction.py:40` |
| 儀表板統計 | `getDashboardStatsV2` | `BACKOFFICE_ROLES` + `reviewer`（含 `customer_service`） | `api/routers/dashboard_v2.py:41` |
| 報表排程建立／取消 | `createScheduledReport` / `cancelScheduledReport` | `OPS_ROLES` | `api/routers/scheduled_reports_v2.py:41`、`:95` |
| 報表排程列表 | `listScheduledReports` | `require_tenant`（無角色閘門） | `api/routers/scheduled_reports_v2.py:71` |

`api/routers/scheduled_reports_v2.py:67-71`

```python
async def list_scheduled_reports(
    tenantId: str = Path(...),
    report_type: str | None = Query(default=None),
    active_only: bool = Query(default=True),
    user: CurrentUser = Depends(require_tenant),
) -> dict:
```

前端路由政策（`web/brand-portal/src/lib/rolePolicy.ts:56`）：

```ts
  { prefix: "/admin/reports", roles: ["admin", "operations_manager"] },
```

### 步驟 5 — 失敗時的畫面狀態

- **動作**：讀前端錯誤路徑與快取隔離
- **預期**：失敗時不留舊資料
- **實際**：快取層有 tenant 隔離且失敗不入快取；頁面層的 `catch` 不清既有資料

快取鍵含 tenant（`web/brand-portal/src/lib/api.ts:471-474`）：

```ts
  const tenant = auth.getTenantId();
  const fullUrl = buildUrl(path, options.query);
  const key = `GET:${fullUrl}:${tenant}`;
  return cacheGet<T>(key, () => rawRequest<T>(method, path, options));
```

失敗不入快取（`web/brand-portal/src/lib/cache.ts:70-73`）：

```ts
    .catch(() => {
      // 失敗的 promise 不該被快取 — 移除讓下次 query 重試
      if (cache.get(key) === entry) cache.delete(key);
    });
```

登出清全部 GET 快取（`web/brand-portal/src/lib/api.ts:809-812`）：

```ts
  } finally {
    auth.clear();
    // 清掉所有 GET cache，避免下次登入讀到上一個帳號的資料
    cacheClear();
  }
```

頁面層（`web/brand-portal/src/app/admin/reports/kpi/page.tsx:126-132`）：

```tsx
    } catch (e) {
      setError(
        friendlyError(e),
      );
    } finally {
      setLoading(false);
    }
```

`setReport(null)` 在 `catch` 分支不存在；`report` 保留前一次成功的值，而畫面的漏斗／異常率／技師效率三張卡片皆以 `report?.` 讀取（`:141`、`:322-338`、`:354-371`）。營收頁（`revenue/page.tsx:167-171`）與技師排行頁（`technician-ranking/page.tsx:150-155`）的 `catch` 為同型。

`auth.setTenantId` 在四站台各定義一次（`web/brand-portal/src/lib/api.ts:167` 等），但 `web/` 下無任何呼叫端：

```
git grep -rn "auth.setTenantId\|setTenantId(" -- web
web/brand-portal/src/lib/api.ts:167:  setTenantId(tenantId: string) {
web/landing/src/lib/api.ts:151:  setTenantId(tenantId: string) {
web/platform-console/src/lib/api.ts:157:  setTenantId(tenantId: string) {
web/tech-portal/src/lib/api.ts:157:  setTenantId(tenantId: string) {
```

即 session 內無切換租戶的入口，tenant 來源為登入時由 JWT payload 寫入的 claims cookie（`api.ts:151-166`）。claims cookie 讀不到時，`getTenantId` 退回硬編常數（`api.ts:144`、`:149`）：

```ts
export const FALLBACK_TENANT_ID = "00000000-0000-0000-0000-000000000001";

export const auth = {
  ...
  getTenantId: () => readClaimsCookie()?.tenantId ?? FALLBACK_TENANT_ID,
```

該檔 `:140-142` 附有 TODO：「正式環境理應在無有效 tenant 時擋下並導回登入，而非靜默退回 1 號租戶（多租戶資料外洩風險）……本次只做『集中字面量』不改 runtime 行為」。

### 步驟 6 — 執行既有測試

- **動作**：跑報表／儀表板既有測試
- **預期**：取得執行證據
- **實際**：31 項全數通過

```
cd api && POSTGRES_URI=<本機測試庫> python -m pytest \
  tests/test_reports_v2_endpoint.py tests/test_export_report.py \
  tests/test_operational_kpi.py tests/test_dashboard_v2_endpoint.py \
  tests/test_cr_0088_dashboard_summary.py -q -p winloop_plugin
31 passed in 2.71s
```

`api/tests/test_reports_v2_endpoint.py` 的六個案例為 200 結構驗證與 cross-tenant 403（`:7-9`、`:81-88`、`:119-126`、`:158-165`），**無**「低權角色（cs）讀報表回 403」的案例；grep `customer_service` 於該檔零命中。

---

## 觀測到的其他事實

- `brand-portal` 的 `api.ts` 對 `timeout` / `AbortController` 零命中（僅 `:54` 有 `signal?: AbortSignal` 型別欄位），無 client 端逾時上限；TC 步驟「令 API timeout」時的畫面行為需執行期觀測。
- `GET` 有 30 秒 staleTime 共享快取（`web/brand-portal/src/lib/cache.ts:27` `DEFAULT_STALE_MS = 30_000`），非 GET 請求成功後預設清空全部 GET 快取（`api.ts:459-466`）。
- KPI 頁的 SLA／滿意度／NPS 區塊由 `UAT_HIDE_FAKE_FLOWS` 旗標隱藏（`kpi/page.tsx:377`，註解「UAT 隱藏(20260702 決議 7):SLA/滿意度/NPS 為待接入佔位塊」）。
- `smartlock-docs/enterprise/20_Test_Cases.md:95` 記載 FR-WEB-04 的追溯狀態為「⚠ 完全沒有案例」，同檔 `:430` 又列有 TC-WEB-REPORT-01 一列。
- `api/services/kpi_service.py:262-320` 的 `get_kpi_report` 在提供 `start_date`／`end_date` 時仍原樣回傳呼叫端送入的 `period` 值，程式碼註解自述原因為「schema 限制：DashboardPeriod enum 沒有 "custom"」。
