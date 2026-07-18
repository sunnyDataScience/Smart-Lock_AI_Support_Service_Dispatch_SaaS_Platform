"use client";

// CR-0114 平台 console — 廠商帳號審核 panel(「發案方審核」頁的分頁之一)。
// vendors = 發案方登入帳號(role=vendor),品牌/經銷/鎖店註冊後 pending_approval,
// 核准即啟用可登入發案。審核職權自品牌後台移到平台方統一管。
// UAT W6-2:文案接 i18n(platform.vendors namespace)。

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { friendlyError } from "@/lib/apiError";
import { cacheInvalidate } from "@/lib/cache";
import { useActionDialog } from "@/components/ui/ActionDialog";
import { useToast } from "@/components/ui/Toast";
import { useTranslations } from "@/components/i18n/LocaleProvider";

type VendorStatus = "pending_approval" | "active" | "suspended" | "rejected";

interface Vendor {
  id: string;
  vendor_type: string;
  name: string;
  company_name: string | null;
  phone: string;
  email: string;
  address: string | null;
  status: VendorStatus;
  created_at: string | null;
}

const STATUS_CLS: Record<VendorStatus, string> = {
  pending_approval: "bg-[var(--badge-warn-bg)] text-[var(--badge-warn-fg)] border-[var(--badge-warn-fg)]/25",
  active: "bg-[var(--badge-success-bg)] text-[var(--badge-success-fg)] border-[var(--badge-success-fg)]/25",
  suspended: "bg-[var(--badge-danger-bg)] text-[var(--badge-danger-fg)] border-[var(--badge-danger-fg)]/25",
  rejected: "bg-[var(--badge-muted-bg)] text-[var(--badge-muted-fg)] border-[var(--border)]",
};

const FILTERS: (VendorStatus | "")[] = ["pending_approval", "active", "rejected", ""];

export default function VendorsPanel() {
  const actionDialog = useActionDialog();
  const { toast } = useToast();
  const t = useTranslations("platform.vendors");
  const tc = useTranslations("platform.common");
  const tf = useTranslations("platform.fields");
  const tt = useTranslations("platform.requestors.type");
  const [filter, setFilter] = useState<string>("pending_approval");
  const [items, setItems] = useState<Vendor[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const qs = filter ? `?status=${filter}` : "";
      const res = await api.get<{ items: Vendor[] }>(`/api/v1/platform/vendors${qs}`);
      setItems(res.items ?? []);
    } catch (e) {
      setError(friendlyError(e));
    } finally {
      setLoading(false);
    }
  }, [filter]);

  useEffect(() => {
    load();
  }, [load]);

  async function act(vendor: Vendor, action: "approve" | "reject") {
    const display = vendor.company_name || vendor.name;
    let body: Record<string, string> = {};
    if (action === "reject") {
      const reason = await actionDialog.open({
        title: t("rejectTitle", { name: display }),
        danger: true,
        confirmLabel: t("reject"),
        input: { label: t("rejectReasonLabel"), hint: t("rejectReasonHint") },
      });
      if (reason === null) return;
      body = { reason: typeof reason === "string" ? reason : "" };
    }
    setBusy(vendor.id);
    try {
      await api.post(`/api/v1/platform/vendors/${vendor.id}:${action}`, body);
      cacheInvalidate("GET:"); // 清 30s GET 快取,否則 load() 讀到含此廠商的舊清單
      await load();
      toast({
        title:
          action === "approve"
            ? t("approveDone", { name: display })
            : t("rejectDone", { name: display }),
        variant: "success",
      });
    } catch (e) {
      toast({ title: tc("actionFailed"), description: friendlyError(e), variant: "error" });
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <p className="text-sm text-[var(--text-secondary)]">{t("intro")}</p>

      <div className="flex gap-2">
        {FILTERS.map((value) => (
          <button
            key={value || "all"}
            type="button"
            onClick={() => setFilter(value)}
            className={`rounded-lg border px-3 py-1.5 text-sm transition ${
              filter === value
                ? "border-[var(--primary)] bg-[var(--primary)] text-white"
                : "border-[var(--border)] text-[var(--text-secondary)] hover:bg-[var(--bg-hover,rgba(0,0,0,0.04))]"
            }`}
          >
            {value === "" ? tc("all") : t(`status.${value}`)}
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
      ) : items.length === 0 ? (
        <p className="rounded-xl border border-[var(--border)] bg-[var(--bg-surface)] px-4 py-10 text-center text-sm text-[var(--text-secondary)]">
          {t("empty")}
        </p>
      ) : (
        <div className="flex flex-col gap-3">
          {items.map((v) => (
            <div
              key={v.id}
              className="rounded-xl border border-[var(--border)] bg-[var(--bg-surface)] p-5"
            >
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="text-base font-semibold text-[var(--text-primary)]">
                      {v.company_name || v.name}
                    </span>
                    <span className="rounded-md border border-[var(--border)] px-2 py-0.5 text-xs text-[var(--text-secondary)]">
                      {["brand", "locksmith", "distributor"].includes(v.vendor_type)
                        ? tt(v.vendor_type)
                        : v.vendor_type}
                    </span>
                    <span className={`rounded-md border px-2 py-0.5 text-xs ${STATUS_CLS[v.status]}`}>
                      {t(`status.${v.status}`)}
                    </span>
                  </div>
                  <div className="mt-2 grid gap-x-6 gap-y-1 text-sm text-[var(--text-secondary)] sm:grid-cols-2">
                    <span>{tf("contact")}{tc("colon")}{v.name}</span>
                    <span>{tf("phone")}{tc("colon")}{v.phone || "—"}</span>
                    <span>{tf("email")}{tc("colon")}{v.email || "—"}</span>
                    {v.address && (
                      <span className="sm:col-span-2">{tf("address")}{tc("colon")}{v.address}</span>
                    )}
                  </div>
                </div>
                {v.status === "pending_approval" && (
                  <div className="flex gap-2">
                    <button
                      type="button"
                      disabled={busy === v.id}
                      onClick={() => act(v, "approve")}
                      className="rounded-lg bg-[var(--primary)] px-3 py-1.5 text-sm font-semibold text-white transition hover:opacity-90 disabled:opacity-50"
                    >
                      {t("approve")}
                    </button>
                    <button
                      type="button"
                      disabled={busy === v.id}
                      onClick={() => act(v, "reject")}
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
    </div>
  );
}
