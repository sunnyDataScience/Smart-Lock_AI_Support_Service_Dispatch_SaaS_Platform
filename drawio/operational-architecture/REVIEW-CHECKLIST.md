# Operational Architecture Review Checklist

## Product model

- [ ] `00` 只有一個清楚的 System of Interest。
- [ ] `01` 從 source 到 outcome 的主幹可在不放大時讀懂。
- [ ] Activity 使用動詞＋受詞，Object 使用可辨識狀態的名詞。
- [ ] 圖面不依賴某個 UI journey 或已知 issue 才成立。
- [ ] 人工 handoff、optional、legacy、gap 沒有被畫成自動主線。

## Software architecture

- [ ] `02` 每個 Container 都能對應 deployable / managed service / owned store。
- [ ] Container 標示 technology 與主要 responsibility。
- [ ] `03` 每條主要 flow 都有 information object、方向與必要 delivery semantics。
- [ ] Video / event / control / artifact 等資料面沒有被不當合併。
- [ ] `04` 的 node、runtime、device、volume 與 environment 已有 evidence。

## Traceability and ownership

- [ ] 每個 `OP-xx` 已登錄 Process Catalog。
- [ ] 每個主要 OP 可對應 `C-xx`、`I-xx`、`N-xx` 與 owner。
- [ ] 假設與 TBD 有 owner 或確認期限。
- [ ] Drill-down 有 parent stable ID，不形成第二套 E2E overview。

## Communication quality

- [ ] 每張圖只回答一類 concern。
- [ ] Edge label 在黑白列印時仍能理解。
- [ ] 圖中沒有 endpoint/class/schema/dashboard/debug command 清單。
- [ ] 新進工程師可用 `00→01→02→03→04` 說出產品如何運作。
- [ ] 維運工程師可用 stable ID 表達 last-good / first-failed boundary。

## Change gate

- [ ] 此變更是 stable architecture fact，而不是單次 incident detail。
- [ ] 受影響的 catalog / matrix / evidence 已同步。
- [ ] 沒有建立與既有 viewpoint 重複的新圖。
