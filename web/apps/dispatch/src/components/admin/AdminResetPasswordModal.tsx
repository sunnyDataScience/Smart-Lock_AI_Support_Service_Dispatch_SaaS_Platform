"use client";

/**
 * AdminResetPasswordModal — 管理員代為重設使用者密碼（A4，會議 2026-06-10 Action #7）。
 *
 * 機制（業主裁決）：免 email 基礎設施。admin 輸入目標使用者 email → 後端
 * 重設為隨機臨時密碼並回傳明文 → admin 把臨時密碼轉達使用者 → 使用者登入後
 * 自行用「變更密碼」改回。
 *
 * 端點：POST /api/v1/auth/admin-reset-password（role_required("admin")；
 * X-Tenant-ID 由 api client 自動注入,service 層限同租戶）。
 */

import { useState } from "react";
import { X, KeyRound, Copy, Check } from "lucide-react";
import { ApiError, api } from "@shared/lib/api";
import { friendlyError } from "@shared/lib/apiError";

interface Props {
  onClose: () => void;
}

interface ResetResult {
  email: string;
  temp_password: string;
}

export default function AdminResetPasswordModal({ onClose }: Props) {
  const [email, setEmail] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<ResetResult | null>(null);
  const [copied, setCopied] = useState(false);

  const emailValid = /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email.trim());

  async function handleSubmit() {
    if (!emailValid || submitting) return;
    setSubmitting(true);
    setError(null);
    try {
      const res = await api.post<{ data: ResetResult }>(
        "/api/v1/auth/admin-reset-password",
        { email: email.trim() },
      );
      setResult(res.data);
    } catch (e) {
      // 404 USER_NOT_FOUND / 403 FORBIDDEN / 其他
      setError(
        e instanceof ApiError
          ? e.status === 404
            ? "找不到此 email 的使用者（限本租戶）"
            : friendlyError(e)
          : e instanceof Error
            ? e.message
            : String(e),
      );
    } finally {
      setSubmitting(false);
    }
  }

  async function handleCopy() {
    if (!result) return;
    try {
      await navigator.clipboard.writeText(result.temp_password);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      /* clipboard 不可用時忽略,使用者仍可手動選取 */
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      onClick={onClose}
    >
      <div
        className="w-full max-w-md rounded-xl border border-[var(--border)] bg-[var(--bg-surface)] p-6 shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between">
          <h2 className="flex items-center gap-2 text-[16px] font-semibold text-[var(--text-primary)]">
            <KeyRound className="h-4 w-4 text-[var(--primary)]" />
            重設使用者密碼
          </h2>
          <button
            onClick={onClose}
            className="flex h-8 w-8 items-center justify-center rounded-lg hover:bg-[var(--bg-page)]"
            aria-label="關閉"
          >
            <X className="h-4 w-4 text-[var(--text-secondary)]" />
          </button>
        </div>

        {!result ? (
          <>
            <p className="mt-2 text-[13px] text-[var(--text-secondary)]">
              輸入要重設的使用者 email，系統會產生臨時密碼。請將臨時密碼轉達該使用者，
              登入後請其自行至「變更密碼」改回。
            </p>
            <label className="mt-4 block">
              <span className="text-[12px] font-medium text-[var(--text-secondary)]">
                使用者 Email
              </span>
              <input
                type="email"
                inputMode="email"
                autoFocus
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleSubmit()}
                placeholder="user@example.com"
                className="mt-1 h-10 w-full rounded-lg border border-[var(--border)] bg-[var(--bg-page)] px-3 text-sm text-[var(--text-primary)] outline-none focus:border-[var(--border-focus)]"
              />
            </label>

            {error && (
              <div className="mt-3 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-[13px] text-red-700">
                {error}
              </div>
            )}

            <div className="mt-5 flex justify-end gap-2">
              <button
                onClick={onClose}
                className="rounded-lg border border-[var(--border)] px-4 py-2 text-sm text-[var(--text-secondary)] hover:bg-[var(--bg-page)]"
              >
                取消
              </button>
              <button
                onClick={handleSubmit}
                disabled={!emailValid || submitting}
                className="rounded-lg bg-[var(--primary)] px-4 py-2 text-sm font-medium text-white hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {submitting ? "重設中…" : "重設密碼"}
              </button>
            </div>
          </>
        ) : (
          <div className="mt-4">
            <p className="text-[13px] text-[var(--text-secondary)]">
              已重設 <strong className="text-[var(--text-primary)]">{result.email}</strong> 的密碼。
              請複製以下臨時密碼並安全地轉達該使用者：
            </p>
            <div className="mt-3 flex items-center gap-2 rounded-lg border border-[var(--border)] bg-[var(--bg-page)] px-3 py-2">
              <code className="flex-1 select-all font-mono text-[15px] text-[var(--text-primary)]">
                {result.temp_password}
              </code>
              <button
                onClick={handleCopy}
                className="flex h-8 w-8 items-center justify-center rounded-lg hover:bg-[var(--bg-surface)]"
                title="複製"
              >
                {copied ? (
                  <Check className="h-4 w-4 text-green-600" />
                ) : (
                  <Copy className="h-4 w-4 text-[var(--text-secondary)]" />
                )}
              </button>
            </div>
            <p className="mt-2 text-[11px] text-[var(--text-disabled)]">
              此密碼僅顯示一次。基於安全，請勿以未加密管道（如公開群組）傳遞。
            </p>
            <div className="mt-5 flex justify-end">
              <button
                onClick={onClose}
                className="rounded-lg bg-[var(--primary)] px-4 py-2 text-sm font-medium text-white hover:opacity-90"
              >
                完成
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
