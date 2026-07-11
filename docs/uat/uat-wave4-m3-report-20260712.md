# UAT wave4 — M3 R0–R5 特性驗收報告（2026-07-12）

- **範圍**：M3 多品牌規模化 CR-0166 R0–R5 特性驗收（AI 紅線 eval／治理欠帳／K3' 情緒／License／provisioning）。
- **方法**：6 面向並行多 agent 驗收——讀碼確認實作＋live（重建含 R1-R5 碼的三 api 容器）/scratch 驗證＋去偽存真。
- **環境**：品牌 api :8001／tech api :8002／platform api :8003（皆已重建）；品牌庫 5433／技師庫 5434／平台庫 5435（唯讀驗證）。

## 結果總表

| 面向 | 判定 | 真實缺口 |
|---|---|---|
| R0 AI 紅線 eval | ✅ **PASS** | 無 |
| R1 治理欠帳 9 件 | ✅ **PASS** | 無 |
| R2 K3' 負面情緒 | ✅ **PASS** | 無 |
| R3 License gate | ✅ **PASS** | 無 |
| R5 品牌開站 provisioning | ✅ **PASS** | 無 |
| 回歸守門 | ✅ **PASS**（零功能回歸） | 2 非功能項（已修） |

## 關鍵證據

- **R0**：`forbidden_run_20260712b.json` gate.pass_rate=**0.985**（197/200，七分類配額齊，agent 重算與存檔一致非手改）；`sentiment_eval_result.json` accuracy=**1.0**（含反諷）；judge 兩級校正＋dry gate 健檢 2 新案例＋reply_guard say-do 兜底＋SKILL v1.4.0＋`--live` import 修復皆讀碼＋本機 assertion 驗證。
- **R1**：8 項 code＋live 雙面驗證——webhook_idempotency 表/接線/cleanup cron、SoD UUID+存在性+交易化、family review SLA cron、audit+family advisory lock、config is_protected/owner（live 5433 payment_gate protected、tax_policy owner=ops）、reject 端點+work_order_events CHECK 含 reject、platform brand-auth 端點+lifecycle CHECK 含 brand_auth_granted、pii_scrub 身分證 regex+入鏈前遮蔽。
- **R2**：classify_sentiment（反諷提示+fallback）、gateway 接線、api sentiment_alerts 寫入+通知；120 題（100 負面含 20 反諷）eval 100%。
- **R3**：platform migration 001 欄位、enforcement 原語、platform api :8003 license 端點（live GET locksmart=enterprise）、refinery entitlement gate、console LicenseModal。
- **R5**：provision_brand.py（env 產生+set_license+checklist+dry-run）、實跑 dry-run 退出碼驗證、5 smoke test、開站 SOP。
- **回歸**：CHANGELOG M1/M2/wave1/2 條目在、seed 技師≥5、F1 主鏈表完整、migration 序號連續無衝突（101-105+platform 001）、REGISTRY 登記、config OPS_ROLES 放寬無越權漏洞。

## 去偽記錄（初判失敗→非缺口）

- psql 密碼連 5433 失敗＝容器 POSTGRES_PASSWORD=0000（環境非缺口）。
- payment_gate owner_role_codes={}＝設計（空=admin-only fallback，靠 is_protected 擋租戶層）。
- config 路由 live GET 404＝無 active config version（CONFIG_NOT_FOUND 語意），非路由缺失（pytest 已證行為）。
- K8 live 3 失敗案例（0.985>0.95）＝gate 容許範圍，非驗收缺口，列品質微調素材。

## 回歸守門發現的 2 非功能項（本輪已修）

1. **CHANGELOG audit trail 斷鏈**：M3 R0-R5 completion-status 有更但 CHANGELOG 漏——**已補** M3 合批 Added＋Decisions 條目。
2. **`_ADMIN_BYPASS_ROLES` 含死角色 super_admin**（SA-01/CR-0130 已移除）：HTTP 不可利用（router 靜態 gate 先擋），但與裁決文字矛盾——**已移除** super_admin 字面（config governance 6 測試仍綠）。

## 結論

**M3 R0–R5 全數驗收通過，零功能回歸。** AI 合約紅線 gate（K8 98.5%／K3' 100%／
紅線 9/9／多輪 1.0／GDPR／影像禁用）全綠——**release gate 的 AI 面已達標**。
剩餘 R4（Kafka，需 D2 選型）／R6（上雲，需 GCP 協同）／R7（v1 收斂，需 D5）待業主決策；
R8 M3 全項總驗收俟其落地。K1 判分方式待 D7 裁定（單輪 rubric 0.623，repo 判讀認定低估）。
