# Modeling Rules

## Stable IDs

| Prefix | Model element | Example |
|---|---|---|
| `OP-` | Operational activity | `OP-30 Execute Core Processing` |
| `C-` | C4 Container / owned store | `C-20 Application API` |
| `I-` | Information flow / contract | `I-30 Normalized Result Event` |
| `N-` | Deployment node | `N-40 Edge GPU Host` |
| `CP-` | Observable checkpoint（若另建 diagnostic 文件） | `CP-I30-02 Consumer Receive` |

ID 不因排版或名稱微調而變更。責任實質拆分時新增 ID；退役 ID 標示
`RETIRED`，不要拿來表示不同概念。

## Naming

- Activity：`動詞 + 受詞`，例如 `Validate Input`。
- Object / Information：可辨識狀態的名詞，例如 `Validated Input`。
- Container：可部署單位名稱，附 technology 與一句 responsibility。
- Data Store：名稱包含 owned information，而非只寫產品名稱。
- Relationship：寫交換目的或資料名稱，禁止只寫 `calls`、`uses`、`data`。
- Deployment Node：使用可查證的 environment / host / runtime 角色。

## Abstraction Budget

主圖採「一眼看主幹、第二眼看分支、需要細節才下鑽」：

- 一頁建議 7–15 個核心元素；超過約 25 個應檢查是否混入第二種 concern。
- 主線最多 5–9 個穩定 processing stages。
- 流程方塊只放 `ID · 短動作`；Container 最多放 `ID · 名稱` 與一行 technology。
  Responsibility、evidence 與長清單移到 catalog。
- Edge crossing 不是美觀問題而已；交錯到無法順著主幹閱讀時應分層或下鑽。
- 不以縮小字體容納更多資訊；一般內容保持可在文件預覽中直接閱讀。

## Relationship Semantics

顏色只是輔助，edge label 必須在黑白列印時仍可理解。

| 關係 | 建議色彩 | 必備 label |
|---|---|---|
| P0 / primary path | 深灰粗實線 | protocol 或 primary product flow |
| Normal interaction | 灰實線 | information object / interaction purpose |
| Async / return / feedback | 藍灰虛線 | event、state、command 或 feedback |
| Cross-cut support | 灰色點線＋open arrow | storage、observability 或 shared support |

## State and Evidence

節點或關係若不是已確認的正常主線，必須標示：

- `CURRENT`：文件、code、deployment 或 owner 可確認。
- `OPTIONAL`：依 feature flag / environment 啟用。
- `LEGACY`：仍存在但不是主線。
- `MANUAL`：需要人員核准、搬移或 reload。
- `PARTIAL / TBD`：責任或 contract 未完全確認。
- `GAP / NOT IMPLEMENTED`：目標需要但現況沒有。

Evidence 應放在圖面 footer、catalog 或 source index，不把長篇證據塞入節點。

## Drill-down Gate

只有下列情況值得新增子圖：

- 一個 container 內有三個以上需跨團隊溝通的主要 component responsibility。
- 一條 information flow 有多個關鍵 protocol / persistence / async boundary。
- deployment 存在多環境、HA、device 或 network zone 差異。
- 圖面評審無法回答 owner 或 interface boundary。

子圖必須標示 parent `OP-xx`、`C-xx`、`I-xx` 或 `N-xx`。不要新增另一張沒有
parent 的 End-to-End overview。
