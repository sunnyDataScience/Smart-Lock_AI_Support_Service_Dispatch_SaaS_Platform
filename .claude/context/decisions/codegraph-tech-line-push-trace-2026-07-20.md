# 技師 LINE 推播全鏈路圖（codegraph 追蹤）

> 追蹤方法：codegraph_trace / codegraph_search 產鏈，逐 edge 以 Read 核對 file:line；本報告**只收經 verify confirmed 的 edge 與 confirmed_risks**，臆測/未驗證項一律剔除。file:line 為驗證當下之行號。

---

## 1. 總覽（端到端一句話）

技師先由「LINE Platform → `POST /technicians/line-webhook` →（`PLATFORM_LINE_CHANNEL_SECRET` HMAC 驗簽）→ 6 位綁定碼 consume → 寫入 `technicians.line_user_id`」建立收件地址（**入站段 S1+S2**）；日後派工事件「`assign_work_order_v2` → `assign_order` →（`_notify_tech_line` aiohttp 帶 `X-Internal-Token` 跨 service）→ tech 側 `internal_notify_assign` → `notify_assignment` 讀出 `line_user_id` → `_push` → `api.line.me` push」以**同步 service-to-service HTTP** 把通知送達技師（**出站段 S3**）。技師派工推播**不走 outbox**；`line_push_outbox` 表 + 背景 worker（**S4+S5**）是 CR-0028「客戶」推播的平行非同步機制，易與技師鏈混淆，本報告列為對照。

---

## 2. 鏈路圖（ASCII）

```
入站 — 技師綁定（S1 HMAC + S2 consume，建立收件地址）
════════════════════════════════════════════════════════════════════
 LINE Platform ──HTTP POST──▶ /technicians/line-webhook  (line_webhook @ technician_line.py:117)
                                 │ raw = await request.body()          (:121，在 json.loads:127 之前)
                                 ▼ _verify_line_signature (:104)  HMAC-SHA256(PLATFORM_LINE_CHANNEL_SECRET)
                                 │   缺 secret/sig → return False → :124 raise 403  【fail-closed】
                                 ▼ _BIND_CODE_RE.match (:136)  ^\s*(\d{6})\s*$
                                 ▼ bind_by_code (technician_line_service.py:71)
                                 │     SELECT bind_codes(code_hash,used_at NULL,expires>NOW) JOIN technicians
                                 │     UPDATE technicians SET line_user_id ─────▶ ┌───────────────────────┐
                                 │                                                │ technicians           │
                                 ▼ reply_text ──HTTP──▶ api.line.me/reply         │  .line_user_id  (DB)  │
                                                                                  └───────────┬───────────┘
出站 — 派工推播（S3 同步 service-to-service HTTP，非 outbox）                                  │ 讀
════════════════════════════════════════════════════════════════════════════════════════════│═════
 assign_work_order_v2 ─▶ assign_order ─▶ _notify_tech_line(path, payload)                      │
   (v2:402)               (svc:1837)      (svc:1394)  base/token 各 .strip()                   │
                                            │ aiohttp POST  X-Internal-Token                   │
        ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~╎~~~ service-to-service HTTP 接縫 ~~~~~~~~~~~~~~~~~~ │
        （靜態圖斷；雲端可能 品牌api → tech api 兩個 deployment，靠 env URL + token 橋接）      │
                                            ▼ internal_notify_assign (technician_line.py:166)  │
                                            │   Depends(require_internal_token)  env未設→503    │
                                            ▼ notify_assignment (svc:191) ──────────讀─────────┘
                                            ▼ _wo_summary(:180)  區域・品牌型號(單號)，無 PII
                                            ▼ _push (svc:134) ──HTTP──▶ api.line.me/v2/bot/message/push
                                                                       Bearer PLATFORM_LINE_CHANNEL_ACCESS_TOKEN
   分支：reassign_order(svc:2136)→notify-assign  ｜ 建單/池單(svc:615)→notify-pool→notify_pool_new(svc:206) 迴圈廣播

對照 — 客戶推播（CR-0028，S4 enqueue + S5 worker，非同步 outbox；技師派工「不」走此路）
════════════════════════════════════════════════════════════════════════════════════════════
 service.enqueue (line_push_outbox_service.py:51)  INSERT ─▶ ┌────────────────────────┐
                                                             │ line_push_outbox 表     │ status=pending
        ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ │  (無 code edge，僅 DB    │
        非同步接縫：worker 靠 DB 輪詢 + 時間條件耦合          │   輪詢 + 時間條件耦合)   │
                                                             └───────────┬────────────┘
 worker._run(:60) ─leader閘(_ensure_leader:69)─▶ _poll_once(:87)  SELECT WHERE status='pending'
        AND next_attempt_at<=NOW() FOR UPDATE SKIP LOCKED ─▶ _process_row(:112)
        ─▶ _resolve_line_uid(:156, target NULL 時 JOIN 反查) ─▶ build_messages(runtime import)
        ─▶ _push_to_line(:232) ─▶ AsyncMessagingApi.push_message(:272) ──HTTP──▶ api.line.me/push
        ─▶ _mark_sent(:282) / _mark_failed(:291,指數退避) / _mark_dead(:314, max_attempts=5)
```

**非同步/跨界接縫共三處**：(a) LINE→webhook 入站 HTTP 邊界（S1/S2/S6 入口，無 caller）；(b) `_notify_tech_line` 同步 service-to-service HTTP（S3，雲端可能跨 deployment）；(c) `line_push_outbox` 表 → worker 輪詢（S4→S5，唯一非同步佇列接縫，技師派工鏈**不經此路**）。

---

## 3. 逐段細節

### S1 — 技師 webhook 進入 + HMAC 驗簽（`technician_line.py`，平台官方號）

- **Entry**：`line_webhook` @ `api/routers/technician_line.py:117`（`POST /technicians/line-webhook`，`operation_id=technicianLineWebhook`；LINE 伺服器主動 POST，靜態無 caller）
- **有序跳點（confirmed）**：
  1. `line_webhook` @ `technician_line.py:117` → `await request.body()` @ `:121` — 在 `json.loads`(:127) 之前先取 raw bytes 供 HMAC 計算。
  2. `line_webhook` @ `:122` → `_verify_line_signature` @ `:104` — 回 False 即於 `:124` `raise ApiError('FORBIDDEN','invalid signature',403)`。
  3. `_verify_line_signature` @ `:104` — `secret=PLATFORM_LINE_CHANNEL_SECRET`(:105)；缺 secret 或 signature 任一即 `return False`(:106-107，fail-closed)；`base64(HMAC-SHA256(secret, raw_body))` 與 `X-Line-Signature` 以 `hmac.compare_digest` 常數時間比對(:108-109)。
- **斷點**：入站 HTTP 邊界（entry 即接縫，無上游 caller）；段內全同步、無 queue/worker，驗簽通過後才進 S2。
- **精度校正**：breakpoint 原註「codegraph 有 3 個 `line_webhook`」計數不準——實測僅 **2 個同名函式定義**（本檔 `:117` 與對照組 `line_webhook.py:200`），同名歧義本身屬實，本段以 Read 確認未誤採 trace 結果。
- **正向（無風險，附證據）**：raw bytes 先於 json 取得(:121) + `compare_digest`(:109) → 無驗簽繞過、無 timing side-channel；`x_line_signature` 預設 None 時 `:106` 直接 False，無 None 繞過。

### S2 — 綁定碼 consume（技師↔LINE 綁定）

- **Entry**：同 `line_webhook` @ `technician_line.py:117`
- **有序跳點（confirmed）**：
  1. `line_webhook` @ `:117` — raw(:121)、驗簽(:122)、`json.loads(...).get('events')`(:127)、逐則過濾 message/text(:133-135)、`source.userId`(:137)、`replyToken`(:138)。
  2. → `_verify_line_signature` @ `:104`（同 S1）。
  3. → `_BIND_CODE_RE.match` @ `:136`（regex `^\s*(\d{6})\s*$` 定義於 `:30`；不符或缺 line_user_id 則 `:139-140` continue）。
  4. → `bind_by_code` @ `technician_line_service.py:71` — SELECT `technician_line_bind_codes`(code_hash + used_at IS NULL + expires_at>NOW) JOIN `technicians`(:74-80) → UPDATE `technicians` SET line_user_id(:85-88) → UPDATE bind_codes SET used_at=NOW(:89-92) → 回 `{technician_id,name}` 或 None。
  5. → `_hash_code` @ `:36`（`SHA-256(code.strip()).hexdigest()`；DB 只存 code_hash，明文不落庫）。
  6. → `require_tech_conn` @ `core/db.py:222`（技師權威庫連線，`tech_db_enabled` 否則 fallback 主連線；全部 DML 走此連線）。
  7. → `reply_text` @ `:161`（aiohttp `POST api.line.me/v2/bot/message/reply`；缺 `PLATFORM_LINE_CHANNEL_ACCESS_TOKEN`(:163-165) 或 ClientError(:176-177) 靜默回 False）。
- **斷點**：入站 HTTP 邊界；**簽發↔消費跨兩次 HTTP 請求靠 `technician_line_bind_codes` 表 row 狀態橋接**（`issue_bind_code` @ `technician_line_service.py:51`，`POST /technicians/me/line-bind-code` 寫 code_hash）；`reply_text`/`_push` aiohttp 外呼為網路接縫；**同名客戶側鏈勿混**：`consume_link_token` @ `line_binding_service.py:96` 寫 `saas.line_binding`、含 tenant 唯一性(409)，與本技師鏈無 call edge。

### S3 — 派工觸發技師推播（assign / reassign / 池單，同步 HTTP）

- **Entry**：`assign_work_order_v2` @ `api/routers/work_orders_v2.py:402`（`:assign`；改派 `reassign_work_order_v2` @ `:576`；池單為建單流程 `work_order_service.py:615`；v1 對應 `work_orders.py:175`）
- **有序跳點（confirmed）**：
  1. `assign_work_order_v2` @ `work_orders_v2.py:402` → `assign_order` @ `:418`（RBAC `role_required(*_DISPATCH_ALLOWED_ROLES, fail_closed=True)`@410 + `_cross_tenant_write`@413 + `idempotency_guard`@411）。
  2. `assign_order` @ `work_order_service.py:1837`（狀態機 `created|assigned→assigned`）→ `_tech_line_wo_summary(result)` @ `:2007` + `_notify_tech_line('/api/v1/internal/technicians/notify-assign', ...)` @ `:2005`（無條件發、無 dedup key）。
  3. `_tech_line_wo_summary` @ `:1383` — 只放 id/document_number/district/brand/model，無 PII（註解引 CIA §4）。
  4. `_notify_tech_line` @ `:1394` — aiohttp `session.post` 到 `{base.rstrip('/')}{path}`，header `X-Internal-Token`；base/token 各 `.strip()`(:1397-1398)；base 或 token 空即 `return` no-op(:1399-1400)；例外 fail-soft(:1410)。**注意**：此為泛用 `_notify_tech_line(path, payload)`，URL path 由呼叫端傳入（assign/reassign 傳 notify-assign、建單傳 notify-pool），非函式內硬編。
  5. `internal_notify_assign` @ `technician_line.py:166`（`dependencies=[Depends(require_internal_token)]`@164）→ `notify_assignment` @ `:167`。
  6. `notify_assignment` @ `technician_line_service.py:191` → `require_tech_conn` + `SELECT line_user_id FROM technicians`(:194-195)，未綁定 return False(:197-198)，`_wo_summary` + `_push`，深連結 `/my-orders`(:201)。
  7. `_wo_summary` @ `:180`（區域・品牌型號(單號)，無 PII）。
  8. `_push` @ `:134` → `POST api.line.me/v2/bot/message/push`，Bearer `PLATFORM_LINE_CHANNEL_ACCESS_TOKEN`；缺 token no-op False(:137-139)；`for attempt in range(3)`(:142)，僅 status∈(429,500,502,503) 且 attempt<2 才重試(:149)。
  9. `require_internal_token` @ `core/deps.py:322` → `INTERNAL_API_TOKEN.strip()`(:336)，env 未設 fail-closed 503(:337-341)，incoming `.strip()`(:343) + `hmac.compare_digest`(:344，不符 401)。
  - 分支：`reassign_order` @ `:2136` → notify-assign；建單 @ `:615` → notify-pool → `internal_notify_pool` @ `technician_line.py:181` → `notify_pool_new` @ `technician_line_service.py:206`（`WHERE line_user_id IS NOT NULL AND notify_pool_new=TRUE AND status='active'`(:210-213)，迴圈序列 `await _push`(:222-224)）。
- **斷點**：`_notify_tech_line` aiohttp URL 字串 → tech 側 router 為**真實靜態斷點**（`codegraph_callees` 對 assign 回空/淺）；本機單 app、雲端可能兩 deployment，靠 env URL + internal token 橋接；`_push` 打 `api.line.me` 為外部終跳。
- **精度校正**：`_push` 重試描述應為 **3 次嘗試 / 2 次重試**（`range(3)`，docstring 自述「重試 2 次」@:135）；原鏈述「重試 3 次」多算一次，不影響風險實質。
- **非本鏈接縫（勿混）**：`assign_order` @ `:1976` 的 `line_push_outbox_service.enqueue` 是 CR-0028「**客戶**」推播（註解 @1969），走 outbox 非同步；技師推播 @ `:2005` 走同步 HTTP。

### S4 — 推播服務 + outbox enqueue（客戶推播寫入段，技師派工不經此路）

- **Entry**：`enqueue` @ `api/services/line_push_outbox_service.py:51`（`async def enqueue(*, tenant_id, push_kind, payload, target_line_id=None, reference_id=None, reference_table=None, max_attempts=5) -> str`）
- **有序跳點（confirmed）**：
  1. `enqueue` @ `:51` → `_ensure_conn` @ `core/db.py:40` — 進入首行 `if not await _ensure_conn(): raise ApiError('DB_UNAVAILABLE',...,503)`(:76-77)。
  2. → `json.dumps(payload, ensure_ascii=False)` @ `:79` — 失敗 `except (TypeError,ValueError)` → `raise ApiError('VALIDATION_ERROR',...,422)`(:80-85)。
  3. → `INSERT INTO line_push_outbox ... RETURNING id` @ `:87` — target_line_id 可 NULL（呼叫端通常不帶），status 未列入 INSERT、由 DB 預設 pending。
  4. → `cur.fetchone() → outbox_id` @ `:96` — `str(row[0])`，log `'outbox enqueue ok'`(:98-101) 後 return。
- **斷點**：**outbox 表 → worker 輪詢非同步接縫**（`worker._poll_once` @ `line_push_outbox_worker.py:87`，`FOR UPDATE SKIP LOCKED`；無 code edge）；push_kind 動態分派 `build_messages`；LINE userId 延遲反查 `_resolve_line_uid` @ `:156`；leader 分散式鎖 `_ensure_leader`（CR-0134）。
- **精度校正**：worker `_resolve_line_uid` 白名單第四項實為帶 schema 前綴的 `saas.reschedule_proposal`（work_orders/quote/scope_changes 無前綴）；失敗訊息實為 `'cannot resolve LINE userId from reference'`。

### S5 — outbox worker → LINE 送出（客戶推播送出段）

- **Entry**：`LinePushOutboxWorker._run` @ `api/realtime/line_push_outbox_worker.py:60`（main.py lifespan 拉起的背景輪詢）
- **有序跳點（confirmed）**：`_run`@60（啟動等 5s、interval 預設 10s）→ `ensure_leader` @ `core/distributed_lock.py:37`（非 leader 待命 return）→ `_poll_once`@87（SELECT `status='pending' AND next_attempt_at<=NOW() ... FOR UPDATE SKIP LOCKED`）→ `_process_row`@112 → `_resolve_line_uid`@156（target NULL 時反查 4 種 reference_table）→ `build_messages` @ `templates/line_flex/builders.py:575`（runtime local import @135，unknown kind → `_mark_dead`）→ `_push_to_line`@232（讀 `LINE_CHANNEL_ACCESS_TOKEN`@240，轉 SDK 物件）→ `AsyncMessagingApi.push_message`@272（vendor SDK，實送邊界）→ `_mark_sent`@282 / `_mark_failed`@291（指數退避 30s/2m/8m/30m/2hr）/ `_mark_dead`@314（max_attempts=5）。
- **斷點**：S4→S5 非同步接縫（唯一銜接為 `_poll_once` SELECT）；leader 動態閘；`build_messages` runtime local import；`push_message` 進 vendor SDK/httpx 離開 repo。

### S6 — 消費者/品牌側 webhook（對照組，`line_webhook.py`）

- **Entry**：`line_webhook` @ `api/routers/line_webhook.py:200`（`POST /line/webhook`，專責 CR-0017 postback）
- **有序跳點（confirmed）**：`line_webhook`@200 → `request.body()`@205 → `_verify_signature`@38（失敗 raise **401**@209）→ `json.loads`（失敗 **400**@212-214）→ 迭代 events，`evt_type=='postback'` 才 `_handle_postback`@130；`_verify_signature`@38 讀 `LINE_CHANNEL_SECRET`(:40)，**缺 secret return True**(:41-43，DEV 略過)、有 secret 但無 signature return False(:44-45)；`_handle_postback`@130 依 kind 分派 → `_handle_get_progress`@87(g:p)、`_handle_binding_start`@110(b:s)、`confirm_reschedule_by_proposal`@155(r:c)、`reject_reschedule_by_proposal`@164(r:r)、`scope_change_service.respond_public`@173(s:a/s:r)；`_push_text`@51 讀 `LINE_CHANNEL_ACCESS_TOKEN`、inline `AsyncMessagingApi.push_message`（**非 outbox**，token 缺 log 略過、except 全吞）。
- **斷點**：驗簽→事件迴圈為同步鏈（無 queue）；r:c/r:r/s:a/s:r 只觸發 service，銷案回推走 service 端 outbox（本 router 內追不到，屬 service 端未於本段驗證）；g:p/b:s 的 `_push_text` 為 inline 直推例外。
- **精度校正**：段抬頭「push 走 inline」屬過度概括——inline `_push_text` **僅** g:p/b:s 兩分支；r:c/r:r/s:a/s:r 在本 router 內完全不 push。

---

## 4. 風險登記表（僅收 confirmed_risks，皆有 code 證據）

| # | 段 | 風險 | 位置（file:line） | 影響 | 建議 |
|---|---|---|---|---|---|
| R1 | S1/S2 | **缺 env fail-closed 且無告警**：`PLATFORM_LINE_CHANNEL_SECRET` 未設 → 直接 return False，webhook 對所有請求 403，本檔**無任何 logger** | `technician_line.py:106-107` | 缺 env 靜默全域失效、技師綁定全斷；對照 `line_webhook.py:208` 有 `logger.warning` | 缺 secret 時 `logger.error` + 啟動時 fail-fast 驗 env（與 R6/R14 同源） |
| R2 | S1/S2 | **Secret 尾端換行 → 簽章全滅**：`secret.encode('utf-8')` **不 strip** | `technician_line.py:108` | 從 .env/secret manager 帶入尾端 `\n` → 合法簽章一律靜默 403 | secret 讀入即 `.strip()`（**與 0719 C-5 同類、此處未修**，見下方對照） |
| R3 | S2 | **綁定碼暴力枚舉面**：SELECT 僅以 code_hash 全域查、無 tenant 條件，碼空間 10^6、TTL 10 分、無 rate limit/嘗試上限 | `technician_line_service.py:74-80` | 理論上可枚舉搶綁他人技師帳號 | 加 per-source rate limit + 嘗試次數鎖定；碼加長或綁 tenant |
| R4 | S2 | **換綁無唯一性檢查與審計**：UPDATE line_user_id 直接覆寫，未查是否已綁他技師、未記舊值 | `technician_line_service.py:86` | 兩技師 row 可持相同 line_user_id → `notify_assignment`/`notify_pool_new` 推送錯人；對照 `consume_link_token:105` 有 409 檢查、本鏈缺 | 綁前查唯一性、自動 unbind 舊綁 + 寫審計 |
| R5 | S1/S2 | **冪等缺口（綁定）**：`bind_by_code` 無去重鍵，JSON 解析失敗(:129)、處理完(:150) 皆回 200 | `technician_line.py:141` | LINE 重送同 event → used_at 已標第二次回 None → 回覆「綁定碼無效」，**UX 假失敗** | 接 event dedup（webhook_idempotency）；重送回「已綁定」而非失敗 |
| R6 | S2 | **line_user_id 明文落庫**（HD-4=a）：UPDATE 寫明文，僅 API 回傳層遮蔽尾碼 | `technician_line_service.py:86,110` | DB/日誌外洩即暴露 LINE userId（PII 邊界） | 評估加密/雜湊儲存或欄位級遮蔽 |
| R7 | S2 | **回覆 fail-soft 遮蔽失敗**：`reply_text` 缺 token 或 ClientError 靜默回 False，webhook 仍回 200 | `technician_line_service.py:164-177` | 綁定已寫入但使用者收不到確認，無從得知成功 | 回覆失敗至少 `logger.warning` + 送達監控 |
| R8 | S3 | **env 未配置=靜默無推播**：`TECH_API_BASE_URL`/`INTERNAL_API_TOKEN`/`PLATFORM_LINE_CHANNEL_ACCESS_TOKEN` 任一空即 no-op | `work_order_service.py:1399-1400`；`technician_line_service.py:137-139` | 三 env 任一漏烤入 → 技師永遠收不到、主流程無錯浮現（**cloud deploy param parity 雷**） | 啟動時 fail-fast 驗三 env；no-op 分支 `logger.error` |
| R9 | S3 | **token 尾端換行**：送端與收端皆靠 `.strip()` 才比對得過 | `work_order_service.py:1397-1398`；`core/deps.py:336,343` | 新 caller 忘 strip → aiohttp 嚴格模式拒發 / `compare_digest` 失敗（0719 C-5 曾炸） | 集中一個 `get_internal_token()` helper，禁散落 strip |
| R10 | S3 | **技師推播無持久重試/送達保證**：`_push` 僅 process 內 backoff（3 嘗試/2 重試），上層 `_notify_tech_line` fire-and-forget、連 HTTP status 都不讀 | `technician_line_service.py:142-158`；`work_order_service.py:1405-1409` | LINE 連續 5xx/逾時 → 該指派通知直接遺失，**不像客戶推播有 outbox 補償**（違 HD-3「指派必推」） | 技師派工也改走 outbox，或加落庫重試佇列 + 送達確認 |
| R11 | S3 | **無冪等/去重（推播）**：`_notify_tech_line` 每次無條件發，router `idempotency_guard` 只快取 HTTP 回應、不涵蓋 service 內推播 | `work_order_service.py:2005` | 反覆 assign/reassign/重送 → 重複推播技師 | 推播加 (work_order_id, kind) dedup key |
| R12 | S3 | **池單廣播在請求路徑內同步阻塞**：`notify_pool_new` 序列 `await _push`，建單流程 inline await 未背景化 | `technician_line_service.py:222-224`；`work_order_service.py:615` | 技師數多或 LINE 限流 → 建單 API 回應被拖長 | 廣播移背景 worker / 併發 gather + 上限 |
| R13 | S4 | **冪等缺口（enqueue）**：無條件 INSERT、無 `(reference_id, push_kind)` 去重 | `line_push_outbox_service.py:87` | 上游重入 → 同工單多筆 pending → 收重複推播 | ON CONFLICT / 唯一鍵去重 |
| R14 | S4 | **通知靜默遺失**：上游 `try/except Exception` 吞掉，`_ensure_conn` 503 / `json.dumps` 422 時 row 根本沒寫入 | `work_order_service.py:1079-1080` | 無任何重試補償、只留一行 log | enqueue 失敗改結構化告警 + 補償佇列 |
| R15 | S4/S5 | **收件人不可解析仍白重試**：target_line_id NULL 全賴 worker 反查，失敗重試到 max_attempts 才 dead | `worker:128-131`（`_resolve_line_uid:156`） | 技師未綁/非 LINE 客戶 → 浪費輪詢、延遲失敗可見性 | 反查不到即直接 `_mark_dead` 不重試 |
| R16 | S4 | **push_kind 與 reference_table 需相容**：enqueue 不校驗，白名單外 reference_table 反查不到 | `worker:156-221`（白名單含 `saas.reschedule_proposal`） | 帶未涵蓋 reference_table → 最終 dead | enqueue 端校驗 push_kind↔reference_table |
| R17 | S4 | **PII 最小化屬呼叫端自律**：enqueue 對 payload 零校驗、原封 `json.dumps` 落 JSONB | `line_push_outbox_service.py:79` | 目前技師 payload 無 PII，但無 schema/allowlist 擋未來塞入 | 加 per-kind payload allowlist |
| R18 | S5 | **缺 env 即靜默失敗**：`LINE_CHANNEL_ACCESS_TOKEN` 未設 → `_push_to_line` 回 `(False,'LINE_CHANNEL_ACCESS_TOKEN missing')` → 重試最終 dead | `worker:240-242` | 推播消失無明顯告警 | 啟動 fail-fast 驗 token（與 R8 同源） |
| R19 | S5 | **冪等缺口（送出）**：`push_message` 成功與 `_mark_sent` 為兩步、無 idempotency key | `worker:272,282` | 兩步間 crash → row 仍 pending → 下輪重送 → 技師收重複 | LINE `X-Line-Retry-Key` / 送出前預標 |
| R20 | S5 | **重試不分永久/暫時錯誤**：except 全捕，400 invalid userId 也照指數退避重試到 max | `worker:276-280` | 浪費 attempts、延誤 dead | 4xx（除 429）即永久失敗直接 dead |
| R21 | S5 | **錯誤可觀測性差**：ApiException 只回 `status=%s`，丟棄 LINE 回傳 body | `worker:276-278` | token 過期/被撤只剩 status code，排障困難 | 記錄 response body（遮敏後） |
| R22 | S5 | **事務/鎖未見 commit**：`FOR UPDATE SKIP LOCKED` 開事務、整段共用 `db_module._conn`，全檔未見顯式 commit | `worker:102` | 若非 autocommit，row 鎖與更新可見性/釋放時機存疑 | 確認 autocommit 或補逐 row commit |
| R23 | S5 | **PII 落庫**：`last_error` 存 `err[:500]`，例外訊息可能含 payload/line_uid 片段（log 端 line_uid 已 `[:8]` 截斷） | `worker:311,319` | DB 外洩暴露片段 PII | `last_error` 亦截敏 |
| R24 | S6 | **驗簽繞過（真實）**：`_verify_signature` 缺 `LINE_CHANNEL_SECRET` 直接 return True（DEV skip），webhook 放行 | `line_webhook.py:41-43` | 雲端漏設 env → `/line/webhook` 變裸端點，可偽造 postback 觸發 confirm/reject_reschedule 與 scope_change respond_public 銷案（**技師側 fail-closed、本側 fail-open**） | 生產環境缺 secret 應 fail-closed 拒絕，非放行 |
| R25 | S6 | **靜默不送達**：`_push_text` 缺 token log 略過、webhook 仍回 200 | `line_webhook.py:55-58` | 使用者收不到查進度/綁定引導，系統無感知 | 同 R7 |
| R26 | S6 | **重試/冪等缺口**：broad except 全吞、一律回 200，LINE 不 retry；service 失敗這條路靜默丟失 | `line_webhook.py:191-196` | 客戶點改期卻無反應、無重送 | service 失敗回非 2xx 讓 LINE retry，或落補償 |
| R27 | S6 | **畸形 postback ValueError**：`int(slot_idx_str)` 對畸形 r:c 落 broad except | `line_webhook.py:154` | 改期確認被靜默丟棄不重試 | 先驗數字格式、明確回錯 |
| R28 | S6 | **dead branch**：`''.split('|')` 回 `['']` 恆非空，`if not parts` 恆假 | `line_webhook.py:136-139` | 該防呆分支永不觸發（潛在誤判空 data） | 改判 `data == ''` |
| R29 | S6 | **多租戶隔離弱點**：固定用單一 `_DEFAULT_TENANT_FOR_LINE_LOOKUP` fallback 查 binding | `line_webhook.py:78-80,93` | 跨租戶同一 line_uid 誤配風險 | 由 binding 反解 tenant，勿硬編 default |

### 對照 2026-07-19 已修雲端斷點：同類殘留

- **TECH_API_BASE_URL 缺（cloud deploy param parity）**：0719 是「把 env 烤入部署腳本」的**個案修復**，**code 層的靜默 no-op 行為未動**。**同類殘留仍在**：R8（三 env 任一漏即靜默）、R1（缺 secret 403 無 log）、R14（缺 DB 連線吞例外）、R18（缺 token 靜默 dead）——凡「缺 env → 靜默/fail-soft」皆屬同源，建議統一補**啟動時 env fail-fast + no-op 分支結構化告警**，根治而非逐個 env 補烤。
- **token 換行（C-5）**：0719 已在 internal token 送/收兩端補 `.strip()`（R9 現靠此才過）。但**同類未修殘留**：**R2 的 HMAC `secret.encode('utf-8')`（`technician_line.py:108`）沒有 strip**——同一「尾端 `\n` 炸掉比對」的病根，只是換到驗簽 secret 上，仍潛伏。建議收斂為單一 `read_secret()`/`get_internal_token()` helper 統一 strip，杜絕新 caller 漏做。

---

## 5. 技師側 vs 客服/品牌側 webhook 差異（S6 對照）

| 面向 | 技師側（S1/S2）`technician_line.py` | 客服/品牌側（S6）`line_webhook.py` |
|---|---|---|
| 路由 | `POST /technicians/line-webhook`（`:117`） | `POST /line/webhook`（`:200`） |
| 處理事件 | 只處理 `message.text` 綁定碼（6 位） | 只處理 `postback`（CR-0017 reschedule/scope_change 銷案 + rich menu）；message/follow 留給 agent gateway |
| 驗簽函式 / secret | `_verify_line_signature`(:104) / `PLATFORM_LINE_CHANNEL_SECRET` | `_verify_signature`(:38) / `LINE_CHANNEL_SECRET` |
| **缺 secret 行為** | **return False → 一律 403（fail-closed）** | **return True → 放行（fail-open，DEV skip）← R24 驗簽繞過** |
| 驗簽失敗 HTTP code | **403**（`raise ApiError FORBIDDEN`） | **401**（`raise HTTPException`） |
| 出站推播機制 | 派工推播走**同步 service-to-service HTTP**（S3：`_notify_tech_line` → internal 端點 → `_push`） | rich menu(g:p/b:s) 走 **inline `_push_text` 直推 Messaging API**；r:c/r:r/s:a/s:r 銷案回推走 **service 端 outbox**（CR-0028） |
| 是否經 outbox/worker | **否**（技師派工不走 outbox；outbox 是客戶推播） | 部分是（銷案回推）、部分否（rich menu inline） |
| 綁定寫入目標 | `technicians.line_user_id`（明文，R6） | `saas.line_binding`（`consume_link_token`，含 tenant 唯一性 409） |
| 冪等處理 | 綁定無 dedup、重送回「無效」假失敗（R5） | broad except 全吞 + 回 200、LINE 不 retry（R26）；service 端 CAS 保銷案冪等（service 內部，本段未驗） |

**最關鍵的安全落差**：技師側對「缺驗簽 secret」是 **fail-closed（403 拒絕）**，客服/品牌側卻 **fail-open（return True 放行）**——後者一旦雲端漏設 `LINE_CHANNEL_SECRET`，`/line/webhook` 即成可被偽造 postback 觸發銷案的裸端點（R24），是兩側對照下最需優先收斂的不一致。