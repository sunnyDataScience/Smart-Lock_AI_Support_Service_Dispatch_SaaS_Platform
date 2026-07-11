# 多 agent 調查報告 — repo 佈局重整（CR-0157 前置）

- **日期**: 2026-07-11 10:30
- **任務**: 盤點 api 按站台四拆、rag→agent/、refinery→knowledge-pipeline/ 的耦合與部署面
- **範圍**: api/ 109 routers 全量、web/ 四站 src、17 個 CI workflows、全部 Dockerfile/compose/scripts/deploy

## 結論

- api「分開啟用」在部署層已存在：API_SURFACE env 分流三實例（:8001 dispatch 帶 11 worker、:8002 tech、:8003 platform）＋三庫物理分離；landing 零 API 消費。
- router 歸屬：46 brand 獨佔／6 platform 獨佔（/api/v1/platform 前綴＋獨立庫，最乾淨可切）／3 tech 獨佔／5 brand↔tech 共用（auth、work_orders_v2、work_orders_ops_v2、notifications_v2、media_v2——恰為業務核心）／49（45%）無站台使用（33 v1 遺留＋5 機器消費者＋11 未上線 v2）。
- 檔案層複製四拆會 fork 工單核心 domain 與 auth 雙身分語意；CI 契約鏈（單 main:app＋單 openapi.yaml：types 生成、v1-freeze、schemathesis、e2e、mock/spec-lint）整條要重做。
- rag 搬遷 7 個會壞檔＋rag/rag 四支 parents[2] 路徑推導（embedding.py 會靜默改讀 agent/.env）；deploy 腳本零 rag 引用。
- refinery 搬遷 6 個會壞檔；與 kp 零 import 耦合；唯一部署入口=brand compose profile=refinery。
- 既有缺口：uv-lock-check 漏 refinery pyproject；refinery image 不在 docker-build-smoke；rag/refinery 測試零 CI。
- 既有 bug 兩件：tech-portal /me/commission-statements 後端無對應 route；brand 對話附件仍走 v1 media（data-driven URL，grep 不到）→ v1 cutover 須靠 deprecation_metrics。

## 行動項目

- [ ] CR-0157 §8 等業主裁決（api 選 A/B/C，建議 C；rag/refinery 搬遷建議同輪執行）
- [ ] 裁決後依 CR-0157 §9 實作（原子更新 pyproject+uv.lock+Dockerfile stub）

## 影響評估

- **嚴重度**: HIGH（architecture boundary）
- **影響範圍**: uv workspace 全體、三個 Python image、brand compose、17 個 workflow 中 15 個
- 詳細證據: CR-0157＋scratchpad wf-*.json（本 session）
