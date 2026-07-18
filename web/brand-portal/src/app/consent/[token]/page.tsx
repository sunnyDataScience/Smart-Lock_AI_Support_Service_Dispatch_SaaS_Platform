/**
 * /consent/[token] — 消費者匿名免責同意頁面（CR-0033）
 *
 * 入口：LINE 推播短連結（例：https://app.example.com/consent/<signed-token>）
 * 後端 v2（複用 work_order_status token）：
 *   GET  /consumer/consents/{token}  (getConsumerConsentsV2)  → 三段文本 + 同意狀態
 *   POST /consumer/consents/{token}  (submitConsumerConsentsV2, body {consents})
 *
 * 設計：mobile-first CSR、不帶 JWT、三段藍圖免責文本（待法務 sign-off）勾選提交。
 * 只處理法律文字 + 同意旗標，不顯示任何金額/成本。
 */

"use client";

import { use, useEffect, useState } from "react";
import { useTranslations } from "@/components/i18n/LocaleProvider";

type Params = { token: string };

// 用 || 而非 ??：Docker build-arg 未傳時 ENV 是空字串 ""（非 undefined），需一併 fallback
const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8001";

interface ConsentItem {
  consent_type: string;
  title: string;
  body: string;
  accepted: boolean;
  accepted_at: string | null;
}
interface ConsentView {
  text_version: string;
  consents: ConsentItem[];
}

type FetchState =
  | { kind: "loading" }
  | { kind: "ok"; data: ConsentView }
  | { kind: "error"; message: string; code: "expired" | "not_found" | "rate_limit" | "other" };

export default function PublicConsentPage({ params }: { params: Promise<Params> }) {
  const { token } = use(params);
  const t = useTranslations("pages.consentPublic");
  const [state, setState] = useState<FetchState>({ kind: "loading" });
  const [checks, setChecks] = useState<Record<string, boolean>>({});
  const [submitting, setSubmitting] = useState(false);
  const [done, setDone] = useState(false);

  async function load() {
    setState({ kind: "loading" });
    try {
      const res = await fetch(`${API_BASE}/consumer/consents/${encodeURIComponent(token)}`, {
        cache: "no-store",
        credentials: "omit",
      });
      if (res.status === 410) return setState({ kind: "error", code: "expired", message: t("errors.expired") });
      if (res.status === 429) return setState({ kind: "error", code: "rate_limit", message: t("errors.rateLimit") });
      // 其餘 4xx（400/404/422 等：token 格式不符 / 不存在）一律視為「連結無效或已過期」，
      // 避免把使用者導向「稍後再試」的暫時性錯誤誤導（UAT W2-5）
      if (res.status >= 400 && res.status < 500)
        return setState({ kind: "error", code: "not_found", message: t("errors.notFound") });
      if (!res.ok) return setState({ kind: "error", code: "other", message: t("errors.fail", { status: String(res.status) }) });
      const data = (await res.json()) as ConsentView;
      setState({ kind: "ok", data });
      setChecks(Object.fromEntries(data.consents.map((c) => [c.consent_type, c.accepted])));
      setDone(data.consents.every((c) => c.accepted));
    } catch {
      setState({ kind: "error", code: "other", message: t("errors.network") });
    }
  }

  useEffect(() => {
    let cancelled = false;
    (async () => {
      if (!cancelled) await load();
    })();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  async function submit() {
    setSubmitting(true);
    try {
      const res = await fetch(`${API_BASE}/consumer/consents/${encodeURIComponent(token)}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "omit",
        body: JSON.stringify({ consents: checks }),
      });
      if (res.ok) {
        setDone(true);
        await load();
      } else {
        setState({ kind: "error", code: "other", message: t("errors.fail", { status: String(res.status) }) });
      }
    } catch {
      setState({ kind: "error", code: "other", message: t("errors.network") });
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="min-h-screen bg-slate-50 px-4 py-8">
      <div className="mx-auto max-w-md rounded-lg bg-white p-6 shadow">
        <h1 className="text-xl font-semibold text-slate-900">{t("title")}</h1>
        {state.kind === "loading" && <ConsentSkeleton />}
        {state.kind === "error" && <ErrorPanel message={state.message} code={state.code} />}
        {state.kind === "ok" && (
          <ConsentForm
            data={state.data}
            checks={checks}
            setChecks={setChecks}
            submitting={submitting}
            done={done}
            onSubmit={submit}
          />
        )}
      </div>
    </main>
  );
}

function ConsentSkeleton() {
  const t = useTranslations("pages.consentPublic");
  return (
    <div data-testid="consent-skeleton" className="mt-6 animate-pulse space-y-3" aria-busy="true" aria-label={t("skeletonLabel")}>
      <div className="h-16 w-full rounded bg-slate-100" />
      <div className="h-16 w-full rounded bg-slate-100" />
      <div className="h-16 w-full rounded bg-slate-100" />
      <div className="h-10 w-full rounded bg-slate-200" />
    </div>
  );
}

function ErrorPanel({
  message,
  code,
}: {
  message: string;
  code: "expired" | "not_found" | "rate_limit" | "other";
}) {
  const t = useTranslations("pages.consentPublic");
  return (
    <div role="alert" data-testid="consent-error" data-error-code={code} className="mt-6 rounded border border-red-200 bg-red-50 p-4 text-sm text-red-700">
      <p className="font-medium">{t("errorTitle")}</p>
      <p className="mt-1 text-[13px]">{message}</p>
    </div>
  );
}

function ConsentForm({
  data,
  checks,
  setChecks,
  submitting,
  done,
  onSubmit,
}: {
  data: ConsentView;
  checks: Record<string, boolean>;
  setChecks: (c: Record<string, boolean>) => void;
  submitting: boolean;
  done: boolean;
  onSubmit: () => void;
}) {
  const t = useTranslations("pages.consentPublic");
  const allChecked = data.consents.every((c) => checks[c.consent_type]);

  return (
    <div className="mt-6 space-y-4" data-testid="consent-form">
      <p className="text-[13px] text-slate-500">{t("intro")}</p>
      {data.consents.map((c) => (
        <label
          key={c.consent_type}
          className="flex cursor-pointer gap-3 rounded-lg border border-slate-200 p-3 hover:bg-slate-50"
        >
          <input
            type="checkbox"
            data-testid={`consent-${c.consent_type}`}
            checked={!!checks[c.consent_type]}
            onChange={(e) => setChecks({ ...checks, [c.consent_type]: e.target.checked })}
            className="mt-1 h-4 w-4 shrink-0"
          />
          <span>
            <span className="block text-sm font-medium text-slate-800">{c.title}</span>
            <span className="mt-1 block text-[12px] leading-relaxed text-slate-500">{c.body}</span>
          </span>
        </label>
      ))}

      {done ? (
        <div data-testid="consent-done" className="rounded-md bg-green-50 px-3 py-3 text-center text-[13px] text-green-700">
          {t("done")}
        </div>
      ) : (
        <button
          data-testid="consent-submit"
          disabled={submitting || !allChecked}
          onClick={onSubmit}
          className="w-full rounded-md bg-[var(--primary,#2563eb)] px-4 py-3 text-sm font-semibold text-white disabled:opacity-50"
        >
          {submitting ? t("submitting") : allChecked ? t("submit") : t("submitHint")}
        </button>
      )}
      <p className="text-center text-[11px] text-slate-400">{t("versionNote", { v: data.text_version })}</p>
    </div>
  );
}
