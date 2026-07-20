---
id: CR-0172
title: 技師派工推播改走 outbox（送達保證）
status: in-progress
type: change-impact-analysis
date: 2026-07-20
related-findings: R10（codegraph LINE 推播稽核）
source-report: .claude/context/decisions/codegraph-tech-line-push-trace-2026-07-20.md
---

# CR-0172 技師派工推播改走 outbox（送達保證）

## 1. 背景與動機（WHY）

2026-07-20 codegraph LINE 推播全鏈稽核（source-report S3 段 + 風險登記表 R10）確認：**技師派工推播無持久重試與送達保證**，與客戶側推播的可靠性明顯不對稱。

現況（皆經 Read 核對，行號為驗證當下）：

- `_notify_tech_line`（`api/services/work_order_service.py:1394`）以 `aiohttp.ClientSession` fire-and-forget `POST` 到 tech-portal 內部端點（`f"{base.rstrip('/')}{path}"`，header `X-Internal-Token`，`work_order_service.py:1409-1413`），**連 HTTP status code 都不讀**；例外只 `logger.warning(... exc_info=True)` fail-soft（`:1414-1415`）。無重試、無持久化、無送達確認。
- 收端 `_push`（`api/services/technician_line_service.py:134`）僅有 process 內 backoff（`range(3)` = 3 次嘗試 / 2 次重試，且只對 429/500/502/503 重試）。一旦 LINE 連續 5xx 或逾時耗盡三次，該指派通知**直接遺失**。
- 呼叫端三處：`assign_order`（`work_order_service.py:2009`，path `/api/v1/internal/technicians/notify-assign`）、`reassign_order`（`:2136`）、建單/池單（`:615` → notify-pool 迴圈廣播）。
- 對照組：**同檔所有客戶側 LINE 推播**（`work_order_assigned` / `work_order_accepted` / `work_order_document` / `scope_change_result` / `reschedule_proposal` / `schedule_conflict` / `quote_proposal` 等）皆走 `line_push_outbox_service.enqueue`（`api/services/line_push_outbox_service.py:51`），由 CR-0017 outbox worker（`api/realtime/line_push_outbox_worker.py`）以 `FOR UPDATE SKIP LOCKED` 輪詢 + 指數退避 + `max_attempts` dead 佇列保證投遞。

**不做的後果**：技師派工鏈違反 HD-3「指派必推」的可靠性承諾——雲端漏烤 env（R8）、LINE 短暫抖動、或 tech-portal 端點瞬斷，都會讓「新工單已派給你」通知靜默消失，技師不知有新單、主流程無錯浮現，只能靠網頁通知中心保底。這與已投入 outbox 佇列基建的客戶側形成不對稱可靠性缺口。

## 2. 變更範圍（WHAT）

將技師派工推播（assign / reassign，池單另議見 §8）從**同步 fire-and-forget HTTP** 改為**經 `line_push_outbox` 佇列的持久化投遞**，複用 CR-0017 outbox worker 的重試 / 退避 / dead-letter 機制，取得與客戶側對等的送達保證。

建議方案骨幹（源自 source-report R10 建議欄，實作細節待 §8 裁決）：

1. `line_push_outbox_service` 的 `PushKind` literal（`line_push_outbox_service.py:33-45`）新增技師派工 kind（命名待裁決，暫記 `tech_dispatch_assigned`）。
2. `enqueue` 時 `reference_table='work_orders'`、`reference_id=wo_id`、`payload` 帶 `technician_id` + `_tech_line_wo_summary(result)`（`work_order_service.py:1383`，已做 PII 最小化）。
3. **outbox worker 依 push_kind 分派**：客戶側 kind 維持現行「反查 `users.line_user_id` → 直推 `api.line.me`」；技師側 kind 改走技師投遞管道（投 tech-portal 內部端點 or 反查 `technicians.line_user_id`——**這是本 CIA 最關鍵的架構岔路，見 §6 / §8**）。
4. `assign_order`（`:2009`）/ `reassign_order`（`:2136`）兩處 `await _notify_tech_line(...)` 改為 `await line_push_outbox_service.enqueue(...)`，維持 fail-soft（enqueue 失敗 `logger.exception` non-fatal，比照客戶側），並以 env flag 灰度。

## 3. CIA 觸發面向

| 面向 | 命中 | 說明 |
|---|---|---|
| **Architecture boundary** | ✅ | outbox worker 目前**只投遞客戶側 LINE**（反查 `users.line_user_id` → `api.line.me`，用 `LINE_CHANNEL_ACCESS_TOKEN`）。技師派工的目標是 tech-portal 內部端點（`X-Internal-Token`）+ 技師官方號（`PLATFORM_LINE_CHANNEL_ACCESS_TOKEN`）+ 技師權威庫（`technicians.line_user_id`，走 `require_tech_conn`）。讓 worker 能路由到技師管道，是佇列/worker 分派架構的擴張。 |
| **External integration** | ✅ | 牽涉兩個不同 LINE channel（客戶官方號 vs 技師官方號）、跨 service HTTP 契約（worker ↔ tech-portal 內部端點的 payload schema / token 傳遞 / 重試去重語意）需重新定義。 |
| **DB schema** | ⚠️ 部分 | `push_kind` 為 `VARCHAR(40)` **無 CHECK 約束**（`Schema_v2_extensions.sql:424`，唯一 CHECK 是 `chk_push_status` 針對 status，`:437`），故**新增 push_kind 值不需 migration**。**唯有**若一併加冪等去重唯一鍵（見 §5 / §8）才需 migration。 |
| **API contract** | ⚠️ 部分 | 對外 REST endpoint 不變；tech-portal 內部端點 `/api/v1/internal/technicians/notify-assign` 的 payload 契約若因 worker 改投而調整，屬內部契約。 |
| **Test plan** | ✅ | 需擴充 outbox worker 分派測試 + 技師 enqueue 測試（見 §7）。 |
| **Domain model** | ❌ | 不新增 entity；`line_push_outbox` row 語意擴充（納入技師收件人）屬既有 entity 延伸，非新概念。 |
| **User flow / Business flow** | ❌ | 派工業務流程不變，僅通知投遞機制由同步改非同步。 |

依 `.claude/rules/change-governance.md`，命中 Architecture boundary + External integration（+ 條件式 DB schema）即須走 CIA gate、等業主裁決後實作。

## 4. API contract 影響

- **對外 REST endpoint**：無變動。`assign_work_order_v2`（`api/routers/work_orders_v2.py:402`）/ `reassign_work_order_v2`（`:576`）request/response schema 不變。
- **tech-portal 內部端點**：`POST /api/v1/internal/technicians/notify-assign`（`internal_notify_assign` @ `api/routers/technician_line.py:166`，`Depends(require_internal_token)`）與 `/notify-pool`（`:181`）——
  - 若採 §8 方案 A（worker 改投內部端點）：端點與現行契約**不變**，僅呼叫者由 `work_order_service` 內同步呼叫改為 outbox worker；payload（`technician_id` + `work_order` summary）維持。
  - 若採方案 B（worker 直推 LINE）：此二內部端點在技師鏈中**不再被呼叫**（可能廢用），屬內部契約破壞。
- `line_push_outbox_service.enqueue` 簽章（`line_push_outbox_service.py:51-60`）**不變**——現有 `push_kind` / `payload` / `reference_id` / `reference_table` / `target_line_id` 參數足以承載技師派工，僅 `PushKind` literal 擴充一個成員。

## 5. Domain model / DB schema 影響

- **entity**：無新增。`line_push_outbox`（`Schema_v2_extensions.sql:421`）沿用；技師派工 row 與客戶 row 同表，靠 `push_kind` 區分。
- **push_kind 新值**：`VARCHAR(40)` 無 CHECK（`:424` 註解與 `line_push_outbox_service.py:32` 均明載「新增 kind 不需 migration」），**故新增技師 kind 零 migration**。同步更新 `line_push_outbox.push_kind` 的 `COMMENT`（`:442`）為佳但非必要。
- **target_line_id**：`VARCHAR(40)`（`:425`）存 LINE userId，可 NULL。技師若走方案 A（內部端點），`target_line_id` 留 NULL、由 tech-portal 端點自行反查 `technicians.line_user_id`；若走方案 B，worker 需反查技師庫填入。
- **冪等去重（可選，R11/R13 連動）**：現行 outbox **無** `(reference_id, push_kind)` 去重（無條件 INSERT，`line_push_outbox_service.py:87`）。若本 CR 一併加技師派工去重（如唯一鍵 `(reference_id, push_kind, technician_id)`），**需新增唯一索引/migration**；因 payload 內的 `technician_id` 目前不是欄位，去重鍵設計須另議（見 §8）。
- **回填**：無歷史資料回填需求（僅影響切換後的新推播）。

## 6. External integration 影響

核心岔路（source-report S3 斷點 + §5 對照表指出的兩側差異）：

- **兩個不同 LINE channel**：客戶側 outbox worker 用 `LINE_CHANNEL_ACCESS_TOKEN` 直推客戶官方號（`line_push_outbox_worker.py:240`）；技師側 `_push` 用 `PLATFORM_LINE_CHANNEL_ACCESS_TOKEN` 推技師官方號（`technician_line_service.py:134`）。**兩者不可混用同一 token**。
- **兩個收件人來源**：客戶 = `users.line_user_id`（主庫，worker `_resolve_line_uid` 現行唯一支援路徑，`line_push_outbox_worker.py:156-224` 全部 JOIN 到 `users`）；技師 = `technicians.line_user_id`（技師權威庫，須 `require_tech_conn`，`technician_line_service.py:194`）。**worker 現行 `_resolve_line_uid` 完全沒有技師反查路徑**。
- **方案 A（建議）**：worker 對技師 kind 改投 tech-portal 內部端點（複用現有 `X-Internal-Token` + header strip 邏輯 `work_order_service.py:1397-1400` 的防護），由端點沿用現行 `notify_assignment` → 反查技師庫 → `_push` 技師官方號。優點：不讓 worker 依賴技師庫與技師 channel token，維持現行雙 deployment 邊界；worker 只多一個「投遞目標 = HTTP 內部端點」的分支。
- **方案 B**：worker 直接反查 `technicians.line_user_id`（跨庫 `require_tech_conn`）+ 用 `PLATFORM_LINE_CHANNEL_ACCESS_TOKEN` 直推 `api.line.me`。優點：少一跳 HTTP；缺點：worker 耦合技師庫與第二個 LINE channel token，跨越原本的 service 邊界。
- **token 換行病根（R9/R2 連動，非本 CR 主體但同源）**：無論哪案，internal token / channel token 讀入的 `.strip()` 需維持；建議收斂為單一 helper（另 CR 處理）。

## 7. 測試計畫影響

現有相關測試（source-report `test_files`）：

- `api/tests/test_cr_0017_outbox_worker.py` — worker 輪詢/退避/dead。**需擴充**：技師 push_kind 的分派路由（方案 A 驗「投內部端點」、方案 B 驗「反查技師庫 + 技師 channel」）。
- `api/tests/test_cr_0028_wo_push.py` — 客戶 enqueue。**需新增**平行案：技師派工 enqueue（assign / reassign 觸發、payload 帶 `technician_id` + summary、reference 正確）。
- `api/tests/test_cr_0169_line_bind.py` — 技師綁定。回歸確認綁定→派工推播鏈端到端。

關鍵新增案例：

1. `assign_order` / `reassign_order` 觸發後，`line_push_outbox` 出現對應技師 kind 的 pending row（flag 開啟時）。
2. **無 worker / flag 關閉時仍 fail-soft**：enqueue 失敗或本機無 worker，不阻斷派單主流程（比照客戶側 `logger.exception` non-fatal）。
3. worker 對技師 kind 的投遞分派正確（不誤走客戶 `users` 反查路徑而 `_mark_failed('cannot resolve LINE userId')`）。
4. 冪等（若採 §8 去重）：重覆 assign 同工單同技師不產生重複 pending row / 重複推播。
5. 灰度回退：flag 關閉時走舊 `_notify_tech_line` 同步路徑，行為與現況一致。

## 8. 🛑 Human Decisions Required（待業主裁決）

實作前必須有答案：

- **HD-A（投遞管道，最關鍵）**：技師派工納入 outbox 後，worker 用哪個管道投遞？
  - 選項 A（建議）：worker 對技師 kind 改投 **tech-portal 內部端點**（`/api/v1/internal/technicians/notify-assign`，複用 `X-Internal-Token`），由端點沿用現行技師庫反查 + 技師官方號推播。維持 service 邊界，不讓 worker 碰技師庫/第二 channel token。
  - 選項 B：worker **直接反查 `technicians.line_user_id`（跨庫）+ 用 `PLATFORM_LINE_CHANNEL_ACCESS_TOKEN` 直推 LINE**。少一跳，但 worker 耦合技師庫與技師 channel。
  - 建議：**A**。

- **HD-B（push_kind 命名）**：新增幾個技師 kind、如何命名？assign 與 reassign 是否共用單一 kind（如 `tech_dispatch_assigned`）還是分開（`tech_dispatch_assigned` / `tech_dispatch_reassigned`）？建議單一 `tech_dispatch_assigned`（reassign 語意上仍是「指派給你」），池單另立 `tech_dispatch_pool`。

- **HD-C（收件人在 outbox 的承載方式）**：技師收件人以 (a) `payload.technician_id` 由投遞端反查（配方案 A 自然），還是 (b) enqueue 時就把 `technicians.line_user_id` 填入 `target_line_id`（配方案 B）？注意現行 `reference_table='work_orders'` 的 worker 反查語意是**客戶 `users.line_user_id`**（`line_push_outbox_worker.py:174-184`），技師鏈**不可**共用該反查——需靠 `push_kind` 分派避開，或使用不同 `reference_table` 值。請裁決 `reference_table` 用 `'work_orders'`（靠 kind 分流）或新值。

- **HD-D（冪等去重範圍）**：本 CR 是否一併補技師派工冪等去重（R11）？若是，去重鍵 `(reference_id=work_order_id, push_kind, technician_id)` 需要唯一索引 migration，且 `technician_id` 目前僅在 payload、非欄位——是否為此加欄位或改用 partial index on payload？建議：**本 CR 先只做送達保證，去重另開 CR**（避免範圍膨脹），僅在切換點保留現有 router `idempotency_guard` 行為。

- **HD-E（池單廣播是否納入本 CR）**：`notify-pool`（`work_order_service.py:615` → `notify_pool_new` 迴圈序列 `await _push`，`technician_line_service.py:222-224`，R12 同步阻塞）是否本輪一併改 outbox？一筆工單 → N 技師的映射需決定「一 row 廣播」或「N rows 各投一技師」。建議：**本 CR 只做 assign/reassign 單點推播，池單廣播另議**（其 N-fan-out 語意較複雜）。

- **HD-F（灰度與回退開關）**：是否引入 env flag（暫記 `TECH_DISPATCH_VIA_OUTBOX`，預設 `false` 走舊同步路徑）作為灰度與即時回退？建議：**是**，穩定後再移除舊 `_notify_tech_line` 直推路徑。

## 9. Suggested Implementation Order

每步可獨立 review / revert：

1. **S1 — worker 技師分派路由（先上線，零副作用）**：在 `line_push_outbox_worker._process_row`（`line_push_outbox_worker.py:112`）依 `push_kind` 加技師分派分支（依 HD-A 落地：投內部端點 or 反查技師庫直推）。此時尚無技師 kind 的 row，**先部署 worker 不影響現況**（避免 R10 risk 所述「入庫但永不投遞」的更糟狀態）。含單元測試。
2. **S2 — enqueue 支援技師 kind**：`PushKind` literal（`line_push_outbox_service.py:33-45`）加技師 kind（HD-B）；補一個技師 enqueue helper（帶 `technician_id` + `_tech_line_wo_summary`）。`push_kind` 無 CHECK，**無 migration**。含測試。
3. **S3 — 切換 assign/reassign（flag 灰度）**：`assign_order`（`work_order_service.py:2009`）/ `reassign_order`（`:2136`）的 `await _notify_tech_line(...)` 在 flag 開啟時改走 `enqueue`，關閉時維持舊路徑（HD-F）。保 fail-soft（`logger.exception` non-fatal）。含 e2e 測試。
4. **S4 —（可選）池單納入**：依 HD-E 決定；若納入則設計 N-fan-out。
5. **S5 —（可選）冪等去重 migration**：依 HD-D 決定；若做則加唯一索引 + 回歸測試。
6. **S6 — 移除舊直推路徑**：flag 全開穩定一段後，刪除 `_notify_tech_line` 的技師派工呼叫點（保留函式若 pool 仍用），收斂為單一 outbox 路徑。

> 三處 audit trail 同步（`.claude/rules` 要求）：本 CR §8 進度區塊、`CHANGELOG.md [Unreleased]`、若確立 worker 分派架構則新開 ADR（append-only）。

## 10. 風險與回退

- **破壞性**：無對外 API 破壞。方案 B 會使 tech-portal 內部端點在技師鏈中廢用（內部契約破壞）；方案 A 無此問題。
- **最大實作雷（source-report R10 risk）**：若**先切 enqueue（S3）而 worker 尚無技師分派（S1）**，技師 kind 的 row 會入庫但永不投遞——比現況更糟（靜默丟失且無 log，且不像現況至少有 `logger.warning`）。**故實作順序 S1 必須先於 S3，不可顛倒。**
- **呼叫端連動**：`_notify_tech_line` 亦被建單/池單（`work_order_service.py:615`）呼叫；任何簽名/行為變更需同步 assign（`:2009`）/ reassign（`:2136`）/ pool（`:615`）三處，避免漏改。
- **跨 channel/庫誤用**：worker 若誤把技師 kind 走客戶 `users` 反查路徑（`_resolve_line_uid`）→ 反查不到 → 白重試至 dead（R15 同型）。分派分支需以 `push_kind` 明確攔截，測試案例 3 專驗此點。
- **灰度**：env flag `TECH_DISPATCH_VIA_OUTBOX`（HD-F）預設 `false`；出問題即刻設回 `false` 回退舊 fire-and-forget，無需回滾部署。
- **本機可用性**：本機無 outbox worker 時，enqueue 仍 fail-soft 不阻斷派單（比照客戶側），且 flag 預設關閉時走舊路徑，保本地開發不受影響。
- **[待確認]**：雲端技師鏈是否確為「品牌 api → tech api 兩個 deployment」（source-report S3 斷點標為靜態圖斷、雲端可能跨 deployment）——若是，方案 A 的 worker→內部端點跳仍跨 deployment，需確認 worker 所在 service 能觸達 tech-portal 內部端點的網路路徑與 `TECH_API_BASE_URL` 配置。

## 11. 進度（實作記錄）

- **§8 決策（業主 2026-07-20）**：HD-A=**A**（worker 投 tech-portal 內部端點）；其餘照建議——HD-B 單一 `tech_dispatch_assigned`、HD-C `payload.technician_id` 由端點反查、HD-D 去重不做（歸 CR-0175 機制／另議）、HD-E 池單不納入本 CR、HD-F flag `TECH_DISPATCH_VIA_OUTBOX` 預設 false。
- **實作（branch `feat/cr-0172-tech-dispatch-outbox`，§9 S1-S3）**：
  - S1 worker：`_TECH_DISPATCH_ENDPOINT` 映射 ＋ `_process_row` 依 `push_kind` 分派 ＋ `_dispatch_to_tech`（POST tech-portal 內部端點，X-Internal-Token，base/token `.strip()`）。**先於 S3 上線、零副作用**（尚無技師 kind row）。
  - S2 enqueue：`PushKind` 加 `tech_dispatch_assigned`（無 CHECK、無 migration）。
  - S3 切換：`work_order_service._dispatch_tech_notify`（flag 開走 `enqueue`、關走舊 `_notify_tech_line`）替換 assign（`:2009`）/ reassign（`:2140`）呼叫；池單（`:615`）維持舊路徑（HD-E）。
- **驗證**：unit **16 passed**（worker tech 路由／客戶 kind 回歸／缺 env／flag 開關×2 ＋既有回歸）。tech 分派為 plain INSERT（非 strict dedup kind），沿用既驗的 enqueue 路徑。
- **剩餘**：S4 池單、S5 冪等、S6 移除舊路徑 依 HD-E/HD-D 或 flag 穩定後另辦；**雲端啟用＝設 `TECH_DISPATCH_VIA_OUTBOX=1`**（前提 worker 所在 service 可觸達 tech-api 內部端點，同現行同步路徑的 `TECH_API_BASE_URL` 配置；[待確認] 見 §10）。