/**
 * 可觀測性基線（CR-0156 / ADR-007 可觀測性補課）——OTLP opt-in，未配置＝零行為變化。
 *
 * 範式比照 api/core/observability.py（brand-portal 為四站參考實作；2026-07-22
 * 三站複製完成＝tech-portal/landing/platform-console 皆同範式接線）：
 *   - `OTEL_EXPORTER_OTLP_ENDPOINT` 設定時：動態載入 @vercel/otel 啟用 OTel
 *     （Next.js 自動 http span，含路由/method/status），OTLP 匯出到 SigNoz collector。
 *   - 未設定：**no-op**——直接 return，連 @vercel/otel 都不 import（單機/測試/本機
 *     零行為變化、零額外載入）。
 *   - 匯入/初始化任何失敗＝降級 no-op + console.warn（可觀測性不可癱瘓服務）。
 *
 * PII 面（25_Monitoring §3 硬性要求之風險註記）：
 *   本站無自訂 server span 屬性；@vercel/otel 自動 http span 僅含路由/status 等
 *   標準屬性。token 一律走 Authorization header、不入 URL query（SPA 統一由
 *   src/lib/api.ts 注入 Bearer header），cookie 不進 span 屬性——URL 帶 token 的
 *   洩漏面不存在，風險低。深度遮蔽已落地：`observability/piiScrub.ts` 自訂
 *   SpanProcessor（[scrub, 'auto']，出站前遮蔽字串屬性，比照 api
 *   `_PIIScrubExporter`）——四站共同遞延項本輪銷案。
 *
 * Next.js 15 instrumentation hook 預設啟用（本站 next 15.5.x，不需
 * experimental.instrumentationHook），Next 於 server 啟動時呼叫 register()。
 */

/**
 * Next.js instrumentation 進入點。
 * OTLP endpoint 未設＝完全 no-op；設定時啟用 @vercel/otel。絕不 throw。
 */
export async function register(): Promise<void> {
  // opt-in 前線：env 未配置＝完全 no-op，不觸發任何 import 副作用
  const endpoint = (process.env.OTEL_EXPORTER_OTLP_ENDPOINT ?? "").trim();
  if (!endpoint) {
    return;
  }

  try {
    // 動態 import：套件缺失（例如未來被移出依賴）時走 catch 安靜降級
    const { registerOTel } = await import("@vercel/otel");
    const { PIIScrubSpanProcessor } = await import("./observability/piiScrub");
    registerOTel({
      // OTEL_SERVICE_NAME 可覆寫（與 api setup_observability 同語意）
      serviceName: process.env.OTEL_SERVICE_NAME || "brand-portal",
      // PII 深度遮蔽（25_Monitoring §3）：scrub 在前、'auto'（預設匯出）在後
      spanProcessors: [new PIIScrubSpanProcessor(), "auto"],
    });
  } catch (error) {
    // 降級 no-op：可觀測性初始化失敗絕不癱瘓站台
    console.warn(
      "[observability] OTel 初始化失敗（@vercel/otel 缺失或註冊錯誤）→ 降級停用",
      error,
    );
  }
}
