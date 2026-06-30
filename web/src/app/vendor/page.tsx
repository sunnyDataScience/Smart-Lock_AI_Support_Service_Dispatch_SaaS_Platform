"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Store, LogOut } from "lucide-react";
import { ApiError, api, getCurrentSession, logout } from "@/lib/api";
import { friendlyError } from "@/lib/apiError";
import LocaleToggle from "@/components/i18n/LocaleToggle";

interface Vendor {
  id: string;
  vendor_type: string;
  name: string;
  company_name: string | null;
  phone: string;
  email: string;
  address: string | null;
  status: string;
  rejection_reason: string | null;
}

const VTYPE: Record<string, string> = {
  brand: "品牌商",
  locksmith: "鎖店",
  distributor: "經銷商",
};
const STATUS: Record<string, { label: string; cls: string; hint: string }> = {
  pending_approval: { label: "待審核", cls: "bg-[#FEF3C7] text-[#92400E]", hint: "您的帳號正在等待平台審核，核准後即可發案。" },
  active: { label: "已啟用", cls: "bg-[#DCFCE7] text-[#15803D]", hint: "帳號已啟用，可正常使用廠商服務。" },
  suspended: { label: "已停用", cls: "bg-[#FEE2E2] text-[#B91C1C]", hint: "帳號已停用，請聯絡平台管理員。" },
  rejected: { label: "已駁回", cls: "bg-[#FEE2E2] text-[#B91C1C]", hint: "您的申請未通過審核。" },
};

export default function VendorPortalPage() {
  const router = useRouter();
  const [vendor, setVendor] = useState<Vendor | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const session = getCurrentSession();
    if (!session || session.role !== "vendor") {
      router.replace("/vendor-login");
      return;
    }
    let cancelled = false;
    (async () => {
      try {
        const res = await api.get<{ data: Vendor }>("/vendors/me");
        if (!cancelled) setVendor(res.data ?? null);
      } catch (e) {
        if (!cancelled) {
          if (e instanceof ApiError && e.status === 401) {
            router.replace("/vendor-login");
            return;
          }
          setError(friendlyError(e));
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [router]);

  async function onLogout() {
    await logout().catch(() => undefined);
    router.replace("/vendor-login");
  }

  const st = vendor ? STATUS[vendor.status] ?? { label: vendor.status, cls: "bg-[#F1F5F9] text-[var(--text-secondary)]", hint: "" } : null;

  return (
    <div className="min-h-screen bg-[var(--bg-page)]">
      <header className="flex items-center gap-3 border-b border-[var(--border)] bg-[var(--bg-surface)] px-4 py-4 md:px-8">
        <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-[var(--primary)]">
          <Store className="h-5 w-5 text-white" />
        </div>
        <h1 className="text-lg font-bold text-[var(--text-primary)]">廠商專區</h1>
        <div className="ml-auto flex items-center gap-3">
          <LocaleToggle />
          <button
            onClick={onLogout}
            className="flex items-center gap-1.5 rounded-md border border-[var(--border)] px-3 py-1.5 text-[13px] font-medium text-[var(--text-secondary)] hover:bg-[var(--bg-page)]"
          >
            <LogOut className="h-4 w-4" /> 登出
          </button>
        </div>
      </header>

      <main className="mx-auto max-w-[720px] px-4 py-8 md:px-0">
        {error && (
          <div className="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>
        )}
        {loading ? (
          <p className="text-sm text-[var(--text-secondary)]">載入中…</p>
        ) : !vendor ? (
          <p className="text-sm text-[var(--text-disabled)]">查無廠商資料</p>
        ) : (
          <div className="flex flex-col gap-5">
            {/* 狀態卡 */}
            {st && (
              <div className="flex items-start gap-3 rounded-xl border border-[var(--border)] bg-[var(--bg-surface)] p-5">
                <div className="flex flex-col gap-1">
                  <div className="flex items-center gap-2">
                    <span className="text-[18px] font-bold text-[var(--text-primary)]">
                      {vendor.company_name || vendor.name}
                    </span>
                    <span className={`rounded px-2 py-[2px] text-[12px] font-medium ${st.cls}`}>{st.label}</span>
                  </div>
                  <span className="text-[13px] text-[var(--text-secondary)]">{st.hint}</span>
                  {vendor.status === "rejected" && vendor.rejection_reason && (
                    <span className="text-[12px] text-red-700">駁回原因：{vendor.rejection_reason}</span>
                  )}
                </div>
              </div>
            )}

            {/* 帳號資料 */}
            <div className="rounded-xl border border-[var(--border)] bg-[var(--bg-surface)] p-5">
              <h2 className="mb-3 text-[15px] font-semibold text-[var(--text-primary)]">帳號資料</h2>
              <dl className="grid grid-cols-1 gap-y-3 sm:grid-cols-2">
                <Row label="廠商類型" value={VTYPE[vendor.vendor_type] ?? vendor.vendor_type} />
                <Row label="公司名稱" value={vendor.company_name || "—"} />
                <Row label="聯絡人" value={vendor.name} />
                <Row label="聯絡電話" value={vendor.phone} />
                <Row label="Email" value={vendor.email} />
                <Row label="地址" value={vendor.address || "—"} />
              </dl>
            </div>

            <p className="text-[12px] text-[var(--text-disabled)]">
              發案 / 對帳等廠商服務功能陸續開放中。如需協助請聯絡平台管理員。
            </p>
          </div>
        )}
      </main>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col gap-[2px]">
      <dt className="text-[12px] text-[var(--text-secondary)]">{label}</dt>
      <dd className="text-[14px] font-medium text-[var(--text-primary)]">{value}</dd>
    </div>
  );
}
