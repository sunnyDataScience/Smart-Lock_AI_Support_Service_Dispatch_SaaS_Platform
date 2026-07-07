# 02_能力資產層 — 生成 prompt

## 02-1 知識與模型能力分層【附錄 B】

四層:Skill 行為層(git-tracked 可攜:locksmith-cs-sop 紅線決策樹/product-knowledge 精選)/RAG 事實層(品牌庫 pgvector 唯一事實語料,🔜 語義層,RAG-via-MCP)/per-user 記憶(agent.* schema,BUILD/SAVE,default deny)/Model Orchestration Layer(LiteLLM 供應商無關字串路由)。知識精煉回流虛線指向 04-4。

## 02-2 AI 邊界紅線治理【附錄 C】

中央=AI 客服(LockCore)。四周紅線卡:工具白名單僅 6 項;transfer_to_human 唯一入口(兜底);AI 永不(建工單/派工/金流/final quote/折扣/免費保固/複誦金額/影像辨識);200 題禁區 Eval <95% 阻擋部署;rule_triggered_by 確定性引擎寫入;prompt injection 攔截 ≥95%。底部:「AI 職責僅限對話判斷與知識回覆」。
