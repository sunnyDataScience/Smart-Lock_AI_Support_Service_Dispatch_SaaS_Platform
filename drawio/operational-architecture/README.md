# Smart Lock 作業架構（Operational Architecture）

這是 Smart Lock AI 客服與派工 SaaS 的五視圖作業架構包。它把既有 `drawio/` 的
Solution Architecture 視覺語言，收斂為可供產品、工程、QA 與維運共同定位的穩定座標。

> **證據快照：2026-07-27 / `dev-ding@6a6dd846`。** 圖中的 `CURRENT` 是程式或
> repository 設定可確認的行為，**不是** production 部署宣告。`PARTIAL`、`TARGET`、
> `OD-xxx` 與虛線皆不可當成已上線事實。

## 產物與閱讀順序

| 順序 | 視圖 | 回答的問題 |
|---|---|---|
| 00 | [System Context](00_system-context.drawio) | 平台邊界、外部角色與外部依賴是什麼？ |
| 01 | [Operational Processing](01_operational-processing.drawio) | 客戶訊號如何被分流、人工核可、派工、交付並回饋？ |
| 02 | [Container Architecture](02_container-architecture.drawio) | 哪些 runtime／store 擁有什麼責任？ |
| 03 | [Information Flow](03_information-flow.drawio) | 哪些資訊產品如何流動、保存與被消費？ |
| 04 | [Deployment Runtime](04_deployment-runtime.drawio) | repository 可確認的部署形態與尚未取證之處是什麼？ |

- [smartlock-operational-architecture.drawio](smartlock-operational-architecture.drawio)：上述五張圖的合併 deck。
- [PROCESS-CATALOG.md](PROCESS-CATALOG.md)：`OP-xx` 的責任、輸入輸出與 SAD/SDS 回查。
- [TRACEABILITY-MATRIX.md](TRACEABILITY-MATRIX.md)：`OP`、`C`、`I`、`N` 與 owner 的跨圖導航。
- [VIEWPOINTS.md](VIEWPOINTS.md)／[MODELING-RULES.md](MODELING-RULES.md)：五視圖方法與標號規則。
- [REVIEW-CHECKLIST.md](REVIEW-CHECKLIST.md)：跨團隊評審檢查表。

`PROCESS-CATALOG.template.md` 與 `TRACEABILITY-MATRIX.template.md` 保留為可攜式範本；
日常使用應以無 `.template` 的 Smart Lock 實例為準。

## 標記與資料來源

| 標記 | 意義 | 主要依據 |
|---|---|---|
| `CURRENT` | code／設定／測試可確認 | [12_SAD §15](../../smartlock-docs/enterprise/12_SAD.md)、[15_SDS](../../smartlock-docs/enterprise/15_SDS.md) |
| `PARTIAL` | 有實作路徑，但依賴設定、環境、SIT 或完整邊界尚缺 | [Codebase 現況掃描](../../smartlock-docs/enterprise/規格統控整理/Codebase現況掃描_2026-07-27.md) |
| `TARGET`／虛線 | 已有設計方向，非現況宣告 | SAD／SDS 的分期設計 |
| `OD-001`～`OD-004` | 尚未拍板的架構聯合決策 | [Open Decisions](../../smartlock-docs/enterprise/14_ADR/OPEN_DECISIONS.md) |
| `N-xx` | deployment node；未取證時明示未知，不臆測 host 或 HA | [部署與 SIT 證據關卡](../../smartlock-docs/enterprise/規格統控整理/部署與SIT證據關卡_2026-07-27.md) |

元件詞彙（如 `line_gateway`、LockCore runtime、Skills、Memory）的一句定義、責任邊界、
程式路徑與 SAD/SDS 章節，統一查
[SAD_SDS元件標籤字典.md](../../smartlock-docs/enterprise/規格統控整理/SAD_SDS元件標籤字典.md)，
不在圖中重複塞入 L3 細節。

## 維護方式

所有 `.drawio` 都由同一個產生器輸出，請修改
[`_build_operational_architecture_template.py`](_build_operational_architecture_template.py) 後重建：

```bash
python3 drawio/operational-architecture/_build_operational_architecture_template.py
```

不要手改產生出的 `.drawio`，否則下次重建會覆寫。變更 stable processing 時，同步更新
Process Catalog 與 Traceability Matrix；變更部署事實時，須同時附上實際環境／SIT 證據。

## 使用於事件定位

一次 operational issue 只需記錄受影響 outcome、最後正常／第一個失敗的 `OP` 或 `I`
邊界、對應 `C`／`N` 與 correlation key。incident 細節、log query 與排障命令應留在
runbook／lesson learned，避免污染五張穩定架構圖。
