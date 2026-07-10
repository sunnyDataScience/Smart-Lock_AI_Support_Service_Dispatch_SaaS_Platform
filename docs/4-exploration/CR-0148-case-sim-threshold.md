# CR-0148 — 案例檢索門檻隨模型校正(M2 Playwright 實機檢查發現)

- **日期**:2026-07-10
- **觸發**:M2 UI 實機檢查——refinery 核可落地後,語意明確相符的中文改寫查詢 0 命中
- **根因**:ADR-010 門檻 0.85 係按 text-embedding-004 設想;CR-0124 換 multilingual-002 後從未重校。實測真改寫 sim≈0.743 → 0.85 恆不命中(案例檢索形同虛設)
- **修**:`CASE_SIMILARITY_THRESHOLD` → env `RAG_CASE_SIM_THRESHOLD` 可調,預設 0.70(高於雜訊、涵蓋真改寫);註解記實測依據
- **驗證**:修後命中 sim=0.743;rag 測試綠。門檻精調隨語料量增長再校(golden_qa 擴充時)

### 進度

- ✅ done(merge 7041bdf8):門檻 env 化預設 0.70,rag 測試綠;CHANGELOG/completion-status 補記於 2026-07-10 文件同步輪
