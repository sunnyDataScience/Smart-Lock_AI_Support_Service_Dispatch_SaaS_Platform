# Change Governance Rule

> AI 加速時代真正要治理的不是「程式碼產出速度」，而是「需求變更如何被吸收、追蹤、驗證、同步」。沒有這層治理，AI 會把矛盾文件腦補成「合理版本」，把「看起來合理」的錯誤訊息產出量產化——這就是 AI slop 的根源。

---

## ⚠️ CIA gate 於 2026-08-05 縮限為「只有跟錢有關的才保留」

本檔原本的第一條規則是：

> 變更涉及 flow / contract / data / architecture → **先產出 Change Impact Analysis (CIA)
> 至 `docs/4-exploration/CR-NNNN-*.md`，🛑 停下等業主裁決 §8「Human Decisions Required」
> 後才可動 code。**

縮限的實證理由（不是嫌麻煩）：2026-08-03 的 UAT 靜態走查回查證出 83 個確認缺口，
其中 **75 個命中 gate 而無法動工，實際修復率只有 9%**（8/83）。產出的 11 張 CIA
（CR-0201～0211，6,777 行）本身是有品質的分析，但對非金流變更而言，
它們把「修好問題」變成了「等一輪裁決」——治理成本超過它防止的風險。

錢不一樣：算錯或被錯誤核准之後，補救成本遠高於事前確認一次，所以這一類保留 gate。

### 💰 仍需 CIA 的範圍（金流）

以下**仍須產出 CIA → 🛑 停下等業主裁決 §8 → 依 §9 實作**：

| 範圍 | 具體例子 |
|---|---|
| 退款 | 退款建立/核准/執行、SoD 三維、金額分層與核准權限、雙簽門檻 |
| 結算 | 月結批次、技師抽成計算、結算狀態機、期末對帳閘門 |
| 傳票／分錄 | voucher 產生、紅字沖銷、hash chain、借貸科目 |
| 對帳 | reconciliation、差異處理、gate_pass 判定 |
| 報價金額與計費 | 定價規則、折扣、免費保固、完工比例、取消費率、稅務 |
| 發票 | invoice 產生、作廢、金額與稅額 |

判準：**這個變更會不會改變「誰付多少錢給誰」或「誰有權核准付錢」**。會 → 走 CIA。

### 其餘一律直接實作

**不產 CIA、不停下等裁決。** 動到下列面向時仍要格外小心，
但那是「做得更仔細」而不是「停下來」：
User/Business flow、API contract、Domain model、DB schema、External integration、
Test plan、Architecture boundary。

取代 gate 的自我要求（這些是實質品質保證，不是流程儀式）：

1. **先查清現況再改** —— 打開實際的 `檔案:行號` 確認，不靠印象或文件轉述。
2. **測試要雙向驗證** —— 新增的測試必須確認「對修復前的版本會紅、對修復後會綠」。
   只會綠的測試等於沒測（2026-08-05 的 `TC-QUOTE-09` 就是例子：既有測試涵蓋了
   出問題的路徑，但需要 live DB 而 CI 跑不到，於是 bug 帶著「有測試」的外觀上線兩週）。
3. **回歸要對基線** —— 跑全套前先 stash 建立基線，比對失敗清單是否相同，
   不要把既有失敗誤認成自己造成的、也不要把自己造成的藏在既有失敗裡。
4. **commit message 寫清 WHY 與影響範圍**，破壞性變更明確標記。

### 既有 CR 文件的地位

`docs/4-exploration/` 下已產出的 CR（CR-0170 / 0197 / 0198 / 0201～0211）
**不因本裁決作廢**——它們仍是有效的背景分析、證據記錄與決策軌跡，實作時該讀。

差別在於還要不要等 §8 被填答：

- **非金流 CR**（0201 / 0204 / 0205 / 0206 / 0207 / 0208 / 0209 / 0210 / 0211）
  → 不必等，直接依 §9 的順序實作；§8 的建議選項當作預設決定。
- **金流 CR**（**CR-0203** 結算/傳票/退款/SoD；**CR-0202** 中涉及報價金額與計費規則的項目；
  **CR-0211** 中的完工比例與取消費率）→ **仍須等業主填答 §8 才動工**。

---
## Source of Truth Conflict — 處理規則

當文件之間或文件與 code 矛盾：

- ❌ **不要**：自己腦補「合理版本」
- ❌ **不要**：靜默選一邊（哪怕看起來明顯）
- ✅ **要**：停下來回報衝突 + **引用具體 ID**（BF-0001、API-0007、TC-0023）+ 等使用者裁決

回報格式範例：

> 🛑 **Source of Truth 衝突偵測**
>
> - `BF-0001 §4 step 3` 描述：訂單建立後立即扣庫存
> - `SF-0001 §3 inputs` 描述：訂單建立後**保留**庫存（reserve），付款後才扣
> - `src/inventory/service.py:142` 實作：保留庫存
>
> 三方不一致。建議裁決方向：
> 1. 把 BF-0001 §4 step 3 改為「保留庫存」（與 SF/code 一致）
> 2. 或：開 CR 把行為改回「立即扣庫存」（推翻 SF/code）
>
> 等待你決定哪個是 source of truth。

---

## Stale Doc — 處理規則

讀到帶以下 frontmatter 的文件：

| frontmatter | AI 該怎麼做 |
|---|---|
| `status: draft` | 警告使用者「此文件尚未 active」；可參考但不視為事實 |
| `status: deprecated` | 警告，並建議遷移到指定替代品；不引用為事實 |
| `status: superseded` | 直接跳到 `superseded_by` 指向的文件；不再讀原文 |
| `status: archived` | 完全忽略（除非使用者明確要求看歷史） |
| 無 status frontmatter | 視為 active，但提示使用者該補 frontmatter |

`sunnydata-doc-freshness` skill 會掃出沒有正確 status 的 contract 並建議補上。

---

## Rewrite vs Refactor — 三層決策

不是所有變更都該用「局部修改」處理。當變動規模大時，先跑這個打分表決定是要**修文件**、**重組模組**、還是**開新主幹**。
（CIA gate 已移除，但這張表仍然有用——它回答的是「這件事的規模對不對」，與要不要產文件無關。）

### 打分維度（每項 0-2 分）

| 維度 | 0 分 | 1 分 | 2 分 |
|---|---|---|---|
| 產品目標是否改變？ | 沒變 | 局部變 | 大幅改 |
| 核心 User Flow 是否改變？ | 沒變 | 新增分支 | 主流程重寫 |
| Domain Model 是否改變？ | 沒變 | 新增概念 | 核心概念改 |
| API Contract 是否大量破壞？ | 少量 | 多 endpoint 變動 | 全面不相容 |
| DB Schema 是否需重建？ | 不用 | migration 可處理 | migration 很痛 |
| 模組邊界是否錯誤？ | 清楚 | 有些混亂 | 根本切錯 |
| 測試是否可信？ | 可信 | 部分可信 | 幾乎不可信 |
| 文件是否可信？ | 可信 | 部分過期 | 大量矛盾 |
| 團隊/AI 是否還理解系統？ | 理解 | 少數人懂 | 幾乎沒人懂 |

### 判斷

| 總分 | 行動 |
|---|---|
| **0–6 分** | 改文件 + 局部重構（一次性實作即可） |
| **7–12 分** | 架構重審 + 模組拆分（多 CR + 跨 sprint） |
| **13 分以上** | 考慮新專案 / 新主幹（freeze 舊系統，重建） |

「**改文件只是修正地圖；當地圖描述的世界已經不是原本那個世界，就要開新專案**」。13 分以上不是逃避，是承認原本的產品假設已經死了。

---
## How AI signals change-governance awareness

- ✅ "Read `BF-0001` and `SF-0001` — they conflict on inventory timing. Stopping to report (see above)."
- ✅ "Document `docs/2-contracts/legacy-payment.md` is `status: superseded` → following pointer to `payment-v2.md` instead."
- ✅ "This touches the quote state machine — opened `quote_engine_service.py:459-520` to confirm the actual transitions before changing anything, rather than trusting the spec table."
- ❌ Silently reconciling conflicting docs by writing "the obviously correct" code
- ❌ Updating an `status: deprecated` document instead of its replacement
- ❌ Adding a test that only proves the fixed version passes, without checking it fails against the broken one

---

## Anti-patterns to refuse

| Anti-pattern | Why bad | What to do instead |
|---|---|---|
| 依文件表格改 code，沒開實際檔案確認 | 文件常落後於實作；2026-08-05 查證 94 支 TC 有 36 支引用的行號有誤 | 每個結論都要有實開過的 `檔案:行號` |
| 新增測試只驗「修好之後會過」 | 只會綠的測試等於沒測 | 對修復前的版本跑一次，確認會紅且指出正確位置 |
| 跑全套測試後把既有失敗當成自己造成的（或反之） | 兩個方向都會導致誤判 | stash 建立基線，比對失敗清單是否相同 |
| 把「用詞不同」當成「功能沒實作」 | 2026-08-05 走查 11 支判重全是這個模式 | 先確認語意是否等價，再判斷是 code 該改還是文件該改 |
| Editing a `status: deprecated` doc | Effort wasted; downstream still confused | Edit the `superseded_by` doc; or write new ADR if reviving |

---

## See also

- `rules/context-stability.md` — 各類產出住在哪個 tier、衝突時誰贏
- `rules/testing.md` — 測試要求與 TDD 流程
- `docs/4-exploration/` — 既有 CR（CR-0170 / 0197 / 0198 / 0201～0211）。
  CIA gate 已移除，但這些文件仍是有效的背景分析與決策記錄，動到相關領域時該讀。
