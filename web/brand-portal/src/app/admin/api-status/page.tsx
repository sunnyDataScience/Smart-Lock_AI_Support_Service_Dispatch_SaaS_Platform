"use client";

/**
 * /admin/api-status — Backend smoke page.
 *
 * 用於本機驗證 web ↔ api 串接：
 *   - 登入流程（POST /api/v1/auth/login，flat-keep P4 才扁平化）→ 寫入 localStorage tokens
 *   - 查 system config（GET /api/v1/config，track-B 待 CR-0004）→ 顯示 JSON
 *   - 查通知列表（GET /tenants/{tid}/notifications，P3 已遷 v2）→ 顯示前 5 筆
 *
 * 需要：NEXT_PUBLIC_API_BASE_URL 指向跑著的 api/ uvicorn。
 */

import { useState } from "react";
import { api, auth, login, logout, tenantPath } from "@/lib/api";
import { friendlyError } from "@/lib/apiError";
import Sidebar from "@/components/layout/Sidebar";

export default function ApiStatusPage() {
  const [email, setEmail] = useState("test@lock-ai.com");
  const [password, setPassword] = useState("");
  const [config, setConfig] = useState<unknown>(null);
  const [notifications, setNotifications] = useState<unknown>(null);
  const [loggedIn, setLoggedIn] = useState<boolean>(
    typeof window !== "undefined" && !!auth.getAccessToken(),
  );
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState<string | null>(null);

  const run = async (label: string, fn: () => Promise<void>) => {
    setError(null);
    setLoading(label);
    try {
      await fn();
    } catch (e) {
      setError(
        friendlyError(e),
      );
    } finally {
      setLoading(null);
    }
  };

  return (
    <div className="flex h-screen">
      <Sidebar />
      <main className="flex-1 overflow-auto bg-[var(--bg-canvas)] p-8">
        <div className="mx-auto flex max-w-3xl flex-col gap-6">
          <div>
            <h1 className="text-2xl font-bold">API Status</h1>
            <p className="text-sm text-[var(--text-secondary)]">
              Smoke test for backend connectivity. Base URL:{" "}
              <code className="rounded bg-slate-100 px-2 py-0.5 text-xs">
                {process.env.NEXT_PUBLIC_API_BASE_URL ?? "(unset)"}
              </code>
            </p>
          </div>

          {error && (
            <div className="rounded border border-red-200 bg-red-50 p-3 text-sm text-red-700">
              {error}
            </div>
          )}

          <section className="rounded-xl border border-[var(--border)] bg-white p-6">
            <h2 className="mb-3 text-lg font-semibold">1. 登入</h2>
            {!loggedIn ? (
              <div className="flex flex-col gap-3">
                <input
                  className="rounded border px-3 py-2"
                  placeholder="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                />
                <input
                  className="rounded border px-3 py-2"
                  type="password"
                  placeholder="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                />
                <button
                  className="rounded bg-blue-600 px-4 py-2 text-white disabled:opacity-50"
                  disabled={loading === "login" || !password}
                  onClick={() =>
                    run("login", async () => {
                      await login(email, password);
                      setLoggedIn(true);
                    })
                  }
                >
                  {loading === "login" ? "登入中…" : "登入"}
                </button>
              </div>
            ) : (
              <div className="flex items-center gap-3 text-sm">
                <span className="text-green-700">已登入</span>
                <button
                  className="rounded border px-3 py-1 text-sm"
                  onClick={() =>
                    run("logout", async () => {
                      await logout();
                      setLoggedIn(false);
                      setConfig(null);
                      setNotifications(null);
                    })
                  }
                >
                  登出
                </button>
              </div>
            )}
          </section>

          <section className="rounded-xl border border-[var(--border)] bg-white p-6">
            <div className="mb-3 flex items-center justify-between">
              <h2 className="text-lg font-semibold">2. GET /api/v1/config</h2>
              <button
                className="rounded border px-3 py-1 text-sm disabled:opacity-50"
                disabled={!loggedIn || loading === "config"}
                onClick={() =>
                  run("config", async () => {
                    // P3-KEEP: track-B (待 CR-0004)
                    setConfig(await api.get("/api/v1/config"));
                  })
                }
              >
                {loading === "config" ? "載入中…" : "Fetch"}
              </button>
            </div>
            {config !== null && (
              <pre className="overflow-auto rounded bg-slate-900 p-3 text-xs text-slate-100">
                {JSON.stringify(config, null, 2)}
              </pre>
            )}
          </section>

          <section className="rounded-xl border border-[var(--border)] bg-white p-6">
            <div className="mb-3 flex items-center justify-between">
              <h2 className="text-lg font-semibold">
                3. GET /tenants/{"{tid}"}/notifications
              </h2>
              <button
                className="rounded border px-3 py-1 text-sm disabled:opacity-50"
                disabled={!loggedIn || loading === "notifs"}
                onClick={() =>
                  run("notifs", async () => {
                    setNotifications(
                      await api.get(tenantPath("/notifications"), {
                        query: { limit: 5 },
                      }),
                    );
                  })
                }
              >
                {loading === "notifs" ? "載入中…" : "Fetch"}
              </button>
            </div>
            {notifications !== null && (
              <pre className="overflow-auto rounded bg-slate-900 p-3 text-xs text-slate-100">
                {JSON.stringify(notifications, null, 2)}
              </pre>
            )}
          </section>
        </div>
      </main>
    </div>
  );
}
