# SQL/seeds/

> Demo / fixture seed data for E2E tests + dashboard 演示。
>
> **PII NOTICE**: 任何含真實技師、客戶、或合作夥伴 PII 的資料 **絕不** 進此目錄。
> 真實名冊請存於 Secret Manager 或 ops repo。
> 本 README 為 CR-0006 partial 的成果（取代 docs/2-contracts/master-data/technicians.PII-WARNING.md）。

## 檔案清單

執行順序見各 SQL 檔頂的「前置」註解。常見入口：
- `_admin_user.sql` → `dispatcher_user.sql` → `technicians.sql` → `work_orders.sql`

## 已知 demo accounts

- `demo-admin@example.com` / `adminpass123`（admin）
- `demo-tech@example.com` / `techpass123`（technician）

## 對應 docs

- `docs/2-contracts/master-data/` — master data 設計
- `docs/2-contracts/modules/MC-0015-rbac.md` — 角色權限矩陣
