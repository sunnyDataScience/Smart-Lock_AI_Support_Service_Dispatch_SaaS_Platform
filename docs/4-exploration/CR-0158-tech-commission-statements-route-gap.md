# CR-0158 — tech-portal 佣金對帳單前後端脫鉤（頁面打的 route 後端不存在）

- **日期**：2026-07-11（CR-0157 調查途中查實，業主裁決另開 CR）
- **狀態**：backlog（🛑 待排程；實作前依本 CIA §8 補裁決）
- **觸發面向**：API contract（前後端契約斷裂）

## §1 事實

- tech-portal `account/commission-statements` 頁實際呼叫 `GET /tenants/{tid}/me/commission-statements`。
- `api/routers/` 全樹**無此 route**——只有 `api/main.py` tech surface keep-list 保留了該路徑前綴（CR-0112/0114 塑形時先行），router 沒跟上。頁面被打開即 404。
- 相近既有面：`technician_commission_v2.py` 提供 `/technicians/{techId}/commission-summary`（品牌管理面視角），與 `/me/...`（師傅自助視角）契約形狀不同；`technician_statement_v2.py`（師傅 AP 對帳單）是另一資源。

## §2 修法選項

| 選項 | 做法 |
|---|---|
| A | 補 `/tenants/{tid}/me/commission-statements` route（對齊前端既有呼叫；資料源接佣金月結 saas 表） |
| B | 前端改打既有端點（若語意可對上）；keep-list 移除死前綴 |

## §8 Human Decisions Required

1. 選 A/B？（建議先查 16_API_Spec 是否已凍結 `/me/commission-statements` 形狀——spec 有則 A 是唯一解）
2. 排程：獨立小輪或併師傅面下一輪。
