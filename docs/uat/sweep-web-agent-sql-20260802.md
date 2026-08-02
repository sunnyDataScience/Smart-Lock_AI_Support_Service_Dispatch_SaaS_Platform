# web / agent / SQL 全維度掃描記錄（2026-08-02）

- **觸發**：業主「繼續，全部都掃，有問題就修復」——api 掃過之後，把剩下三塊補完
- **範圍**：`web/` 485 tsx（四站台）、`agent/` 56 個自有 py、`SQL/` 125 個 migration
- **方法**：11 個維度平行掃描（web 6 + agent/SQL 5），每個 finding 派 skeptic 對抗驗證
- **結果**：19 個 finding，13 個存活、4 個駁回（含 2 個我獨立複驗後推翻 skeptic 的）
- **commit**：`e107baa8` → `ceb9d73d` → `264b7dab`

---

## 一、已修（8 項）

| 嚴重度 | 位置 | 缺陷 |
|---|---|---|
| **CRITICAL** | `agent/scripts/line_gateway.py` | 檔案工具無路徑沙箱，LINE 使用者可誘導讀 `/proc/self/environ` 帶走全部機密 |
| HIGH | `agent/lockcore/channels/line_gateway.py` | 兜底話術含「專員與您」→ 觸發自己的轉真人兜底 → AI 對該客人永久靜音 |
| HIGH | `agent/lockcore/channels/line_gateway.py` | spool 補送在 turn 路徑上持全域鎖序列重送整批 → 一次 API 慢就卡死所有客人 |
| HIGH | `api/routers/cancellation.py` | v2 取消端點無角色守衛（legacy 孿生端點有）→ technician/vendor 可取消任一工單並操控取消費 |
| HIGH | `api/services/refund_service.py` | SoD 退款路徑不寫 `reason_code` → 唯一索引因 NULL 失效 → 可重複退款 |
| MEDIUM | `web/tech-portal/.../home/page.tsx` | 工單載入失敗被靜默丟棄 → 顯示「今天沒單」讓師傅誤判 |
| MEDIUM | `api/routers/platform_brand_applications.py` | 未認證表單的 `website` 無 scheme 驗證（深度防禦，見 §三-1） |
| — | `api/tests/test_env_symlink_guard.py` | `web/*/.env` symlink 退化防護（見 §三-2） |

## 二、未修，已開 CR

**CR-0200**：agent workspace 全域 `history.jsonl` 會把 A 客人的對話注入 B 客人的
system prompt。三條修法都動到架構（per-user workspace 會衝擊 SkillSync 設計、
關閉注入要改 vendor code、cursor workaround 語意不清），需業主裁決。
觸發門檻高（單一客人對話累積 > 65k tokens）但一旦發生就持續且不會自己好。

## 三、兩個「對抗驗證說錯了、我複驗推翻」的案例

這一節比修好的東西更值得記錄——**對抗驗證也會錯，實測才是最終仲裁**。

### 1. XSS：skeptic 對，我的修正是深度防禦而非補洞

我先獨立確認了攻擊鏈：`submit_brand_application` 完全沒有 `Depends`（公開端點）、
`website` 只限 `max_length`、前端直接渲染成 `<a href>`。看起來是 stored XSS。

skeptic 駁回，理由是「渲染器本身把 sink 廢掉了」。我實測 React 19.2.7：

```html
<a href="javascript:throw new Error('React has blocked a javascript: URL as a security precaution.')">
```

**攻擊者的 payload 沒有進 DOM**，skeptic 是對的。

我第一次的判斷之所以錯，是因為我用 `out.includes('javascript:')` 當判準——
而那個 `javascript:` 是 React 自己的擋阻碼，不是 payload。**字串比對不能當安全判定。**

修正保留（後端 pattern 擋髒資料進 DB、前端 `safeHref` 防日後改用非 React 渲染），
但它是深度防禦，**不是**修補一個當下可利用的漏洞。

### 2. `.env` symlink：skeptic 錯，我實測推翻

skeptic 判 refuted，理由是「no secrets are in version control, and the failure path
invented to get them there is wrong at every step」。

前半對——版控裡存的是 symlink 本身（字串 `../../.env`），目標未進版控，**沒有外洩**。

後半錯。我建了一個乾淨 repo 實測「把 symlink 換成實體檔案」：

```
初始 mode: 120000
換成實體檔案後：git status → T web/app/.env
git add -A → 🔴 機密會被 commit
```

`.gitignore` 的 `.env` 規則**對已追蹤路徑無效**，失效路徑真實存在。
測試保留。

## 四、我自己駁回的 finding

**`technician_payout_rule` 業務鍵無唯一約束 → 佣金重複累加**（掃描判 HIGH）——不成立：

1. `get_rule` 明確處理多筆：`ORDER BY effective_date DESC NULLS LAST LIMIT 1`，
   docstring 寫「多版本時取最新生效」→ **多版本是刻意的版本化設計**，加 UNIQUE 反而打壞
2. 拆帳計算**完全不查這張表**（grep 零命中，與 migration 檔頭
   `NOT wired：reconciliation 拆帳重算待 Phase II` 註解一致）

「師傅多領錢」的失效路徑不存在。

## 五、我犯的一個錯：no-op 修正

第一版沙箱修正傳了 `AgentLoop(restrict_to_workspace=True)`——**完全沒生效**。
那個 kwarg 只轉給 `SubagentManager`（loop.py:256→288），而檔案工具讀的是
`ToolContext(config=self.tools_config)`（loop.py:484），兩者之間沒有任何同步。

是對抗驗證實跑 `read_file('/etc/hosts')` 抓出來的。**比沒修更糟的是留下「已修好」的假象。**

教訓已寫進測試設計：`test_tool_workspace_sandbox.py` 不再斷言「有沒有傳這個參數」，
改成**直接建出工具、檢查 `_allowed_dir`、真的去讀 workspace 外的檔案**。
設定怎麼傳是實作細節，工具擋不擋得住才是要守的東西。

反向驗證確認：把 code 還原成第一版寫法，新測試會紅。

## 六、未修的 MEDIUM / LOW（附具體修法）

| 位置 | 問題 | 建議修法 |
|---|---|---|
| `web/brand-portal/.../work-orders/page.tsx:82` | 客戶姓名/電話/地址經搜尋框進 URL query string，明文落在**兩層** Cloud Run access log（brand-portal + API），繞過 RBAC 且不產生 audit | 搜尋改用 POST body，或前端先雜湊；屬 API contract 變更需走 CIA |
| `web/brand-portal/.../work-orders/kanban` | 搜尋框逐鍵發 request 且無取消 → 較舊查詢的結果覆蓋較新的 | `AbortController` + debounce |
| `web/brand-portal/.../admin/disputes/page.tsx:131` | 爭議證據照片載入失敗被靜默吞掉，畫面顯示「0 個檔案」而客服據此裁決賠償 | 同師傅站首頁的做法：加 error state |
| `agent/config.toml:31` | 硬寫 `backend="sqlite"` 無 runtime 覆寫 → 多實例下 per-instance sqlite，去重失效 | 加 env 覆寫；但目前 `MIN=MAX=1` 單實例，影響未實現 |

## 七、驗證

| 項目 | 結果 |
|---|---|
| api 全套 | **20 failed / 2314 passed**（基線 20 / 2284），`comm -13` **零新增** |
| agent 全套 | **337 passed / 1 failed**（既有 live LLM 測試，stash 對照確認） |
| tech-portal tsc | 25 個既有錯誤，stash 對照相同；我改的檔案零錯誤 |
| platform-console tsc | 17 個既有錯誤；我改的檔案零錯誤 |
| 反向驗證 | 沙箱測試、spool 界限測試都確認「還原 code 後會紅」 |

## 八、涵蓋率（誠實版）

至此三塊都掃過一輪，但**維度不是窮舉的**：

- web 只掃了 6 個維度（XSS／client 機密／權限落差／PII／錯誤處理／React 競態），
  沒掃：依賴套件漏洞、CSP、build 設定、a11y、效能
- agent 只掃了 3 個維度，且 `lockcore/` 的 vendor code 刻意排除在外
  （只看本專案接線處與被用錯的地方）
- SQL 只掃了 2 個維度（約束缺口／migration 部署安全），
  沒掃：索引效能、查詢計畫、資料型別選擇

且每個維度**限制最多回報 2 個 finding**（為壓誤報率），所以低優先的問題不會浮上來。
