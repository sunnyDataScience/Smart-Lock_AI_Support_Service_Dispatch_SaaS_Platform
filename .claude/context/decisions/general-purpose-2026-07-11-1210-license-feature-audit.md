# License 功能查證報告（規格 vs 實作）

- **日期**: 2026-07-11 12:10
- **任務**: 查證 License 功能實作現況（業主提問）
- **範圍**: smartlock-docs 全套規格＋api/SQL/web/agent/scripts 全樹 code

## 結論

- License 執行面**零實作**（8 條「未實作」主張經同義詞反查全數 CONFIRMED），與 WBS 排程一致非漏做。
- 規格定義單一：Casdoor subscription＝開通閘門，控 ①per-brand bundle 部署權＋綁 LINE ②附加模組集（refinery/Studio/Compiler）。
- 已存在的只有三件互不相連的資料面殘樁：
  1. 平台庫 `tenant.plan` 欄（Schema_platform.sql:148，註解自標「MVP 未用」；唯讀曝露於 GET /platform/tenants，無任何寫入路徑）
  2. `casdoor_bootstrap.py` 把 plan 同步進 Casdoor org properties（「資料面就緒」，但 oidc.py 消費端只取身分三鍵、不讀 plan）
  3. refinery（唯一「License 附加模組」實例）開通＝運維手動 `docker compose --profile refinery up`，零程式化 gate
- 未做：enforcement／plan 寫入路徑／模組開通 API／console License 管理 UI／brand 端 plan 條件渲染／license key・到期日資料結構／品牌庫 plan 欄。
- 排程：WBS 2.1.1「License 訂閱管理」屬 🔶 未做半邊（R1/R2=IdP/OIDC 已落地）；3.3.1 License→provisioning 自動化＋3.5.1 第 2 品牌開站演練＝M3 階段二 ⬜（設計凍結）。
- 開放待決：15_SDS §設計待決(d) 未購精煉 License 租戶語料歸屬；ADR-004 重評條款（複雜規則→外掛 license 服務）。

## 影響評估

- **嚴重度**: MEDIUM（商業模式核心能力，但依 roadmap 屬 M3 前置未到期）
- 若要實作：涉 API contract＋external integration（Casdoor subscription 消費）→ 依 change-governance 須先 CIA
