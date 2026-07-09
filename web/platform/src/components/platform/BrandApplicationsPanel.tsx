"use client";

// CR-0114 平台 console — 品牌申請審核 panel（「發案方審核」頁的分頁之一）。
// 列出 landing 送來的品牌/鎖店/經銷申請;核准(可填品牌代號)後顯示手動開站
// 指引文字(裁決 2:實際開站全人工);拒絕填原因。內部工具,文案直接繁中。

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { friendlyError } from "@/lib/apiError";
import { cacheInvalidate } from "@/lib/cache";

type Status = "pending" | "approved" | "rejected";

interface BrandApplication {
  id: string;
  application_type: "brand" | "locksmith" | "distributor";
  company_name: string;
  contact_name: string;
  tax_id: string;
  phone: string;
  email: string;
  address: string | null;
  notes: string | null;
  status: Status;
  slug: string | null;
  review_notes: string | null;
  reviewed_at: string | null;
  created_at: string | null;
  // 業界補充欄位(申請導入表單擴充)
  website: string | null;
  coverage_regions: string | null;
  store_count: number | null;
  expected_monthly_orders: string | null;
  main_brands: string | null;
  referral_source: string | null;
}

const TYPE_LABEL: Record<BrandApplication["application_type"], string> = {
  brand: "品牌商",
  locksmith: "鎖店",
  distributor: "經銷商",
};

const STATUS_LABEL: Record<Status, string> = {
  pending: "待審核",
  approved: "已核准",
  rejected: "已拒絕",
};

const STATUS_CLS: Record<Status, string> = {
  pending: "bg-amber-50 text-amber-700 border-amber-200",
  approved: "bg-green-50 text-green-700 border-green-200",
  rejected: "bg-gray-100 text-gray-600 border-gray-200",
};

export default function BrandApplicationsPanel() {
  const [filter, setFilter] = useState<Status>("pending");
  const [rows, setRows] = useState<BrandApplication[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [guide, setGuide] = useState<{ company: string; text: string } | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.get<{ data: BrandApplication[] }>(
        `/api/v1/platform/brand-applications?status=${filter}`,
      );
      setRows(res.data);
    } catch (err) {
      setError(friendlyError(err));
    } finally {
      setLoading(false);
    }
  }, [filter]);

  useEffect(() => {
    load();
  }, [load]);

  async function onApprove(app: BrandApplication) {
    const slug = window.prompt(
      `核准「${app.company_name}」\n請輸入品牌代號（3-30 字元，小寫英數與連字號，字母開頭；留空自動產生）：`,
      "",
    );
    if (slug === null) return; // 取消
    try {
      const res = await api.post<{ data: { onboarding_guide: string } }>(
        `/api/v1/platform/brand-applications/${app.id}:approve`,
        slug.trim() ? { slug: slug.trim() } : {},
      );
      setGuide({ company: app.company_name, text: res.data.onboarding_guide });
      cacheInvalidate("GET:"); // 清 30s GET 快取,否則 load() 讀到含此申請的舊清單
      await load();
    } catch (err) {
      window.alert(friendlyError(err));
    }
  }

  async function onReject(app: BrandApplication) {
    const reason = window.prompt(`拒絕「${app.company_name}」\n請輸入原因（至少 3 字）：`, "");
    if (reason === null) return;
    try {
      await api.post(`/api/v1/platform/brand-applications/${app.id}:reject`, { reason });
      cacheInvalidate("GET:"); // 清 30s GET 快取,否則 load() 讀到含此申請的舊清單
      await load();
    } catch (err) {
      window.alert(friendlyError(err));
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <p className="text-sm text-[var(--text-secondary)]">
        品牌／經銷／鎖店送來的平台導入「申請意向」（不含帳號）。核准後依開站指引手動部署該品牌 stack、聯絡申請人開通。
      </p>

      <div className="flex gap-2">
        {(["pending", "approved", "rejected"] as Status[]).map((s) => (
          <button
            key={s}
            type="button"
            onClick={() => setFilter(s)}
            className={`rounded-lg border px-3 py-1.5 text-sm transition ${
              filter === s
                ? "border-[var(--primary)] bg-[var(--primary)] text-white"
                : "border-[var(--border)] text-[var(--text-secondary)] hover:bg-[var(--bg-hover,rgba(0,0,0,0.04))]"
            }`}
          >
            {STATUS_LABEL[s]}
          </button>
        ))}
      </div>

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      {loading ? (
        <p className="text-sm text-[var(--text-secondary)]">載入中…</p>
      ) : rows.length === 0 ? (
        <p className="rounded-xl border border-[var(--border)] bg-[var(--bg-surface)] px-4 py-10 text-center text-sm text-[var(--text-secondary)]">
          目前沒有{STATUS_LABEL[filter]}的申請
        </p>
      ) : (
        <div className="flex flex-col gap-3">
          {rows.map((app) => (
            <div
              key={app.id}
              className="rounded-xl border border-[var(--border)] bg-[var(--bg-surface)] p-5"
            >
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="text-base font-semibold text-[var(--text-primary)]">
                      {app.company_name}
                    </span>
                    <span className="rounded-md border border-[var(--border)] px-2 py-0.5 text-xs text-[var(--text-secondary)]">
                      {TYPE_LABEL[app.application_type]}
                    </span>
                    <span className={`rounded-md border px-2 py-0.5 text-xs ${STATUS_CLS[app.status]}`}>
                      {STATUS_LABEL[app.status]}
                    </span>
                    {app.slug && (
                      <span className="rounded-md bg-[var(--bg-page)] px-2 py-0.5 font-mono text-xs text-[var(--text-secondary)]">
                        {app.slug}
                      </span>
                    )}
                  </div>
                  <div className="mt-2 grid gap-x-6 gap-y-1 text-sm text-[var(--text-secondary)] sm:grid-cols-2">
                    <span>聯絡人：{app.contact_name}</span>
                    <span>統編：{app.tax_id}</span>
                    <span>電話：{app.phone}</span>
                    <span>Email：{app.email}</span>
                    {app.website && (
                      <span className="sm:col-span-2">
                        網站：
                        <a
                          href={app.website}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-[var(--primary)] hover:underline"
                        >
                          {app.website}
                        </a>
                      </span>
                    )}
                    {app.address && <span className="sm:col-span-2">地址：{app.address}</span>}
                    {app.coverage_regions && <span>涵蓋地區：{app.coverage_regions}</span>}
                    {app.store_count != null && <span>門市/據點：{app.store_count}</span>}
                    {app.expected_monthly_orders && <span>預估月工單量：{app.expected_monthly_orders}</span>}
                    {app.main_brands && <span>主營品牌：{app.main_brands}</span>}
                    {app.referral_source && <span>得知來源：{app.referral_source}</span>}
                    {app.notes && <span className="sm:col-span-2">需求：{app.notes}</span>}
                    {app.review_notes && (
                      <span className="sm:col-span-2 text-[var(--text-primary)]">
                        審核備註：{app.review_notes}
                      </span>
                    )}
                  </div>
                </div>
                {app.status === "pending" && (
                  <div className="flex gap-2">
                    <button
                      type="button"
                      onClick={() => onApprove(app)}
                      className="rounded-lg bg-[var(--primary)] px-3 py-1.5 text-sm font-semibold text-white transition hover:opacity-90"
                    >
                      核准
                    </button>
                    <button
                      type="button"
                      onClick={() => onReject(app)}
                      className="rounded-lg border border-[var(--border)] px-3 py-1.5 text-sm text-[var(--text-secondary)] transition hover:bg-[var(--bg-hover,rgba(0,0,0,0.04))]"
                    >
                      拒絕
                    </button>
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* 核准後的開站指引 modal */}
      {guide && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
          onClick={(e) => {
            if (e.target === e.currentTarget) setGuide(null);
          }}
        >
          <div className="max-h-[85vh] w-full max-w-[680px] overflow-y-auto rounded-2xl border border-[var(--border)] bg-[var(--bg-surface)] p-6 shadow-lg">
            <div className="mb-3 flex items-center justify-between">
              <h3 className="text-lg font-bold text-[var(--text-primary)]">
                開站指引 — {guide.company}
              </h3>
              <button
                type="button"
                onClick={() => setGuide(null)}
                className="rounded-lg px-2 py-1 text-sm text-[var(--text-secondary)] hover:bg-[var(--bg-page)]"
              >
                關閉
              </button>
            </div>
            <p className="mb-3 text-sm text-[var(--text-secondary)]">
              已核准。開站流程為手動 —— 依下列步驟部署該品牌 stack，並聯絡申請人開通。
            </p>
            <pre className="overflow-x-auto whitespace-pre-wrap rounded-lg bg-[var(--bg-page)] p-4 font-mono text-xs leading-relaxed text-[var(--text-primary)]">
              {guide.text}
            </pre>
          </div>
        </div>
      )}
    </div>
  );
}
