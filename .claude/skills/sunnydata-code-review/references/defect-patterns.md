# 缺陷樣式清單（review 時「該找什麼」）

> 母 skill `sunnydata-code-review` 管的是**流程紀律**（怎麼驗證、怎麼請求審查、
> 怎麼回應意見）。本檔管的是**內容**：實際該找哪些缺陷。
>
> **來源**：§A 的判準結構取自 [alibaba/open-code-review](https://github.com/alibaba/open-code-review)
> 的 Python 規則集（Apache-2.0），2026-08-02 實測後改寫並在地化。
> §B、§C 是它**沒有涵蓋**、但本專案已經踩過的類型。
>
> 每條盡量綁真實案例（附 commit）。沒有案例的條目標 `（尚未在本專案出現）`。

---

## 總原則：precision > recall

> 只在**確信是真缺陷**時提出；周邊脈絡不明就保持沉默。
> **一個誤報的代價高於一個漏報的小問題**——誤報會讓人不再相信審查結果。

- **安全與正確性**問題 → blocking
- **風格與慣用法**建議 → non-blocking，且不要跟 blocking 混在一起講

這條擺第一是有原因的：本輪 6 個 FAIL 經對抗式覆核只有 2 個成立，
另 4 個是「規格與實作用詞不同」被誤判成功能沒做。**誤報率 67%。**

---

# §A 通用 Python 缺陷

每節末尾的「不要報」條款和條目本身一樣重要——那是壓誤報率的地方。

## A1. 錯誤處理與例外

- 裸 `except:` 連 `KeyboardInterrupt`／`SystemExit` 都吞；至少要 `except Exception`，
  最好指名實際會拋的型別
- `except Exception` 仍比實際要處理的失敗更寬 → 收窄到被保護呼叫真正會拋的那幾種
- **例外被捕捉後靜默丟棄（`pass`）而未 log 或 re-raise**
  - ✅ 真實案例：轉真人 escalation 轉發失敗被吞，無 spool／重試／告警，
    使用者以為轉了其實沒轉（`898e1fbd`）
- re-raise 時遺失原始 traceback → 用 `raise NewError(...) from err`
- `try` 區塊包得比真正會失敗的那行大得多，掩蓋錯誤來源
- `assert` 用於驗證外部輸入——`python -O` 下會被整個移除

**不要報**：已由呼叫端或型別契約排除的情境。

## A2. 邊界與極端值

- 空輸入被當成非空：`xs[0]`、`max()`／`min()`、切片，未先處理空的 list／str／dict／iterator
- off-by-one 與索引越界，特別是頭尾元素
- **上游合法回 `None`，下游卻假設有值**——flag 前先 `file_read` 確認資料源
  - ✅ 真實案例：`work_orders.problem_card_id` DB 可為 NULL，Pydantic 卻宣告必填 UUID，
    一筆 NULL 讓**整支工單列表 500**（`57ce5a6b`）
- 浮點數用 `==` 比較 → 用 `math.isclose` 或明確容差
- `//` 非預期截斷；除數可能為 0
- 集合內元素型別不一致，code 卻假設同型
- `d[k]` 未處理 key 不存在（vs `d.get(k)`）

**不要報**：上游已驗證過的邊界。

## A3. 可變預設參數與共享狀態

- `def f(x=[])` / `def f(x={})`——預設值只建立一次、跨呼叫共享。改用 `None` 在函式體內建
- class 層級的可變屬性被非預期地跨實例共享
- module 層級的可變全域（list／dict／cache）跨 request 或 thread 被改動
- closure 以參照捕捉迴圈變數，最後全部看到最終值

**不要報**：函式從不改動該參數，或那個共享預設是**刻意且有註解**的 cache／sentinel。

## A4. 資源管理

- 檔案、socket、鎖、DB 連線未用 `with`，early return 或例外時洩漏
- 有 context manager 卻改用手動 `open()`／`close()`
- `try` 取得資源但 `finally` 的清理在錯誤路徑上缺漏或不完整

**不要報**：短命腳本，或已被外層 `with`／框架生命週期管理的 handle
（flag 前用 `file_read` 確認外層 scope）。

## A5. 併發與 async

**只在有多執行緒／多行程／async 呼叫證據時才提**（先確認呼叫脈絡）：

- `async def` 內有阻塞呼叫（同步 I/O、`time.sleep`、`requests`、CPU 重活）卡住 event loop
- 建立 asyncio task 卻不 await → 例外被吞，工作可能在完成前被 GC
- check-then-act 競態；非原子的複合更新被當成原子
  - ✅ 真實案例：對帳核准非原子且無列鎖 → settlement 遺失與重複出款（CR-0189）
- 跨 thread／task 的共享可變狀態無同步

**不要報**：區域變數、對共享資料的唯讀存取、沒有併發使用證據的 code。

## A6. 識別與相等

- 用 `is`／`is not` 比對字串、數字、tuple 字面值——依賴 interning 實作細節（**真實正確性風險**）
- 用 `== True`／`== False` 比較，truthy-but-not-True 的值會不相等
- `is` 只保留給 singleton 與 sentinel
- `== None` vs `is None` 是風格偏好，報成 minor 就好，**不是 blocking**

## A7. 效能

**先確認資料規模且確實在熱路徑上**再提：

- 迴圈內 `+=` 接字串（改累積進 list 再 `"".join`）
- 對 list 反覆做成員測試（改 set／dict，O(n) → O(1)）
- 該用 generator 卻建完整 list
- 迴圈內重算迴圈不變量（編譯 regex、熱路徑的屬性查找）
- `logging.info(f"...")` 提前格式化 → 用 `logging.info("%s", value)` 保留 lazy formatting

## A8. 死碼與錯字

- 永遠到不了的分支、`return`／`raise`／`break`／`continue` 之後的 code
- 宣告但從未被讀取的變數、import、參數
- 大段沒有保留意圖的註解掉的 code
- **宣告處**的變數／函式／類別命名錯字（引用處不報，由宣告決定）
- log 或例外訊息中影響可讀性的錯字

## A9. 安全（通用）

**先確認輸入真的是攻擊者可控**，不是可信常數：

- `eval`／`exec`／`compile` 吃不可信輸入
- `subprocess(shell=True)` 用未消毒輸入組成
- `pickle`／`marshal`／`yaml.load`（未用 SafeLoader）處理不可信資料
- SQL 用字串串接或 f-string 組成，而非參數化查詢
- **secrets／token／密碼／PII 寫進 log 或提交進原始碼**
  - ✅ 真實案例：log 有明文 email（`57ce5a6b`，已改為 `mask_email_for_log()`）
- 弱加密：`md5`／`sha1` 存密碼、`random` 產安全 token（改 `secrets`）
- 未驗證的路徑串接 → path traversal

---

# §B 上游規則**沒有涵蓋**、但本專案吃過虧的

> ⚠️ 這一節是本檔存在的主要理由。
> 2026-08-02 實測確認 ocr 的 Security 節**不含權限檢查缺失**——
> 而那正是本輪最嚴重的缺陷。通用 reviewer 不會幫你看這些。

## B1. 🔴 權限檢查缺失（broken access control / IDOR）

**本專案最高風險類型。任何回傳資料的端點都要問這三題：**

1. **有沒有驗「這筆資料屬於呼叫者」？**——只驗登入不算
2. **列表收斂了，那 detail 與子資源呢？**
3. **回 403 還是 404？**——403 等於確認該 id 存在，可被拿來列舉

✅ 真實案例（`2e9dd334`，本輪最嚴重）：
工單**列表**已依角色收斂，但 detail／quote-items／document／evidence-package
**四個端點全沒收**。技師拿別人的工單 id 直接打，detail 與 admin 逐欄比對只差
`customer_phone` 與 `address`；`document` 回 200 application/pdf，
**位元組數與 admin 取得的完全一致**。

> 教訓：**「列表收斂」是收斂了一半**。修好列表之後要立刻列出該資源的所有
> 子資源端點逐一檢查——`49de54d3` 修了列表，`2e9dd334` 才補完其餘四個。

**檢查清單**：
- [ ] 該資源的**所有**端點都過同一個 ownership guard（detail、子資源、匯出、PDF）
- [ ] guard 內的放行條件寫得出理由（本專案的搶單池：`technician_id IS NULL AND status='created'` 要放行，否則搶單壞掉）
- [ ] 未授權回 **404 不是 403**
- [ ] 有測試涵蓋「別人的資料」而不只是「自己的資料」

## B2. 🔴 多租戶隔離

- [ ] 查詢有沒有帶 `tenant_id`／`brand`？
- [ ] 跨面 token（brand／tech／platform）能不能打這個端點？
- [ ] 該守衛在**目標環境**是不是真的開著？

✅ 真實案例：CR-0182 的 portal 守衛靠 `ALLOWED_TOKEN_PORTALS`，
**prod 有設、本機三個容器全沒設**。在本機測「跨面沒擋住」是測到一個守衛被關掉的環境，
結論不可外推。→ 見 C3。

## B3. 🔴 Fail-open vs fail-closed

准入類的閘門，**查不到資料時預設放行還是擋下**？

✅ 真實案例（`5a9c323d`）：品牌授權查不到任何授權名單時回 `None`（＝不過濾＝全放行），
與 FR-TEC-02「未過准入閘門不得進入派工候選集」**正好相反**。

- [ ] 空結果集的分支寫得出「為什麼是放行／擋下」
- [ ] 若改成 fail-closed，**先確認資料齊全**再開，否則等於全面斷線
- [ ] 危險開關預設 off，且有回滾路徑

## B4. 🟠 閘門真空通過

檢查類邏輯在**前置條件不具備**時，回的是「通過」還是「跑不起來」？

✅ 真實案例（`49de54d3`）：對帳閘門在事件投影未啟用時回 `skipped=true` **且**
`gate_pass=true`——等於「沒檢查」被當成「檢查通過」。已改為
`gate_pass=false` + `RECONCILE_GATE_UNAVAILABLE`。

- [ ] `skipped`／`disabled`／`unavailable` 不得等價於 `pass`

## B5. 🟠 契約與實際儲存值不符

Pydantic／TypeScript 型別宣告的是**期望**，DB 存的是**現實**。

✅ 真實案例（`f35181c1`）：`media_urls` 宣告 `list[AnyUrl]`，
但寫入端存的是相對路徑 `/api/v1/media/{id}` → 端點 500、**對話卡死無法處理**。

- [ ] 改型別前先查**寫入端實際存什麼**，不要只看 schema
- [ ] `api/models/generated.py` 檔頭寫「generated by datamodel-codegen」但
      **實際是手動維護的**——改動要留註解說明為何偏離產生器

## B6. 🟠 「API 看起來支援」但參數是死的

✅ 真實案例（`57ce5a6b`）：`levels` 過濾參數收下了但完全不生效。
比不支援更糟——呼叫端以為過濾了。

- [ ] 每個宣告的 query／body 參數都要能指出它在哪裡被用到
- [ ] 未實作的參數要嘛移除，要嘛明確 warn

## B7. 🟡 只有 happy path 沒有自救路徑

✅ 真實案例（`898e1fbd`）：AI 判斷要轉真人時會翻狀態，但**若 AI 沒翻**，
客服端**完全沒有手動接管入口**——零自救手段，帳號就此卡死。

- [ ] 自動流程失效時，人有沒有手動介入的入口？
- [ ] 狀態機的每個狀態都出得去嗎？

## B8. 🟡 狀態變更無稽核

✅ 真實案例（`8d71904e`）：接管狀態變更沒留痕，事後查「這筆為什麼是 active」
只能翻 Cloud Run log 比對 timestamp。

- [ ] 權限／金流／狀態機的變更寫 `audit_events`（含 `from_status`／`to_status`）
- [ ] 稽核寫入失敗**不可**讓主流程失敗（best-effort）

---

# §C 本專案特有的硬規矩

> 這些不是通用缺陷，是**本 repo 的歷史包袱**。外來 reviewer 不可能知道。

## C1. migration-first 的前提

加 NOT NULL 欄位前先問：**「code 部署失敗時，新 schema + 舊 code 能活嗎？」**

- 2026-07-30 prod 實際故障過（被 CR-0190 pre-flight 擋住）
- 部署前必查 prod migration 進度 + 現行 image 落後幾個 commit
- migration 要帶 `migrate-targets:` header（brand／tech／platform）並走
  `apply-schema-routed.sh`——直接 psql 會落 schema 但**跳過 `schema_migrations` 記帳**

## C2. M18 config 開關的 FK 陷阱

`config_version.namespace` 對 `config_namespace(code)` 有 FK。
**namespace 沒註冊 → 那個開關永遠設不起來**（migration 118 的前車之鑑）。

- 新增開關必須同時註冊 namespace
- `read_global_value` 讀 `tenant_id IS NULL`——是**全域**開關不是 per-tenant
- 改 config fallback 常數前先在 repo 根 grep SQL/migrations 查 DB 種子值
  （DB 值會蓋掉 fallback，054/115 實案）

## C3. 環境參數必須先確認，結論不可跨環境外推

守衛在本機關著、prod 開著（或反之）是常態。

- [ ] 下「這裡沒擋住」的結論前，先確認**該守衛在這個環境是不是開的**
- [ ] 本機測出的安全結論，標明適用環境

## C4. 沒有對照組的狀態碼不算數

✅ 真實案例：183 個端點回 400，我判為「守衛擋下」。加對照組才發現
**admin token 打同一端點也是 400**（`MISSING_TENANT`）——那是 tenant header 檢查，
跑在角色守衛**之前**。那 183 筆等於完全沒測到。

- [ ] 任何「被擋下」的判定都要有**應該通過**的對照組
- [ ] 錯誤碼要看內容，不只看數字

## C5. 假基線比沒有基線更糟

✅ 真實案例：全套失敗數長期停在 129 支被當「既有失敗清單」。
補齊測試庫缺的 migration 後**真實基線是 20 支**——那 100 多支是測試庫 schema 落後。

- [ ] 每次改動後用 `comm -13 baseline.txt after.txt` 比對
- [ ] 反向驗證：stash 掉修正，確認**恰好**該紅的測試變紅
- [ ] 守衛已加（`8e542cdf`）：測試庫落後會直接中止。逃生門 `ALLOW_TEST_DB_DRIFT=1`
- ⚠️ **別對 :5433 業主 UAT 庫跑全套 pytest**——會洩漏測試資料。用 `lock_scratch_test`

## C6. gateway vs loop 分層

agent 的 bug 先判在哪一層：`line_gateway.py`（handoff 兜底／接管／debounce）
**繞過** loop，`real_turn_demo.py` 測不到。gateway 邏輯用 `test_line_gateway.py` 測。

## C7. 產品知識 bronze-only

references 內容嚴格源自 `knowledge-pipeline/storage/bronze/`。
**PDF (GDrive) 不可信，只引 URL 不抄內容。**

---

# §D 使用方式

## D1. 搭配 ocr 的確定性 pipeline（零金鑰）

`ocr delegate` 不需要任何 LLM 或金鑰，可以先讓它算出審查範圍：

```bash
ocr delegate preview --from <base> --to <head>   # 檔案清單 + merge_base + 增刪統計
ocr delegate rule <files>                         # 該檔適用的規則（本檔 §A 的來源）
```

拿到檔案清單後，依 §A→§B→§C 的順序審。**§B 優先於 §A**——
通用缺陷值得修，但權限缺陷會出事。

> 背景：2026-08-02 實測，ocr 的完整 review 需要能產出結構化 tool call 的模型；
> 本機 7B 模型做不到，且無雲端金鑰。詳見
> `docs/4-exploration/tech-eval-open-code-review-20260802.md` §9。

## D2. 審查順序建議

1. **§B1／B2**（權限與租戶）——先問「這個端點回的資料，呼叫者有資格看嗎」
2. **§B3／B4**（fail-open、真空通過）——所有 guard 與 gate 的空結果分支
3. **§C**（本專案硬規矩）——動 migration／config／agent 時必查
4. **§A**（通用）——最後掃

## D3. 報告紀律

- 每條指出 `file:line`
- 標明 blocking／non-blocking
- 寫得出**具體失效情境**（什麼輸入 → 什麼錯誤結果）才提；寫不出來就是還不夠確信
- 不確定時保持沉默——見開頭的 precision > recall
