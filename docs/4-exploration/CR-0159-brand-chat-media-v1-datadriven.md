# CR-0159 — brand 對話附件以 data-driven URL 持續消費 v1 media（v1 下架風險）

- **日期**：2026-07-11（CR-0157 調查覆核員查實，業主裁決另開 CR）
- **狀態**：backlog（🛑 待排程；屬 v1 cutover 前置事實）
- **觸發面向**：API contract（v1 deprecation 決策依據）

## §1 事實

- brand-portal 對話頁 `ChatTimeline.tsx`（AuthChatImage）用 **server 回傳的 `media_url`** 取附件圖——該 URL 指向 v1 `GET /api/v1/media/{id}`（`routers/media.py`）。
- 這種 **data-driven 消費在前端程式碼 grep 不到路徑字串**——CR-0157 的 router×站台矩陣把 `media.py` 標成「無站台使用」，覆核員抓到此漏判並更正為「brand 間接使用」。
- 另查實：brand `components/work-orders/MediaGallery.tsx` 全站無 import（死碼）；「證據包」端點屬 work_orders_v2 非 media_v2。

## §2 含義與修法方向

1. **v1 cutover 鐵律**：任何 v1 router 下架前，必須比對 server 端 `deprecation_metrics` 實際命中率（30 天窗），不可只憑前端靜態掃描——存在 media_url 這類 server 產生的 URL 消費。
2. 收斂修法（擇一或並行）：①server 端改發 v2 media URL（`/tenants/{tid}/media/{id}` 形狀）②前端 AuthChatImage 對 media_url 做 v1→v2 改寫。順帶清 MediaGallery 死碼。

## §8 Human Decisions Required

1. 併入未來 v1 cutover 輪（CR-0157 選項 C 前置①）處理，或先行小修？（建議：併 cutover 輪，本 CR 作為該輪的已知事實輸入）
