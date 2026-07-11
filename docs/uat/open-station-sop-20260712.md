# 品牌開站 SOP（CR-0166 R5 / WBS 3.3.1＋3.5.1，M3 Release gate）

- **日期**：2026-07-12
- **範圍**：第 2 品牌租戶「申請 → 核准 → 開站 → 綁 LINE」標準流程，及 provisioning 自動化工具。
- **工具**：`scripts/deploy/provision_brand.py`（CR-0166 R5）。

## 開站流程（申請 → 上線）

| 步 | 動作 | 執行者 | 工具／端點 |
|---|---|---|---|
| 1 | 品牌於 landing `/platform/apply` 送申請 | 品牌方 | `POST /platform/brand-applications` |
| 2 | 平台審核佇列核准（設 slug） | 平台管理員 | `POST /platform/brand-applications/{id}:approve` → **自動登錄 tenant registry** |
| 3 | 設 License（訂閱級距＋開通模組） | 平台管理員 | platform console → 租戶管理 → **License** 鈕（`PUT /platform/tenants/{id}/license`） |
| 4 | 產生部署參數檔＋開站 checklist | 平台/OPS | `provision_brand.py --slug <slug> --tenant-id <uuid> --plan-tier <tier> --modules <...>` |
| 5 | Casdoor org 同步 | OPS | `scripts/idp/casdoor_bootstrap.py --org <slug>` |
| 6 | Secret Manager 建 secrets | OPS | POSTGRES_URI／API_JWT_SECRET_KEY／INTERNAL_API_TOKEN／LINE_CHANNEL_* |
| 7 | compose 起站（本機/自架）或 Cloud Run 部署（上雲＝R6） | OPS | `BRAND=<slug> docker compose ... up`；prod 走 `scripts/deploy/{api,web,agent}.sh` |
| 8 | LINE 綁定：webhook URL＋rich menu | OPS | LINE console＋`setup_rich_menu.py` |
| 9 | 建品牌 Admin 帳號 → 通知申請人開通 | 平台管理員 | — |

## provisioning 自動化（provision_brand.py）

原 `_onboarding_guide` 只產文字步驟；本工具把「產部署參數檔＋設 License」腳本化：

```bash
# dry-run（驗證＋顯示 checklist，不寫檔/不動 DB）
uv run python scripts/deploy/provision_brand.py --slug acme --dry-run

# 實際（寫 brands/<slug>.env + 設 License；需 PLATFORM_POSTGRES_URI）
PLATFORM_POSTGRES_URI=... uv run python scripts/deploy/provision_brand.py \
    --slug acme --tenant-id <uuid> --plan-tier pro --modules refinery,studio
```

- 產出 `scripts/deploy/brands/<slug>.env`（自 locksmart.env 模板改 PROJECT_ID／service 名／AGENT_TENANT_ID）；已存在則不覆蓋。
- 設 `tenant.entitled_modules`（platform 庫）——與 R3 License gate 同源，refinery 等模組 gate 即時生效。
- Casdoor／secrets／compose／LINE 仍列 checklist（需人工或 R6 上雲自動化）。

## 第 2 品牌開站演練（dry-run 驗證，M3 Release gate）

2026-07-12 於 live platform 庫實測「acme-demo」全鏈（驗後即清）：

1. ✅ 登錄 tenant registry（模擬核准連動）→ tenant_id 產生。
2. ✅ `provision_brand.py` 產部署參數檔＋設 License（pro＋refinery）→ 平台庫 `entitled_modules=["core","refinery"]` 驗證。
3. ✅ refinery 模組 gate（`is_refinery_entitled`）對此租戶回 `True`（開通生效）；對 core-only 租戶回 `False`（未開通擋）。
4. ✅ provision 冪等（.env 已存在不覆蓋；License upsert）。

**結論**：申請→核准→租戶登錄→License→模組 gate 全鏈自動化貫通。**剩餘＝上雲部署（R6，需 GCP 協同）＋真實 LINE 通道綁定**（測試通道以外需申請人提供 channel secret）。

## 尚未自動化（誠實邊界）

- **實際部署**（compose up／Cloud Run deploy）：本工具產參數不執行部署；prod 走 R6 上雲腳本＋GCP 協同。
- **Casdoor org／secrets／LINE 綁定**：列 checklist，需 OPS 執行（Casdoor bootstrap 已有腳本）。
- **技師庫接入**：全品牌共用權威庫（CR-0112），開站不需每品牌建技師庫。
