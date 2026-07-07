# 00_總覽 — 生成 prompt

> 對象:Smart Lock AI 客服與派工 SaaS 平台(enterprise 文件集 00-27)。

## 00-1 商業模式與營運鏈心智模型

畫三層水平堆疊 + 右側縱向脊椎:
- 上層(黃,設計態)「商業模式 — License 開通」:per-brand bundle(每品牌一套物理隔離單體+綁 LINE 官方帳號)/附加模組 License 加購(knowledge-refinery、Agent Studio)/集中共用平台(我方營運)。
- 中層(紅,即時鏈)「營運全鏈路(單品牌)」:客服(AI 問題卡)→報價(客戶 LIFF 確認)→派工(工單)→維修(現場複核/存證)→結算(計費/對帳),粗實線串接;註記「報價先行:客人確認後才派工;急件 4 類事後補審」。
- 下層(綠,平台共用)「平台核心 — 產業無關」:工單狀態機引擎(flow DSL)/金流軌(append-only)/四方 RBAC/事件骨幹 🔜。
- 脊椎(橘色縱向粗箭頭):「知識精煉閉環+積木飛輪(階段二)」。
- 底部橫幅:「通用工單維運核心 + 產業配置層(Vertical Pack)——藍領營運的商業邏輯編譯器」。

## 00-2 System Context (C4 L1)

中心=本平台(6 子系統+集中共用)。actor:終端客戶(LINE)/品牌營運人員/簽約技師(跨品牌)/平台管理員/潛在加盟品牌。外部系統:LINE Platform(webhook/LIFF/Flex)、LLM 供應商(經 LiteLLM 字串路由)、GCP(Cloud Run/Secret Manager/Cloud SQL)、產品素材源(YouTube/官網/手冊)。連線標互動語意(報修/確認報價/接單/存證/requote…)。
