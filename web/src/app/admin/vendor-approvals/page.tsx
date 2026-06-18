"use client";

import { useCallback, useEffect, useState } from "react";
import { Store, Check, X } from "lucide-react";
import Sidebar from "@/components/layout/Sidebar";
import { ApiError, api, tenantPath } from "@/lib/api";
import { useTranslations } from "@/components/i18n/LocaleProvider";

interface Vendor {
  id: string;
  vendor_type: string;
  name: string;
  company_name: string | null;
  phone: string;
  email: string;
  address: string | null;
  status: string;
  created_at: string | null;
}

const VTYPE: Record<string, string> = {
  brand: "品牌商",
  locksmith: "鎖店",
  distributor: "經銷商",
};

export default function VendorApprovalsPage() {
  const t = useTranslations("admin.vendorApprovals");
  const [items, setItems] = useState<Vendor[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  const fetchPending = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.get<{ items: Vendor[] }>(
        tenantPath("/vendors"),
        { query: { status: "pending_approval" } },
      );
      setItems(res.items ?? []);
    } catch (e) {
      setError(e instanceof ApiError ? `${e.errorCode} (${e.status})：${e.message}` : String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchPending();
  }, [fetchPending]);

  async function act(vendorId: string, action: "approve" | "reject") {
    setBusy(vendorId);
    try {
      if (action === "reject") {
        const reason = window.prompt(t("rejectReasonPrompt")) ?? undefined;
        await api.post(tenantPath(`/vendors/${vendorId}:reject`), { reason });
      } else {
        await api.post(tenantPath(`/vendors/${vendorId}:approve`), {});
      }
      setItems((prev) => prev.filter((v) => v.id !== vendorId));
    } catch (e) {
      setError(e instanceof ApiError ? `${e.errorCode} (${e.status})：${e.message}` : String(e));
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="flex h-full bg-[var(--bg-page)]">
      <Sidebar />
      <div className="flex flex-1 flex-col overflow-hidden">
        <div className="flex items-center gap-3 border-b border-[var(--border)] bg-[var(--bg-surface)] pl-14 pr-4 md:px-8 py-5">
          <Store className="h-7 w-7 text-[var(--primary)]" />
          <h1 className="text-2xl font-bold text-[var(--text-primary)]">{t("title")}</h1>
          <span className="text-[13px] text-[var(--text-secondary)]">
            {t("pendingCount", { n: items.length })}
          </span>
        </div>

        <div className="flex-1 overflow-auto pl-14 pr-4 md:px-8 py-6">
          {error && (
            <div className="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
              {error}
            </div>
          )}
          {loading ? (
            <p className="text-sm text-[var(--text-secondary)]">{t("loading")}</p>
          ) : items.length === 0 ? (
            <p className="text-sm text-[var(--text-disabled)]">{t("empty")}</p>
          ) : (
            <div className="overflow-hidden rounded-lg border border-[var(--border)] bg-[var(--bg-surface)]">
              <table className="w-full text-sm">
                <thead className="bg-[#F8FAFC] text-xs text-[var(--text-secondary)]">
                  <tr>
                    <th className="px-4 py-3 text-left">{t("colName")}</th>
                    <th className="px-4 py-3 text-left">{t("colType")}</th>
                    <th className="px-4 py-3 text-left">{t("colContact")}</th>
                    <th className="px-4 py-3 text-right">{t("colAction")}</th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((v) => (
                    <tr key={v.id} className="border-t border-[var(--border)]">
                      <td className="px-4 py-3">
                        <div className="font-medium text-[var(--text-primary)]">{v.company_name || v.name}</div>
                        <div className="text-[12px] text-[var(--text-secondary)]">{v.name}</div>
                      </td>
                      <td className="px-4 py-3 text-[var(--text-secondary)]">{VTYPE[v.vendor_type] ?? v.vendor_type}</td>
                      <td className="px-4 py-3 text-[var(--text-secondary)]">
                        <div>{v.phone}</div>
                        <div className="text-[12px]">{v.email}</div>
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex justify-end gap-2">
                          <button
                            disabled={busy === v.id}
                            onClick={() => act(v.id, "approve")}
                            className="flex items-center gap-1 rounded-md bg-green-600 px-3 py-1.5 text-[13px] font-semibold text-white hover:bg-green-700 disabled:opacity-60"
                          >
                            <Check className="h-4 w-4" />
                            {t("approve")}
                          </button>
                          <button
                            disabled={busy === v.id}
                            onClick={() => act(v.id, "reject")}
                            className="flex items-center gap-1 rounded-md border border-[var(--border)] px-3 py-1.5 text-[13px] font-semibold text-[var(--text-secondary)] hover:bg-[var(--bg-page)] disabled:opacity-60"
                          >
                            <X className="h-4 w-4" />
                            {t("reject")}
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
