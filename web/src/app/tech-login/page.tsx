"use client";

import { Wrench } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";
import { ApiError, loginTechnician } from "@/lib/api";

export default function TechLoginPage() {
  const router = useRouter();
  const [identifier, setIdentifier] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await loginTechnician(identifier.trim(), password);
      router.replace("/pool");
    } catch (e) {
      setError(
        e instanceof ApiError
          ? `${e.errorCode} (${e.status})：${e.message}`
          : e instanceof Error
            ? e.message
            : String(e),
      );
      setLoading(false);
    }
  }

  return (
    <div
      className="flex min-h-screen w-full justify-center"
      style={{
        background:
          "linear-gradient(180deg, #2563EB 0%, #1E40AF 60%, #F8FAFC 60%)",
      }}
    >
      <div className="flex min-h-screen w-full max-w-[480px] flex-col bg-transparent px-6 pt-[env(safe-area-inset-top,0)]">
        {/* brand_header_mobile */}
        <header className="mt-12 flex flex-col items-center gap-2 text-white">
          <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-white/20 backdrop-blur">
            <Wrench className="h-7 w-7 text-white" />
          </div>
          <h1 className="mt-1 text-[20px] font-bold">Smart Lock</h1>
          <p className="text-[14px] opacity-90">技師工作台</p>
        </header>

        {/* tech_login_form */}
        <main className="mt-10 flex-1">
          <form
            onSubmit={onSubmit}
            className="flex flex-col gap-4 rounded-2xl bg-white p-6 shadow-2xl"
          >
            <h2 className="text-[16px] font-semibold text-[var(--text-primary)]">
              登入
            </h2>

            <label className="flex flex-col gap-[6px]">
              <span className="text-[12px] font-medium text-[var(--text-secondary)]">
                手機號碼或 Email
              </span>
              <input
                type="text"
                inputMode="email"
                autoComplete="username"
                required
                value={identifier}
                onChange={(e) => setIdentifier(e.target.value)}
                className="h-12 rounded-lg border border-[var(--border)] px-3 text-[15px] focus:border-[var(--primary)] focus:outline-none"
                placeholder="0912xxxxxx 或 tech@example.com"
              />
            </label>

            <label className="flex flex-col gap-[6px]">
              <span className="text-[12px] font-medium text-[var(--text-secondary)]">
                密碼
              </span>
              <input
                type="password"
                autoComplete="current-password"
                required
                minLength={4}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="h-12 rounded-lg border border-[var(--border)] px-3 text-[15px] focus:border-[var(--primary)] focus:outline-none"
                placeholder="••••••"
              />
            </label>

            {error && (
              <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-[12px] text-red-700">
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={loading || !identifier || !password}
              className="mt-2 h-12 rounded-lg bg-[var(--primary)] text-[15px] font-semibold text-white hover:bg-[#1D4ED8] disabled:opacity-60"
            >
              {loading ? "登入中…" : "登入"}
            </button>

            <div className="mt-2 flex items-center justify-between text-[12px]">
              <button
                type="button"
                disabled
                className="text-[var(--text-disabled)]"
                title="V2.0 規劃"
              >
                忘記密碼（待補）
              </button>
              <Link href="/login" className="text-[var(--primary)] hover:underline">
                我是管理員 →
              </Link>
            </div>
          </form>
        </main>

        {/* mobile_footer */}
        <footer className="my-6 text-center text-[11px] text-[var(--text-disabled)]">
          v0.1 — 技師端 PWA
        </footer>
      </div>
    </div>
  );
}
