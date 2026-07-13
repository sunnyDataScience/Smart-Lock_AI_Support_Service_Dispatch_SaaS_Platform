"use client";

import { useEffect, useState } from "react";

/**
 * IdleLogoutNotice — 因閒置逾時被自動登出後（IdleLogoutGuard 導向 `?reason=idle`），
 * 在登入頁顯示一則說明，避免使用者不解「為何突然被登出」。可關閉。
 * 系統安全訊息，一律繁體中文（與 CLAUDE.md user-facing 文字規範一致）。
 */
export default function IdleLogoutNotice() {
  const [show, setShow] = useState(false);

  useEffect(() => {
    if (new URLSearchParams(window.location.search).get("reason") === "idle") {
      setShow(true);
    }
  }, []);

  if (!show) return null;

  return (
    <div
      role="status"
      className="mb-4 flex items-start gap-2 rounded-lg border border-[var(--warning)]/30 bg-[var(--warning)]/10 px-4 py-3 text-[13px] leading-relaxed text-[var(--text-secondary)]"
    >
      <svg
        width="16"
        height="16"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
        className="mt-0.5 shrink-0 text-[var(--warning)]"
        aria-hidden="true"
      >
        <circle cx="12" cy="12" r="10" />
        <path d="M12 6v6l4 2" />
      </svg>
      <span>因閒置逾時，為保護帳號安全已自動登出，請重新登入。</span>
      <button
        type="button"
        onClick={() => setShow(false)}
        aria-label="關閉提示"
        className="ml-auto shrink-0 text-[var(--text-tertiary)] hover:text-[var(--text-secondary)]"
      >
        ×
      </button>
    </div>
  );
}
