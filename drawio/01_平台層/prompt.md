# 01_平台層 — 生成 prompt

## 01-1 部署三分層(enterprise 12_SAD §2)

三個大 container:
- ① per-brand bundle(藍,每品牌一套物理隔離可獨立部署):web 品牌後台 :3000、api 派工控制平面 :8001(API_SURFACE 塑形)、agent(LockCore LINE Bot)、品牌庫 PostgreSQL+pgvector、Redis、MCP-RAG server。
- ② 集中共用平台(綠,跨品牌我方營運):Casdoor(IdP/租戶/License)、SigNoz+OPIK、technician-platform(tech-api :8002+師傅 web :3001+技師庫)、Kafka 🔜 階段二、平台 console :3003+platform-api :8003+平台庫。
- ③ License 附加模組(青):knowledge-refinery(精煉管線+HITL 審核 UI)。
重點跨層線:api→Casdoor(OIDC 🔜,點線)、全部→SigNoz(點線)、api→tech-api(OHS:派工/requote,實線)、refinery→品牌庫 pgvector(核可後灌語料,虛線回流)。註:「品牌不依賴任何共享元件即可自成一套上線(ADR-002)」。

## 01-2 平台核心 vs 領域配置(Vertical Pack)【附錄 A,🔜 階段二】

左(綠)平台核心永不隨產業改:工單引擎/共用元件庫/金流軌/RBAC/事件骨幹。右(黃)Vertical Pack:field_metadata/flow DSL/catalog/knowledge/ui_composition/blocks。中間「pack@version 裝載+租戶覆寫」。註記 FDE 4 配置面與三鐵律;標「業主裁決 2026-07-07:全數列產品階段二」。
