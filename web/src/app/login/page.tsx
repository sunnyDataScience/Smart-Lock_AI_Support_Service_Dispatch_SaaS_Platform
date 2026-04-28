"use client";

import { Lock } from "lucide-react";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";
import { ApiError, login } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await login(email.trim(), password);
      router.replace("/dashboard");
    } catch (e) {
      if (e instanceof ApiError) {
        setError(`${e.errorCode} (${e.status})：${e.message}`);
      } else if (e instanceof Error) {
        setError(e.message);
      } else {
        setError(String(e));
      }
      setLoading(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-[var(--bg-page)] px-4">
      <div className="w-full max-w-[400px] rounded-2xl border border-[var(--border)] bg-[var(--bg-surface)] p-8 shadow-sm">
        <div className="mb-6 flex flex-col items-center gap-3">
          <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-[var(--primary)]">
            <Lock className="h-6 w-6 text-white" />
          </div>
          <div className="flex flex-col items-center gap-1">
            <h1 className="text-xl font-bold text-[var(--text-primary)]">
              登入 SmartLock Admin
            </h1>
            <p className="text-sm text-[var(--text-secondary)]">
              請輸入您的帳號與密碼
            </p>
          </div>
        </div>

        <form onSubmit={onSubmit} className="flex flex-col gap-4">
          <label className="flex flex-col gap-[6px]">
            <span className="text-[13px] font-semibold text-[var(--text-primary)]">
              Email
            </span>
            <input
              type="email"
              autoComplete="username"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              disabled={loading}
              className="h-10 rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] px-3 text-sm text-[var(--text-primary)] outline-none focus:border-[var(--border-focus)] disabled:opacity-50"
              placeholder="admin@example.com"
            />
          </label>

          <label className="flex flex-col gap-[6px]">
            <span className="text-[13px] font-semibold text-[var(--text-primary)]">
              密碼
            </span>
            <input
              type="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              disabled={loading}
              className="h-10 rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] px-3 text-sm text-[var(--text-primary)] outline-none focus:border-[var(--border-focus)] disabled:opacity-50"
              placeholder="••••••••"
            />
          </label>

          {error && (
            <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={loading || !email || !password}
            className="h-10 rounded-lg bg-[var(--primary)] text-sm font-medium text-white transition hover:bg-[var(--primary-hover)] disabled:opacity-50"
          >
            {loading ? "登入中…" : "登入"}
          </button>
        </form>

        {/* TODO: remove dev hint before prod */}
        <p className="mt-6 text-center text-xs text-[var(--text-disabled)]">
          測試帳號：admin@example.com / changeme123
        </p>
      </div>
    </div>
  );
}
