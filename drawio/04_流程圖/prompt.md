# 04_流程圖 — 生成 prompt

## 04-2 跨系統資料流 DAG

主鏈:LINE→agent→問題卡→小編確認→線上報價→LIFF 確認→工單→OHS 派工→技師平台接單→現場(requote command 回流 ADR-027)→完工硬閘→計費 Billing→commission.accrued(🔜 Kafka)→技師平台 Settlement→reconcile 閘門。知識支線(虛線):messages 三方全量存檔(BR-CONV-03)+knowledge_ready 卡→knowledge-refinery→pgvector/skill→agent RAG 回流。

## 04-3 Sequence — 單次工單全程(報價先行)

參與者:客戶/AI 客服/派工小編/報價引擎/技師/系統。依 BRD §5.6:進線→意圖→轉真人+草擬卡→補齊確認→建線上報價送出→Flex 推送→客戶同意→customer_confirmed→1-click 開單→派工→接單到場門檢→【opt:現場報價不符→requote v+1→LIFF 確認→復工】→施工完工→客戶確認結案。註急件 carve-out。

## 04-4 知識精煉閉環(HITL MLOps)

環形:輸入汲取(診斷對話+素材)→Medallion raw→bronze→silver→LLM 提煉分流(事實/行為)→HITL 審核 UI→落地(pgvector+skill)→agent RAG-via-MCP→回到下一輪。中央註 BR-CONV-03 資料前提;角落註 License 附加+與 AI Onboarding Compiler 孿生對稱(階段二)。
