---
title: "ADR-044: 拆解樹 Feature 錨點改為業務能力（階層 V3）"
version: 1.0
status: active
owner: PM / SA
last-updated: 2026-08-08
relates:
  - ../規格統控整理/_feature_taxonomy.yaml
  - ../規格統控整理/Feature層定義.md
  - ../規格統控整理/產出健康報告.md
---

# ADR-044: 拆解樹 Feature 錨點改為業務能力（階層 V3）

| 欄位 | 內容 |
|---|---|
| 狀態 | Accepted（2026-08-08 業主審核通過） |
| 層級 | 規格治理（拆解樹 / Plane 投影） |
| 真相源 | [`_feature_taxonomy.yaml`](../規格統控整理/_feature_taxonomy.yaml) |
| 對帳 | `uv run python _validate_taxonomy.py` |
| 影響產物 | 四本 xlsx、`產出健康報告.md`、Plane 投影（未移植） |

## Context

拆解樹的 L1/L2 在三個月內換過兩次錨點，兩次都不是因為節點錯，而是因為**分組的軸選錯**：

| 代 | Feature 的定義 | 退場原因 |
|---|---|---|
| G1（2026-07-30）| 32 個 `子系統·模組` 能力群 | 技術切法。一個 sprint 交付的價值橫跨多個子系統，roll-up 出來的數字回答「agent 這包做完幾成」，而管理層問的是「哪幾條客戶旅程跑得通」 |
| G2（2026-08-05）| 19 條 SC 旅程 ＋ 18 個 NFR category 地板 | 情境切法＋品質屬性切法混用 |
| **G3（本 ADR）** | **18 個業務能力群 `CAP-*`** | — |

G2 有兩個結構性代價：

1. **FR 與 NFR 被拆到樹的兩側。**106 條 NFR 全數丟進 `E-GLB` 地板，於是「派工媒合這件事
   做得夠不夠好」要在樹的兩個地方各看一半——功能面在 `SC-05`，品質面散在
   `地板-Perf` / `地板-SLA` / `地板-Scal`。

2. **32 條 FR 判不出 parent。**追溯是 M:N（一條需求可以同時服務多條旅程），但樹上
   parent 只能有一個。65 支 FR 裡只有 27 支有唯一 `essential` 邊可以機器推導，6 支宣告
   `global`，剩下 32 支需要 BA 逐條裁決「主旅程」。這 32 支同時讓
   `01_需求收斂` 的 Feature 欄整欄空白、`03_交付切片` 的 Epic 欄出現「待定」。

第 2 點值得展開：它不是資料髒，是**錨點與載體不匹配**。用旅程當 Feature，就必然要求
每條需求選一條主旅程，而「這條需求主要為哪條旅程存在」對橫跨多旅程的需求本來就沒有
非任意的答案。裁決 32 次只是把這個不匹配轉嫁給人。

## Decision

**Feature 層改以業務能力（做什麼）分組**，真相源為 `_feature_taxonomy.yaml`：

| 層 | Plane type | 張數 | 裝什麼 |
|---|---|---:|---|
| L1 | `Epic` | 4 | 業務域：`E-SERVE` / `E-SUPPLY` / `E-TENANT` / `E-CORE` |
| L2 | `Feature` | 18 | 業務能力群 `CAP-*`，**FR 與 NFR 掛同一張** |
| L3 | `Story` | 171 | FR 65 ＋ NFR 106；驗收契約掛這一層 |

硬約束（來自 canon，不是模型偏好）：

1. 必須蓋滿 171 個 Story，一條一組，不重不漏（由 `_validate_taxonomy.py` 守）
2. 不可機械推導——FR ID 內建子系統（`FR-AGT-01`），自動分群必落回 G1
3. FR 與 NFR 掛同一組

### 為什麼留在 yaml 而不搬進 `_spec_data.py`

審核時的原計畫是「審過才進 `_spec_data.py` 成為常數」。實作時改為留在 yaml：這 171 條
掛載有一支專屬 validator 擋漏掛／重掛／幽靈 ID，搬成 Python 常數會讓同一份資料存在兩個
地方，而 validator 只驗得到其中一份。`_spec_data.py` 收的是「沒有機器可驗的人工判斷」，
這份有，所以留在機讀格式。

## Consequences

### 正面

- **171 條全部有 parent，orphan 0。**G2 的 32 條缺口消失——不是被填平，是成因隨錨點更換
  而不存在了。連帶關掉的下游缺口：`01_需求收斂` Epic/Feature 四欄從整欄空白改為 derived
  全填；`03_交付切片` 173 個 Task 全部有業務域 Epic（原 32 支 FR 的 Task 顯示「待定」）。
- **16/18 個能力群同時裝著功能面與品質面**，一個能力的完整品質輪廓在同一張卡上。
  另外兩個是刻意的單邊：`CAP-QUOTE`（4 FR / 0 NFR，報價沒有獨立的品質門檻）與
  `CAP-BASE`（0 FR / 5 NFR，全系統服務基線本來就不對應任何功能）。
- **不需要 BA 逐條裁決 `primary: true`。**

### 負面 / 待處理

- **SC 旅程退出拆解樹。**19 條旅程仍是《業務邏輯驗收控制表》的列節點與 `SC × RQ`／
  `SC × TC` 兩條追溯邊的一端，但不再是 Plane 的 Feature 卡。BOM 的「服務旅程」欄改由
  追溯邊算出來，《業務邏輯驗收控制表》的「Plane Feature」欄改為「這條旅程的 essential
  需求落在哪幾張能力群卡」。
- **V14 降級但未歸零。**`primary_scenario()` 保留作 SC 覆蓋分析用，V14 的 32 筆 finding
  仍會出現，語意改為「SC 覆蓋歸屬未裁決」，**不阻擋交付**。訊息文字與 rule 說明已同步改寫，
  避免被讀成拆解樹的洞。
- **🛑 Plane 投影尚未移植。**`_plane/rebuild_hierarchy.py` 仍是 G2，已加守線（非 `--dry-run`
  直接 `exit 3`），因為移植要動線上資料且其中一題只有人能決定：既有 19 張 SC Feature 卡與
  18 張地板 Feature 卡如何處置（降級／改型別／archive／保留為追溯卡）。**在那之前 Plane
  的樹與四書 xlsx 不一致**，以 xlsx 為準。

## 驗證

```bash
cd smartlock-docs/enterprise/規格統控整理
uv run python _validate_taxonomy.py      # 171 條一條一組，不重不漏
uv run python _build_workbooks.py        # 四本重生（必須用 uv run，裸 python3 缺 lxml）
```

實測：BOM `② 需求 → 元件 BOM` 分頁 L1 4 列／L2 18 列／L3 171 列，無 orphan 段落；
連續兩次重生的儲存格值 checksum 相同。
