# Operational Architecture Viewpoints

本文件定義五張圖的 concern、元素與完成條件。每張圖都有唯一責任，避免同一資訊
在不同圖中以不同名稱重複維護。

## 00 — System Context / C4 L1

Concern：產品邊界與對外責任。

必要元素：

- 一個明確的 System of Interest。
- 直接使用或維護系統的人員角色。
- 與系統直接交換資訊或能力的外部系統。
- 每條 relationship 的目的或交換內容。

完成條件：

- 不熟悉實作的人能說出系統負責與不負責什麼。
- 所有外部依賴有 owner 或至少有清楚的外部邊界。
- 圖中沒有內部 microservice、database、host 或 incident。

常見錯誤：把 repository 清單當 System Context；把未來平台元件畫成現況外部系統。

## 01 — Operational Processing / UML Activity + Object Flow

Concern：產品從輸入到可交付結果的穩定加工邏輯。

必要元素：

- `OP-xx` activity，名稱使用動詞＋受詞。
- 可辨識狀態的 object node，例如 `Validated Input`、`Versioned Policy`。
- 真正的 decision、fork/join、feedback。
- Activity Partition 表達 accountable architecture domain，不使用組織圖式泳道。
- 主要 outcome 與需要人工介入的 handoff。

完成條件：

- 能從 source 沿主幹走到 outcome，並看到儲存、事件、控制回饋等分支。
- 每個 OP 在 Process Catalog 有定義、owner 與輸入輸出。
- 圖中沒有 container 名稱冒充 activity，也沒有 troubleshooting step。

常見錯誤：照 UI click sequence 畫流程；每個 API call 畫一個 activity；用 service
泳道讓 process 被目前部署切碎。

## 02 — Container Architecture / C4 L2

Concern：可獨立執行或保存資料的責任單位。

必要元素：

- 使用者與必要的外部系統。
- `C-xx` Container：名稱、technology、主要 responsibility。
- Container 間有方向與目的的 relationship。
- 資料存放的 ownership，而不只是「DB」方塊。

完成條件：

- 每個 container 都能對應實際 deployable、managed service 或 owned store。
- 能由 OP 找到主要實作 container。
- 不把 library、class、endpoint、Pod 或 replicated instance 當 container。

常見錯誤：只畫技術棧；用一個「Backend」隱藏多個互相衝突的責任；把 process
sequence 重畫成 container 箭頭鏈。

## 03 — Information Flow / DFD L1

Concern：information product 的產生、轉換、傳遞、保存與消費。

必要元素：

- External Entity、Process、Data Store。
- `I-xx` named flow，名稱是可理解的資料／事件／命令。
- 重要的同步／非同步、stream／batch、delivery semantics 或版本語意。
- Video、event、control、artifact 等不同資料面分開表達。

完成條件：

- 任何主要 outcome 都能追溯到 source、transformation、store 與 consumer。
- 看得出「資料未產生」與「資料已產生但未被投影」是不同 boundary。
- 圖中沒有 host、port inventory、dashboard 或推測的 failure mode。

常見錯誤：箭頭全部寫 `data`；將 control command 和 event feedback 畫成同一條線；
為了完整列出每個 topic 或 endpoint 而失去主幹。

## 04 — Deployment Architecture / C4 Deployment

Concern：Container instance 在真實 runtime 與 infrastructure 的配置。

必要元素：

- `N-xx` Deployment Node 與 network / trust boundary。
- Container instance 到 `C-xx` 的映射。
- runtime、device、accelerator、persistent volume 或 managed service。
- 必要的 protocol、port、mount 或 external connectivity。
- replica、HA、optional、manual 等狀態明示。

完成條件：

- 維運人員能找到負責 instance、host、network、device 與持久化位置。
- 圖面只包含已查證的環境事實；未確認資訊明確標記。
- 不重畫 business process，也不把期望中的 target topology 當成 current。

常見錯誤：Docker Compose service、container、host、cluster 名稱混用；只畫 logical
container 而沒有 placement；用 deployment 圖記錄臨時 incident。

## Viewpoint Change Gate

| 變更 | 應更新 |
|---|---|
| 產品責任或外部 actor 改變 | 00，並檢查 01–04 |
| 穩定 processing / outcome 改變 | 01、Process Catalog、Traceability |
| deployable responsibility 改變 | 02、Traceability，必要時 04 |
| information contract / source / store 改變 | 03、Traceability |
| host / runtime / device / volume 改變 | 04 |
| 新 incident 但架構事實不變 | 不改五張圖；更新 runbook / lesson learned |
