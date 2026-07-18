"use client";

// CR-0114 平台 console — 品牌申請審核 panel(「發案方審核」頁的分頁之一)。
// 列出 landing 送來的品牌/鎖店/經銷申請;核准(可填品牌代號)後顯示手動開站
// 指引文字(裁決 2:實際開站全人工);拒絕填原因。
// UAT W6-2:文案接 i18n(platform.brandApps namespace)。
// UAT W3-6:已駁回申請的 review_notes 以「駁回理由」明確標示(原僅通稱審核備註)。

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { friendlyError } from "@/lib/apiError";
import { cacheInvalidate } from "@/lib/cache";
import { useActionDialog } from "@/components/ui/ActionDialog";
import { useToast } from "@/components/ui/Toast";
import { useTranslations } from "@/components/i18n/LocaleProvider";

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

const STATUS_CLS: Record<Status, string> = {
  pending: "bg-[var(--badge-warn-bg)] text-[var(--badge-warn-fg)] border-[var(--badge-warn-fg)]/25",
  approved: "bg-[var(--badge-success-bg)] text-[var(--badge-success-fg)] border-[var(--badge-success-fg)]/25",
  rejected: "bg-[var(--badge-muted-bg)] text-[var(--badge-muted-fg)] border-[var(--border)]",
};

export default function BrandApplicationsPanel() {
  const actionDialog = useActionDialog();
  const { toast } = useToast();
  const t = useTranslations("platform.brandApps");
  const tc = useTranslations("platform.common");
  const tf = useTranslations("platform.fields");
  const tt = useTranslations("platform.requestors.type");
  const [filter, setFilter] = useState<Status>("pending");
  const [rows, setRows] = useState<BrandApplication[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  // R3:審核中鎖定按鈕,避免連點重複送出
  const [busyId, setBusyId] = useState<string | null>(null);
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
    const slug = await actionDialog.open({
      title: t("approveTitle", { name: app.company_name }),
      description: t("approveDesc"),
      confirmLabel: t("approve"),
      input: {
        label: t("slugLabel"),
        placeholder: t("slugPlaceholder"),
        mono: true,
        hint: t("slugHint"),
      },
    });
    if (slug === null) return; // 取消
    setBusyId(app.id);
    try {
      const res = await api.post<{ data: { onboarding_guide: string } }>(
        `/api/v1/platform/brand-applications/${app.id}:approve`,
        typeof slug === "string" && slug ? { slug } : {},
      );
      setGuide({ company: app.company_name, text: res.data.onboarding_guide });
      cacheInvalidate("GET:"); // 清 30s GET 快取,否則 load() 讀到含此申請的舊清單
      await load();
      toast({ title: t("approveDone", { name: app.company_name }), variant: "success" });
    } catch (err) {
      toast({ title: t("approveFailed"), description: friendlyError(err), variant: "error" });
    } finally {
      setBusyId(null);
    }
  }

  async function onReject(app: BrandApplication) {
    const reason = await actionDialog.open({
      title: t("rejectTitle", { name: app.company_name }),
      danger: true,
      confirmLabel: t("reject"),
      input: { label: t("rejectReasonLabel"), minLength: 3 },
    });
    if (reason === null) return;
    setBusyId(app.id);
    try {
      await api.post(`/api/v1/platform/brand-applications/${app.id}:reject`, { reason });
      cacheInvalidate("GET:"); // 清 30s GET 快取,否則 load() 讀到含此申請的舊清單
      await load();
      toast({ title: t("rejectDone", { name: app.company_name }), variant: "success" });
    } catch (err) {
      toast({ title: t("rejectFailed"), description: friendlyError(err), variant: "error" });
    } finally {
      setBusyId(null);
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <p className="text-sm text-[var(--text-secondary)]">{t("intro")}</p>

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
            {t(`status.${s}`)}
          </button>
        ))}
      </div>

      {error && (
        <div className="rounded-lg border border-[var(--badge-danger-fg)]/25 bg-[var(--badge-danger-bg)] px-4 py-3 text-sm text-[var(--badge-danger-fg)]">
          {error}
        </div>
      )}

      {loading ? (
        <p className="text-sm text-[var(--text-secondary)]">{tc("loading")}</p>
      ) : rows.length === 0 ? (
        <p className="rounded-xl border border-[var(--border)] bg-[var(--bg-surface)] px-4 py-10 text-center text-sm text-[var(--text-secondary)]">
          {t("empty", { status: t(`status.${filter}`) })}
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
                      {tt(app.application_type)}
                    </span>
                    <span className={`rounded-md border px-2 py-0.5 text-xs ${STATUS_CLS[app.status]}`}>
                      {t(`status.${app.status}`)}
                    </span>
                    {app.slug && (
                      <span className="rounded-md bg-[var(--bg-page)] px-2 py-0.5 font-mono text-xs text-[var(--text-secondary)]">
                        {app.slug}
                      </span>
                    )}
                  </div>
                  <div className="mt-2 grid gap-x-6 gap-y-1 text-sm text-[var(--text-secondary)] sm:grid-cols-2">
                    <span>{tf("contact")}{tc("colon")}{app.contact_name}</span>
                    <span>{tf("taxId")}{tc("colon")}{app.tax_id}</span>
                    <span>{tf("phone")}{tc("colon")}{app.phone}</span>
                    <span>{tf("email")}{tc("colon")}{app.email}</span>
                    {app.website && (
                      <span className="sm:col-span-2">
                        {tf("website")}{tc("colon")}
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
                    {app.address && (
                      <span className="sm:col-span-2">{tf("address")}{tc("colon")}{app.address}</span>
                    )}
                    {app.coverage_regions && (
                      <span>{t("coverageRegions")}{tc("colon")}{app.coverage_regions}</span>
                    )}
                    {app.store_count != null && (
                      <span>{t("storeCount")}{tc("colon")}{app.store_count}</span>
                    )}
                    {app.expected_monthly_orders && (
                      <span>{t("expectedMonthlyOrders")}{tc("colon")}{app.expected_monthly_orders}</span>
                    )}
                    {app.main_brands && (
                      <span>{t("mainBrands")}{tc("colon")}{app.main_brands}</span>
                    )}
                    {app.referral_source && (
                      <span>{t("referralSource")}{tc("colon")}{app.referral_source}</span>
                    )}
                    {app.notes && (
                      <span className="sm:col-span-2">{t("notes")}{tc("colon")}{app.notes}</span>
                    )}
                    {app.review_notes && (
                      // W3-6:駁回時 review_notes 即駁回理由——用明確標籤+警示色呈現,
                      // 讓「已拒絕」清單一眼看到當初的駁回原因(核准備註維持通稱)。
                      <span
                        className={`sm:col-span-2 ${
                          app.status === "rejected"
                            ? "text-[var(--badge-danger-fg)]"
                            : "text-[var(--text-primary)]"
                        }`}
                      >
                        {app.status === "rejected" ? t("rejectReason") : t("reviewNotes")}
                        {tc("colon")}
                        {app.review_notes}
                      </span>
                    )}
                  </div>
                </div>
                {app.status === "pending" && (
                  <div className="flex gap-2">
                    <button
                      type="button"
                      disabled={busyId === app.id}
                      onClick={() => onApprove(app)}
                      className="rounded-lg bg-[var(--primary)] px-3 py-1.5 text-sm font-semibold text-white transition hover:opacity-90 disabled:opacity-50"
                    >
                      {t("approve")}
                    </button>
                    <button
                      type="button"
                      disabled={busyId === app.id}
                      onClick={() => onReject(app)}
                      className="rounded-lg border border-[var(--border)] px-3 py-1.5 text-sm text-[var(--text-secondary)] transition hover:bg-[var(--bg-hover,rgba(0,0,0,0.04))] disabled:opacity-50"
                    >
                      {t("reject")}
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
                {t("guideTitle", { company: guide.company })}
              </h3>
              <button
                type="button"
                onClick={() => setGuide(null)}
                className="rounded-lg px-2 py-1 text-sm text-[var(--text-secondary)] hover:bg-[var(--bg-page)]"
              >
                {tc("close")}
              </button>
            </div>
            <p className="mb-3 text-sm text-[var(--text-secondary)]">{t("guideDesc")}</p>
            <pre className="overflow-x-auto whitespace-pre-wrap rounded-lg bg-[var(--bg-page)] p-4 font-mono text-xs leading-relaxed text-[var(--text-primary)]">
              {guide.text}
            </pre>
          </div>
        </div>
      )}
    </div>
  );
}
