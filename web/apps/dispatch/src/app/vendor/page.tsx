"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  Store,
  LogOut,
  Building2,
  UserRound,
  Phone,
  Mail,
  MapPin,
  Send,
  ReceiptText,
  BarChart3,
  LifeBuoy,
  CheckCircle2,
  Clock,
  type LucideIcon,
} from "lucide-react";
import { ApiError, api, getCurrentSession, logout } from "@shared/lib/api";
import { friendlyError } from "@shared/lib/apiError";
import LocaleToggle from "@shared/components/i18n/LocaleToggle";

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

const STATUS: Record<string, { label: string; chipCls: string; hint: string }> = {
  pending_approval: {
    label: "待審核",
    chipCls: "bg-amber-400/20 text-amber-100 ring-amber-300/30",
    hint: "您的帳號正在等待平台審核，核准後即可使用廠商服務。",
  },
  active: {
    label: "已啟用",
    chipCls: "bg-emerald-400/20 text-emerald-100 ring-emerald-300/30",
    hint: "帳號已啟用，發案與對帳功能開放後將於此頁啟用。",
  },
  suspended: {
    label: "已停用",
    chipCls: "bg-red-400/20 text-red-100 ring-red-300/30",
    hint: "帳號已停用，請聯絡平台管理員。",
  },
  rejected: {
    label: "已駁回",
    chipCls: "bg-red-400/20 text-red-100 ring-red-300/30",
    hint: "您的申請未通過審核。",
  },
};

// 服務模組（發案 / 對帳 / 報表 後端尚未開放；誠實標示「規劃中」，
// 讓廠商知道入口將出現在這裡，避免「空白專區」的斷頭感）。
const MODULES: { Icon: LucideIcon; title: string; desc: string }[] = [
  {
    Icon: Send,
    title: "發案管理",
    desc: "建立維修/安裝案件，追蹤派工與施工進度。",
  },
  {
    Icon: ReceiptText,
    title: "對帳與請款",
    desc: "查看每期對帳單、費用明細與請款狀態。",
  },
  {
    Icon: BarChart3,
    title: "營運報表",
    desc: "案件量、完修率與服務品質的統計總覽。",
  },
];

export default function VendorPortalPage() {
  const router = useRouter();
  const [vendor, setVendor] = useState<Vendor | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const session = getCurrentSession();
    if (!session || session.role !== "vendor") {
      router.replace("/login");
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
            router.replace("/login");
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
    router.replace("/login");
  }

  const st = vendor
    ? STATUS[vendor.status] ?? {
        label: vendor.status,
        chipCls: "bg-white/15 text-white ring-white/20",
        hint: "",
      }
    : null;
  const pending = vendor?.status === "pending_approval";

  return (
    <div className="min-h-screen bg-[var(--bg-page)]">
      <header className="flex items-center gap-3 border-b border-[var(--border)] bg-[var(--bg-surface)] px-4 py-3.5 md:px-8">
        <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-[var(--primary)]">
          <Store className="h-5 w-5 text-white" />
        </div>
        <div className="flex flex-col leading-tight">
          <h1 className="text-[16px] font-bold text-[var(--text-primary)]">廠商專區</h1>
          <span className="text-[11px] text-[var(--text-secondary)]">SmartLock 派工平台</span>
        </div>
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

      <main className="mx-auto max-w-[880px] px-4 py-6 md:py-8">
        {error && (
          <div className="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            {error}
          </div>
        )}

        {loading ? (
          <p className="text-sm text-[var(--text-secondary)]">載入中…</p>
        ) : !vendor ? (
          <p className="text-sm text-[var(--text-disabled)]">查無廠商資料</p>
        ) : (
          <div className="flex flex-col gap-5">
            {/* hero：歡迎 + 公司 + 類型/狀態（與師傅端首頁同一深色漸層語彙） */}
            <section className="relative overflow-hidden rounded-2xl bg-[linear-gradient(135deg,#0F172A_0%,#1E3A8A_78%,#1D4ED8_100%)] p-5 text-white shadow-md md:p-6">
              <div
                aria-hidden
                className="pointer-events-none absolute -right-16 -top-24 h-64 w-64 rounded-full bg-[#3B82F6] opacity-20 blur-3xl"
              />
              <div className="relative flex flex-col gap-2">
                <span className="text-[13px] text-white/60">歡迎回來</span>
                <div className="flex flex-wrap items-center gap-2.5">
                  <h2 className="text-[22px] font-bold leading-tight">
                    {vendor.company_name || vendor.name}
                  </h2>
                  <span className="inline-flex items-center rounded-full bg-white/10 px-2.5 py-1 text-[12px] font-medium text-white/90 ring-1 ring-inset ring-white/15">
                    {VTYPE[vendor.vendor_type] ?? vendor.vendor_type}
                  </span>
                  {st && (
                    <span
                      className={`inline-flex items-center rounded-full px-2.5 py-1 text-[12px] font-medium ring-1 ring-inset ${st.chipCls}`}
                    >
                      {st.label}
                    </span>
                  )}
                </div>
                {st?.hint && <p className="text-[13px] text-white/70">{st.hint}</p>}
                {vendor.status === "rejected" && vendor.rejection_reason && (
                  <p className="text-[13px] text-red-200">
                    駁回原因：{vendor.rejection_reason}
                  </p>
                )}
              </div>
            </section>

            {/* 待審核：申請進度三步 */}
            {pending && (
              <section className="rounded-xl border border-[var(--border)] bg-[var(--bg-surface)] p-5 shadow-sm">
                <h3 className="mb-4 text-[15px] font-semibold text-[var(--text-primary)]">
                  申請進度
                </h3>
                <ol className="flex flex-col gap-0 md:flex-row md:items-start md:gap-4">
                  <ProgressStep
                    state="done"
                    title="送出申請"
                    desc="已收到您的廠商資料"
                  />
                  <ProgressStep
                    state="current"
                    title="平台審核中"
                    desc="平台將核對公司與聯絡資訊"
                  />
                  <ProgressStep
                    state="todo"
                    title="核准開通"
                    desc="核准後即可開始使用廠商服務"
                    last
                  />
                </ol>
              </section>
            )}

            {/* 帳號資料 + 服務模組 */}
            <div className="grid gap-5 md:grid-cols-2">
              <section className="rounded-xl border border-[var(--border)] bg-[var(--bg-surface)] p-5 shadow-sm">
                <h3 className="mb-4 text-[15px] font-semibold text-[var(--text-primary)]">
                  帳號資料
                </h3>
                <dl className="flex flex-col gap-3.5">
                  <InfoRow Icon={Building2} label="公司名稱" value={vendor.company_name || "—"} />
                  <InfoRow Icon={Store} label="廠商類型" value={VTYPE[vendor.vendor_type] ?? vendor.vendor_type} />
                  <InfoRow Icon={UserRound} label="聯絡人" value={vendor.name} />
                  <InfoRow Icon={Phone} label="聯絡電話" value={vendor.phone} />
                  <InfoRow Icon={Mail} label="Email" value={vendor.email} />
                  <InfoRow Icon={MapPin} label="地址" value={vendor.address || "—"} />
                </dl>
              </section>

              <section className="rounded-xl border border-[var(--border)] bg-[var(--bg-surface)] p-5 shadow-sm">
                <div className="mb-4 flex items-center justify-between">
                  <h3 className="text-[15px] font-semibold text-[var(--text-primary)]">
                    服務功能
                  </h3>
                  <span className="text-[11px] text-[var(--text-disabled)]">陸續開放中</span>
                </div>
                <ul className="flex flex-col gap-3">
                  {MODULES.map(({ Icon, title, desc }) => (
                    <li
                      key={title}
                      className="flex items-start gap-3 rounded-lg border border-dashed border-[var(--border)] bg-[var(--bg-page)] p-3"
                    >
                      <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-[var(--surface-strong)] text-[var(--text-secondary)]">
                        <Icon className="h-4.5 w-4.5" />
                      </span>
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-2">
                          <span className="text-[14px] font-semibold text-[var(--text-primary)]">
                            {title}
                          </span>
                          <span className="rounded bg-[var(--surface-strong)] px-1.5 py-[1px] text-[11px] font-medium text-[var(--text-secondary)]">
                            規劃中
                          </span>
                        </div>
                        <p className="mt-0.5 text-[12px] leading-relaxed text-[var(--text-secondary)]">
                          {desc}
                        </p>
                      </div>
                    </li>
                  ))}
                </ul>
              </section>
            </div>

            {/* 支援 */}
            <section className="flex items-center gap-3 rounded-xl border border-[var(--border)] bg-[var(--bg-surface)] px-5 py-4 shadow-sm">
              <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-[rgba(59,130,246,0.12)] text-[#3B82F6]">
                <LifeBuoy className="h-4.5 w-4.5" />
              </span>
              <p className="text-[13px] text-[var(--text-secondary)]">
                需要協助或想調整帳號資料？請聯絡平台管理員，我們會盡快處理。
              </p>
            </section>
          </div>
        )}
      </main>
    </div>
  );
}

function InfoRow({
  Icon,
  label,
  value,
}: {
  Icon: LucideIcon;
  label: string;
  value: string;
}) {
  return (
    <div className="flex items-center gap-3">
      <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-[var(--surface-strong)] text-[var(--text-secondary)]">
        <Icon className="h-4 w-4" />
      </span>
      <div className="min-w-0">
        <dt className="text-[11px] text-[var(--text-secondary)]">{label}</dt>
        <dd className="truncate text-[14px] font-medium text-[var(--text-primary)]">{value}</dd>
      </div>
    </div>
  );
}

function ProgressStep({
  state,
  title,
  desc,
  last = false,
}: {
  state: "done" | "current" | "todo";
  title: string;
  desc: string;
  last?: boolean;
}) {
  const icon =
    state === "done" ? (
      <CheckCircle2 className="h-5 w-5 text-[#10B981]" />
    ) : state === "current" ? (
      <Clock className="h-5 w-5 text-[#F59E0B]" />
    ) : (
      <span className="block h-2.5 w-2.5 rounded-full bg-[var(--border)]" />
    );

  return (
    <li className="relative flex flex-1 gap-3 md:flex-col md:gap-2">
      {/* 連接線：手機直向、桌面橫向 */}
      {!last && (
        <span
          aria-hidden
          className="absolute left-[13px] top-8 h-[calc(100%-20px)] w-px bg-[var(--border)] md:left-8 md:top-[13px] md:h-px md:w-[calc(100%-40px)]"
        />
      )}
      <span className="flex h-7 w-7 shrink-0 items-center justify-center">{icon}</span>
      <div className="pb-5 md:pb-0">
        <div
          className={`text-[13px] font-semibold ${
            state === "todo" ? "text-[var(--text-disabled)]" : "text-[var(--text-primary)]"
          }`}
        >
          {title}
        </div>
        <p className="mt-0.5 text-[12px] text-[var(--text-secondary)]">{desc}</p>
      </div>
    </li>
  );
}
