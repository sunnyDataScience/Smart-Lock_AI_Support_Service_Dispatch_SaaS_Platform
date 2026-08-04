# TC-WEB-OPS-01 — 工單時間軸技師姓名與 accepted_at

## 結果

| 項目 | 內容 |
|---|---|
| **判定** | **部分實作** |
| 走查日期 | 2026-08-04 |
| 證據型態 | 靜態原始碼走查 |
| 走查基準 | commit `2cfeca92` |
| 走查範圍 | `web/brand-portal/src/app/work-orders/[id]/page.tsx:643-830/1326-1361/2018`、`web/brand-portal/src/components/problem-cards/ResolutionTimeline.tsx:1-20`、`web/brand-portal/src/i18n/messages/zh-TW.json:750-760`、`web/shared-contract/src/api-generated.ts:11498-11520`、`api/services/technician_service.py:58-83`、`api/services/work_order_service.py:150-152/171-192/1281-1289` |
| 優先級 / 路徑類型 | P1 / happy＋例外 |

「有姓名時顯示技師全名」在原始碼中成立：時間軸以 `technician?.name` 餵入 `buildEvents`（`work-orders/[id]/page.tsx:771`），排程與接單兩個事件用 `{name}` 佔位的 i18n 文案（`zh-TW.json:753`、`:756`）。判定為「部分實作」的原因是**缺姓名時的 fallback 與 TC 描述及檔內註解不同**：後端把空姓名正規化為空字串（`api/services/technician_service.py:66` 的 `row[2] or ""`），而前端的兩層 `??`（`page.tsx:688`、`:771`）只接 `null` / `undefined`，空字串會原樣通過，導致 `techName` 為空字串、`scheduled` 事件轉用 `scheduledNoTech`（文案「尚未指派技師」，`zh-TW.json:754`），`accepted` 事件則不帶技師明細（`page.tsx:718-719`）；`page.tsx:682` 的註解則寫「fetch 未回/失敗 fallback shortId，永不空白」。另 TC 步驟提到的「問題卡時間軸」在程式碼中是固定空狀態元件，不含技師欄位（`ResolutionTimeline.tsx:7-19`）。狀態與 `accepted_at` 由同一句 UPDATE 寫入（`work_order_service.py:1283`）。畫面實際渲染結果屬執行期觀測，本次未取得。

---

## TC 原文

| 欄位 | 內容 |
|---|---|
| 章節 | 12. Web 與顯示整合案例（2026-07-23 codebase 對帳） |
| 前置 | 工單時間軸含有姓名與無姓名技師 |
| 步驟 | 開啟問題卡/工單時間軸並比對 API |
| 預期結果（判定基準） | 有姓名時顯示技師全名；缺姓名時採明確 fallback（非誤顯其他技師）；狀態與 accepted_at 時間一致 |
| 路徑類型 | happy＋例外 |
| 驗證面向 | 功能 |
| 優先級 | P1 |
| 驗證哪些需求 | FR-WEB-03 |
| 屬於哪條旅程腳本 | — |

出處：`smartlock-docs/enterprise/20_Test_Cases.md:404`。

---

## 逐條驗收條件對照

| 條件 | 程式碼落點 | 狀態 |
|---|---|---|
| 有姓名時顯示技師全名 | `work-orders/[id]/page.tsx:771` → `:687-688` → `:706-707`、`:718-719`；文案 `zh-TW.json:753`、`:756` | 一致 |
| 缺姓名時採明確 fallback | `page.tsx:688` 用 `??`，後端空姓名為 `""`（`technician_service.py:66`），空字串不觸發 shortId 分支 | 不一致（與 `page.tsx:682` 註解所述不同） |
| 非誤顯其他技師 | `page.tsx:1331-1361` 以 `order.technician_id` 為 key 單獨 fetch，失敗時 `setTechnician(null)`（`:1355`） | 一致 |
| 狀態與 accepted_at 時間一致 | `api/services/work_order_service.py:1283` 同一 UPDATE 寫 `status='accepted'` 與 `accepted_at=NOW()` | 一致 |
| accepted_at 上 envelope | `work_order_service.py:191`（SELECT）、`:150-152`（輸出） | 一致 |
| 問題卡時間軸顯示技師 | `ResolutionTimeline.tsx:7-19` 為固定空狀態，無技師欄位 | 不一致 |

---

## Event Storming

本案例為前端呈現行為，無新的 domain event。改列時間軸事件與資料來源對照：

| 時間軸事件 | 資料來源欄位 | 顯示條件 | 程式碼落點 | 程式碼實際行為 |
|---|---|---|---|---|
| created | `order.created_at` | 恆顯示 | `page.tsx:690-699` | 無技師欄位 |
| scheduled | `order.scheduled_time` | 非空 | `page.tsx:701-710` | `techName` 為真 → `scheduledWithTech`；否則 `scheduledNoTech` |
| accepted | `order.accepted_at` | 非空 | `page.tsx:712-722` | `techName` 為真 → `acceptedByTech`；否則無明細 |
| arrived | `order.actual_arrival` | 非空 | `page.tsx:724-731` | 無技師欄位 |
| completed | `order.completion_time` | 非空 | `page.tsx:733-740` | 無技師欄位 |
| lastUpdated | `order.updated_at` | 與 `created_at` 不同 | `page.tsx:742-752` | 帶翻譯後 `status` |
| 技師姓名 | `GET /tenants/{id}/technicians/{techId}` | `order.technician_id` 非空 | `page.tsx:1331-1361` | 成功 → `technician`；失敗 → `null` + `techError` |

---

## 逐層走查

### 步驟 1 — 頁面元件：時間軸如何取得技師姓名

`web/brand-portal/src/app/work-orders/[id]/page.tsx:761-771`

```tsx
function WorkTimeline({
  order,
  technician,
}: {
  order: WorkOrder | null;
  technician: Technician | null;
}) {
  const t = useTranslations("pages.workOrderDetail.timeline");
  const tCommon = useTranslations("common");
  const tStatus = useTranslations("status.workOrder");
  const events = buildEvents(order, (s) => tStatus(s), technician?.name ?? null);
```

掛載點在 `:2018`：`<WorkTimeline order={order} technician={technician} />`。

### 步驟 2 — `buildEvents` 的姓名 fallback

`web/brand-portal/src/app/work-orders/[id]/page.tsx:679-688`

```tsx
function buildEvents(
  order: WorkOrder | null,
  statusLabel: (status: string) => string,
  // CR-0178 輪次 C：技師全名（fetch 未回/失敗 fallback shortId，永不空白）
  technicianName: string | null = null,
): TimelineEvent[] {
  if (!order) return [];
  const list: TimelineEvent[] = [];
  const techName =
    technicianName ?? (order.technician_id ? order.technician_id.slice(0, 8) : null);
```

兩個事件對 `techName` 的使用（`:701-722`）：

```tsx
  if (order.scheduled_time) {
    list.push({
      color: "#F43F5E",
      badge: "schedule",
      eventKey: "scheduled",
      detailKey: techName ? "scheduledWithTech" : "scheduledNoTech",
      detailParams: techName ? { name: techName } : undefined,
      time: order.scheduled_time,
    });
  }

  // CR-0178 UAT-0720-08：技師接單事件（accepted_at 上 envelope 後可顯示）
  if (order.accepted_at) {
    list.push({
      color: "#3B82F6",
      badge: "technician",
      eventKey: "accepted",
      detailKey: techName ? "acceptedByTech" : undefined,
      detailParams: techName ? { name: techName } : undefined,
      time: order.accepted_at,
    });
  }
```

對應文案（`web/brand-portal/src/i18n/messages/zh-TW.json:753-756`）：

```json
          "scheduledWithTech": "技師 {name} 已排程",
          "scheduledNoTech": "尚未指派技師",
          "acceptedTitle": "技師接單",
          "acceptedByTech": "技師 {name} 已接單",
```

### 步驟 3 — 「無姓名技師」在契約與後端的形狀

契約中 `Technician.name` 為必填非可空字串（`web/shared-contract/src/api-generated.ts:11498-11507`）：

```ts
        Technician: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Name */
            name: string;
            /** Phone */
            phone: string;
```

後端把 DB 的 NULL 姓名正規化為空字串（`api/services/technician_service.py:64-67`）：

```python
    out: dict = {
        "id": str(row[0]),
        "name": row[2] or "",
        "phone": row[3] or "",
```

因此「無姓名技師」在 API 回應中呈現為 `name: ""`。前端 `:771` 的 `technician?.name ?? null` 與 `:688` 的 `technicianName ?? (...)` 都是 `??`（僅接 `null` / `undefined`），空字串會原樣通過並成為 `techName`，其後 `techName ? ... : ...` 判斷為 falsy。

TC 判定基準寫「缺姓名時採**明確 fallback**」（出處：`smartlock-docs/enterprise/20_Test_Cases.md:404`）／`page.tsx:682` 的註解寫「fetch 未回/失敗 fallback shortId，永不空白」／程式碼在 `name` 為空字串時走的是 `scheduledNoTech`（「尚未指派技師」）與「accepted 事件不帶明細」兩條分支，而非 shortId（`page.tsx:688`、`:706-707`、`:718-719`）。此處僅並陳，不裁定。

技師 id 前 8 碼的 shortId 分支只在 `technicianName` 嚴格為 `null` 時才生效——即 `order.technician_id` 為空、或 fetch 失敗後 `setTechnician(null)` 這兩條路徑（`:1333-1336`、`:1355`）。

### 步驟 4 — 技師資料的取得與失敗處理（是否可能誤顯其他技師）

`web/brand-portal/src/app/work-orders/[id]/page.tsx:1331-1361`

```tsx
  useEffect(() => {
    const technicianId = order?.technician_id ?? null;
    if (!technicianId) {
      setTechnician(null);
      setTechError(null);
      return;
    }
    let cancelled = false;
    setTechError(null);
    (async () => {
      try {
        const res = await api.get<TechnicianEnvelope>(
          tenantPath(`/technicians/${encodeURIComponent(technicianId)}`),
        );
        if (!cancelled) setTechnician(res.data ?? null);
      } catch (e) {
        if (cancelled) return;
        setTechError(
          e instanceof ApiError
            ? friendlyError(e)
            : e instanceof Error
              ? e.message
              : String(e),
        );
        setTechnician(null);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [order?.technician_id]);
```

effect 的依賴為 `order?.technician_id`；`technician_id` 為空時先 `setTechnician(null)`（`:1334`），fetch 失敗時亦 `setTechnician(null)`（`:1355`），並以 `cancelled` 旗標擋下過期回應（`:1338`、`:1345`、`:1359-1360`）。原始碼中不存在「沿用前一張工單技師」的路徑。

### 步驟 5 — 問題卡時間軸

`web/brand-portal/src/components/problem-cards/ResolutionTimeline.tsx:7-19`

```tsx
export default function ResolutionTimeline() {
  return (
    <div className="rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] p-6">
      <h2 className="text-[18px] font-semibold text-[var(--text-primary)]">
        解決嘗試歷程
      </h2>
      <div className="mt-4 flex h-24 items-center justify-center rounded-lg border border-dashed border-[var(--border)] bg-[var(--bg-page)]">
        <span className="text-[13px] text-[var(--text-disabled)]">
          尚無解決嘗試紀錄（診斷引擎未啟用）
        </span>
      </div>
    </div>
  );
}
```

該元件不接 props，檔頭註解（`:3-6`）自述原本的 L1/L2/L3 假信心已移除、後端 `problem_cards.attempts=[]`。掛載點為 `web/brand-portal/src/app/problem-cards/[id]/page.tsx:950`。

問題卡頁另一處出現技師姓名的區塊是自動匹配候選清單（`problem-cards/[id]/page.tsx:1145`），其 fallback 為顯性字串：

```tsx
                      {c.technician_name || "（未命名技師）"}
```

該處用的是 `||`（空字串亦觸發 fallback），與時間軸的 `??` 不同。

### 步驟 6 — 後端：狀態與 accepted_at 的一致性

`api/services/work_order_service.py:1281-1289`

```python
    _cur = await db_module._conn.execute(
        # CR-0043 Tier②：技師接單後完工細狀態進「待完工回報」（M05 Q052 起點）
        "UPDATE work_orders SET status = 'accepted', accepted_at = NOW(), "
        "  technician_id = COALESCE(%s::uuid, technician_id), "
        "  completion_status = 'pending_report', updated_at = NOW() "
        "WHERE id = %s::uuid AND status = ANY(%s)",
        (claim_tech_id, wo_id, sorted(allowed_from)),
    )
    _assert_transition_applied(_cur, allowed=allowed_from, action="接單")
```

`status` 與 `accepted_at` 為同一句 UPDATE 的兩個賦值，且帶樂觀條件 `status = ANY(%s)`。全 repo 對 `accepted_at =` 的寫入點只有此一處（`api/services/consent_service.py:120` 為 `work_order_consents` 表的同名欄位，屬客戶同意書，非工單接單時間）：

```
git grep -rn "accepted_at =" -- api SQL
api/services/auth_service.py:672:    terms_accepted_at = datetime.now(timezone.utc) if terms_accepted else None
api/services/consent_service.py:120:            "  accepted = EXCLUDED.accepted, accepted_at = EXCLUDED.accepted_at, "
api/services/work_order_service.py:1283:        "UPDATE work_orders SET status = 'accepted', accepted_at = NOW(), "
```

envelope 側：SELECT 第 39 欄（`work_order_service.py:190-191`）

```python
    # CR-0178 UAT-0720-08（index 39）：技師接單時間（accept/claim 寫入，上 envelope 供時間軸）
    "wo.accepted_at"
```

輸出（`:150-152`）

```python
    # CR-0178 UAT-0720-08：技師接單時間（39）
    if len(row) > 39 and row[39] is not None:
        out["accepted_at"] = row[39].isoformat()
```

沒有任何路徑在後續狀態轉移時清空 `accepted_at`；時間軸的 accepted 事件顯示條件是 `order.accepted_at` 非空（`page.tsx:713`），與當下 `status` 無關。

---

## 既有測試證據

前端側：`git grep -rn "buildEvents\|WorkTimeline\|acceptedByTech" -- web/brand-portal/tests` 零命中，無對應既有測試；四站台 `node_modules` 均未安裝，本次未實跑前端測試。

後端側有一支直接斷言 `status` 與 `accepted_at` 同步寫入的既有測試，本次實跑通過：

```
cd api && POSTGRES_URI=<本機測試庫> python -m pytest tests/test_pool_claim_accept.py -q -p winloop_plugin
10 passed in 1.24s
```

`api/tests/test_pool_claim_accept.py:106-114`

```python
        assert out["status"] == "accepted"
        cur = await db_module._conn.execute(
            "SELECT status, technician_id, accepted_at FROM work_orders WHERE id=%s::uuid",
            (wid,),
        )
        row = await cur.fetchone()
        assert row[0] == "accepted"
        assert str(row[1]) == tech_id  # claim 寫入搶單技師
        assert row[2] is not None
```

該檔斷言的是「`accepted_at` 非空」，未斷言其與 `status` 之外的時間關係；亦無「技師姓名為空字串」的案例——該檔的 `name` 命中僅有 seed 用的 INSERT（`:33`、`:38`、`:49`）與客戶個資遮蔽斷言（`:267`、`:276`）。

---

## 事實結論

1. 時間軸的技師姓名來源是單獨的 `GET /tenants/{id}/technicians/{techId}`（`page.tsx:1342-1344`），非工單 envelope 欄位。
2. 有姓名時，排程與接單兩個事件套用 `{name}` 文案（`zh-TW.json:753`、`:756`）。
3. 後端把空姓名輸出為空字串（`technician_service.py:66`）；前端兩層 `??`（`page.tsx:688`、`:771`）不攔空字串。
4. 空字串姓名下，排程事件文案為「尚未指派技師」（`zh-TW.json:754`），接單事件無明細（`page.tsx:718-719`）。
5. shortId fallback（`page.tsx:688`）只在 `technician_id` 為空或 fetch 失敗（`:1355`）時生效。
6. 技師 fetch 以 `order?.technician_id` 為 effect 依賴並帶 `cancelled` 旗標（`:1338`、`:1359`），無沿用前一筆技師的路徑。
7. 問題卡頁的「解決嘗試歷程」為固定空狀態元件，不含技師與時間欄位（`ResolutionTimeline.tsx:7-19`）。
8. 問題卡頁候選技師清單用 `||` 做 fallback（`problem-cards/[id]/page.tsx:1145`），與時間軸的 `??` 行為不同。
9. `status='accepted'` 與 `accepted_at=NOW()` 為同一句 UPDATE（`work_order_service.py:1283`），全 repo 僅此一處寫入工單 `accepted_at`。
10. 時間軸事件依 `time` 由新到舊排序（`page.tsx:754-758`），排序基準為各欄位字串轉 `Date`。
11. 畫面上的實際文字、排序與 API 回應的逐欄比對屬執行期觀測，本次未取得。
