"use client";

import { useEffect } from "react";

/**
 * Root catastrophic error boundary
 *
 * 當 root layout 自己出錯時 Next.js 會 fallback 到這裡。
 *
 * 規範（不可違反）：
 *   - 必須是 Client Component
 *   - 必須自己渲染 `<html>` 與 `<body>`（取代壞掉的 root layout）
 *   - 不依賴 globals.css / next/font / 任何 layout-scoped 資源
 *     → 樣式必須完全內聯，否則可能跟著 layout 一起掛掉
 *
 * 此處刻意極簡：純 system font、原生 button、無外部圖示，
 * 確保最低渲染依賴。
 */
interface Props {
  error: Error & { digest?: string };
  // Next.js 會傳入 reset，但 root layout 級錯誤通常需要硬重整才會復原，
  // 故此處直接 window.location.reload() 而不呼叫 reset。
  reset: () => void;
}

export default function GlobalError({ error }: Props) {
  useEffect(() => {
    console.error("[global-error.tsx] catastrophic error", error);
  }, [error]);

  return (
    <html lang="zh-TW">
      <body
        style={{
          margin: 0,
          minHeight: "100vh",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          background: "#F8FAFC",
          padding: "48px 24px",
          fontFamily:
            'ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, "Noto Sans TC", sans-serif',
          color: "#0F172A",
          WebkitFontSmoothing: "antialiased",
        }}
      >
        <div
          style={{
            maxWidth: 480,
            width: "100%",
            textAlign: "center",
          }}
        >
          <div
            aria-hidden="true"
            style={{
              margin: "0 auto",
              width: 56,
              height: 56,
              borderRadius: "50%",
              border: "1px solid #E2E8F0",
              background: "#FFFFFF",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: 24,
              color: "#EF4444",
              fontWeight: 600,
            }}
          >
            !
          </div>

          <p
            style={{
              marginTop: 24,
              fontSize: 13,
              fontWeight: 500,
              letterSpacing: "0.05em",
              textTransform: "uppercase",
              color: "#64748B",
            }}
          >
            System Error
          </p>
          <h1
            style={{
              marginTop: 8,
              fontSize: 28,
              fontWeight: 600,
              lineHeight: 1.25,
            }}
          >
            系統發生嚴重錯誤
          </h1>
          <p
            style={{
              marginTop: 12,
              fontSize: 14,
              lineHeight: 1.6,
              color: "#64748B",
              maxWidth: 360,
              marginLeft: "auto",
              marginRight: "auto",
            }}
          >
            主程式無法正確載入。請重新整理頁面；若問題持續發生，請聯絡技術支援。
          </p>

          {error?.digest && (
            <p
              style={{
                marginTop: 16,
                display: "inline-block",
                padding: "4px 10px",
                fontSize: 12,
                fontFamily:
                  'ui-monospace, SFMono-Regular, Menlo, Consolas, monospace',
                color: "#64748B",
                background: "#FFFFFF",
                border: "1px solid #E2E8F0",
                borderRadius: 6,
              }}
            >
              Reference: {error.digest}
            </p>
          )}

          <div style={{ marginTop: 32 }}>
            <button
              type="button"
              onClick={() => window.location.reload()}
              style={{
                cursor: "pointer",
                padding: "8px 18px",
                fontSize: 14,
                fontWeight: 500,
                color: "#FFFFFF",
                background: "#2563EB",
                border: "none",
                borderRadius: 6,
                transition: "background 0.15s ease",
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.background = "#1D4ED8";
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = "#2563EB";
              }}
            >
              重新載入
            </button>
          </div>
        </div>
      </body>
    </html>
  );
}
