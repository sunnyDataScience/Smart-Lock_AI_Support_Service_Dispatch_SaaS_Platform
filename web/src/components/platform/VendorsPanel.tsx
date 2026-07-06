"use client";

// CR-0114 平台 console — 廠商帳號審核 panel（「發案方審核」頁的分頁之一）。
// vendors = 發案方登入帳號（role=vendor），品牌/經銷/鎖店註冊後 pending_approval,
// 核准即啟用可登入發案。審核職權自品牌後台移到平台方統一管。
// 內部工具 → 文案直接繁中，不入 i18n。

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { friendlyError } from "@/lib/apiError";

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

const VTYPE: Record<string, string> = {
  brand: "品牌商",
  locksmith: "鎖店",
  distributor: "經銷商",
};

const STATUS_LABEL: Record<VendorStatus, string> = {
  pending_approval: "待審核",
  active: "已啟用",
  suspended: "已停權",
  rejected: "已拒絕",
};

const STATUS_CLS: Record<VendorStatus, string> = {
  pending_approval: "bg-amber-50 text-amber-700 border-amber-200",
  active: "bg-green-50 text-green-700 border-green-200",
  suspended: "bg-red-50 text-red-700 border-red-200",
  rejected: "bg-gray-100 text-gray-600 border-gray-200",
};

const FILTERS: { value: string; label: string }[] = [
  { value: "pending_approval", label: "待審核" },
  { value: "active", label: "已啟用" },
  { value: "rejected", label: "已拒絕" },
  { value: "", label: "全部" },
];

export default function VendorsPanel() {
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
    let body: Record<string, string> = {};
    if (action === "reject") {
      const reason = window.prompt(`拒絕「${vendor.company_name || vendor.name}」的原因（記入審核）：`, "");
      if (reason === null) return;
      body = { reason: reason.trim() };
    }
    setBusy(vendor.id);
    try {
      await api.post(`/api/v1/platform/vendors/${vendor.id}:${action}`, body);
      await load();
    } catch (e) {
      window.alert(friendlyError(e));
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <p className="text-sm text-[var(--text-secondary)]">
        發案方（品牌／經銷／鎖店）自助註冊的「登入帳號」。核准後即可登入平台發案（相對於申請意向，此為已建帳號的啟用審核）。
      </p>

      <div className="flex gap-2">
        {FILTERS.map((f) => (
          <button
            key={f.value || "all"}
            type="button"
            onClick={() => setFilter(f.value)}
            className={`rounded-lg border px-3 py-1.5 text-sm transition ${
              filter === f.value
                ? "border-[var(--primary)] bg-[var(--primary)] text-white"
                : "border-[var(--border)] text-[var(--text-secondary)] hover:bg-[var(--bg-hover,rgba(0,0,0,0.04))]"
            }`}
          >
            {f.label}
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
      ) : items.length === 0 ? (
        <p className="rounded-xl border border-[var(--border)] bg-[var(--bg-surface)] px-4 py-10 text-center text-sm text-[var(--text-secondary)]">
          目前沒有符合條件的廠商
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
                      {VTYPE[v.vendor_type] ?? v.vendor_type}
                    </span>
                    <span className={`rounded-md border px-2 py-0.5 text-xs ${STATUS_CLS[v.status]}`}>
                      {STATUS_LABEL[v.status]}
                    </span>
                  </div>
                  <div className="mt-2 grid gap-x-6 gap-y-1 text-sm text-[var(--text-secondary)] sm:grid-cols-2">
                    <span>聯絡人：{v.name}</span>
                    <span>電話：{v.phone || "—"}</span>
                    <span>Email：{v.email || "—"}</span>
                    {v.address && <span className="sm:col-span-2">地址：{v.address}</span>}
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
                      核准
                    </button>
                    <button
                      type="button"
                      disabled={busy === v.id}
                      onClick={() => act(v, "reject")}
                      className="rounded-lg border border-[var(--border)] px-3 py-1.5 text-sm text-[var(--text-secondary)] transition hover:bg-[var(--bg-hover,rgba(0,0,0,0.04))] disabled:opacity-50"
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
    </div>
  );
}
