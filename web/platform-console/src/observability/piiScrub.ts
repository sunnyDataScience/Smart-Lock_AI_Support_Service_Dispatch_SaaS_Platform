/**
 * OTel span 屬性 PII 深度遮蔽（25_Monitoring §3 硬性要求）——四站共同遞延項銷案。
 *
 * 範式移植 api/core/pii_scrub.py 與 agent/lockcore/observability.py：regex 順序
 * 有意義（LINE uid 先於 token；電話先於地址）。掛法＝自訂 SpanProcessor 於 onEnd
 * 就地遮蔽字串屬性，registerOTel({ spanProcessors: [scrub, "auto"] })——陣列順序
 * 即執行順序，'auto'（預設 Batch+OTLP 匯出）在後 → 出站前必先過遮蔽。
 * 遮蔽失敗絕不 throw（可觀測性不可癱瘓服務；該 span 屬性原樣照出）。
 * 本檔四站位元組級一致（brand-portal / tech-portal / landing / platform-console）。
 */
import type { ReadableSpan, Span, SpanProcessor } from "@opentelemetry/sdk-trace-base";

const LINE_UID_RE = /\bU[0-9a-f]{32}\b/g;
const TOKEN_PARAM_RE = /((?:access_|refresh_)?token=)[^&\s]+/g;
const EMAIL_RE = /[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}/g;
const PHONE_RE =
  /(?:\+886[-\s]?9\d{2}|09\d{2})[-\s]?\d{3}[-\s]?\d{3}|\b0\d{1,2}-\d{6,8}\b/g;
const ADDR_RE =
  /\S{1,6}[縣市]\S{0,12}?[區鄉鎮市]?\S{0,20}?(?:路|街|大道|巷|弄)[\S]{0,12}?號?/g;

function hashLineUid(uid: string): string {
  try {
    // 64-bit FNV-1a 僅產生穩定 pseudonymous fingerprint；LINE UID 本身為
    // 128-bit 隨機識別碼。純 JS 實作可同時在 Node/Edge/client fallback 編譯，
    // 避免 instrumentation 將 node:crypto 誤帶進 Next.js browser bundle。
    let fingerprint = BigInt("0xcbf29ce484222325");
    for (const char of uid) {
      fingerprint ^= BigInt(char.charCodeAt(0));
      fingerprint = BigInt.asUintN(
        64,
        fingerprint * BigInt("0x100000001b3"),
      );
    }
    return "U#" + fingerprint.toString(16).padStart(16, "0").slice(0, 12);
  } catch {
    return "[LINE_UID]";
  }
}

/** 單一字串遮蔽：LINE uid（雜湊）→ token 參數 → email → 電話 → 地址。 */
export function scrubText(value: string): string {
  let v = value.replace(LINE_UID_RE, hashLineUid);
  v = v.replace(TOKEN_PARAM_RE, "$1[TOKEN]");
  v = v.replace(EMAIL_RE, "[EMAIL]");
  v = v.replace(PHONE_RE, "[PHONE]");
  v = v.replace(ADDR_RE, "[ADDR]");
  return v;
}

/** 出站前遮蔽 processor：只動 string / string[] 屬性，數值與 bool 原樣。 */
export class PIIScrubSpanProcessor implements SpanProcessor {
  onStart(_span: Span): void {
    // 進場不動作——屬性在 span 生命週期內可能續增，統一於 onEnd 遮蔽
  }

  onEnd(span: ReadableSpan): void {
    try {
      const attrs = span.attributes as Record<string, unknown> | undefined;
      if (!attrs) return;
      for (const key of Object.keys(attrs)) {
        const v = attrs[key];
        if (typeof v === "string") {
          const s = scrubText(v);
          if (s !== v) attrs[key] = s;
        } else if (Array.isArray(v) && v.some((i) => typeof i === "string")) {
          attrs[key] = v.map((i) => (typeof i === "string" ? scrubText(i) : i));
        }
      }
    } catch {
      // 遮蔽失敗絕不影響 span 匯出（該 span 屬性原樣照出）
    }
  }

  forceFlush(): Promise<void> {
    return Promise.resolve();
  }

  shutdown(): Promise<void> {
    return Promise.resolve();
  }
}
