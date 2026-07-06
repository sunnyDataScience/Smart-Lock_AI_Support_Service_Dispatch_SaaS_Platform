"use client";

// CR-0114 平台方 console 殼(Lock AI 內部自用,非品牌/師傅面)。
// 刻意不用品牌後台 Sidebar:console 是跨品牌視角,選單極小(儀表板/師傅申請/
// 品牌申請),頂欄式即可。內部工具 → 文案直接繁中,不入 i18n 兩 locale 對照。

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { LayoutDashboard, LogOut, ShieldCheck } from "lucide-react";
import { logoutPlatformAdmin } from "@/lib/api";

const NAV: { href: string; label: string }[] = [
  { href: "/platform", label: "儀表板" },
  { href: "/platform/brand-applications", label: "品牌申請" },
  { href: "/platform/technicians", label: "師傅管理" },
];

export default function PlatformLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const pathname = usePathname();
  const router = useRouter();

  // 登入頁與公開申請導入頁不套 console 殼(未登入 / 對外申請者面)
  if (pathname === "/platform/login" || pathname === "/platform/apply")
    return <>{children}</>;

  const onLogout = async () => {
    await logoutPlatformAdmin();
    router.replace("/platform/login");
  };

  return (
    <div className="min-h-screen bg-[var(--bg-page)]">
      <header className="sticky top-0 z-20 border-b border-[var(--border)] bg-[var(--bg-surface)]">
        <div className="mx-auto flex h-14 max-w-6xl items-center justify-between px-4">
          <div className="flex items-center gap-6">
            <div className="flex items-center gap-2">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-[var(--primary)]">
                <ShieldCheck className="h-4.5 w-4.5 text-white" aria-hidden />
              </div>
              <span className="text-sm font-bold text-[var(--text-primary)]">
                Lock AI 平台管理
              </span>
            </div>
            <nav className="flex items-center gap-1" aria-label="平台管理導覽">
              {NAV.map((item) => {
                const active =
                  pathname === item.href ||
                  pathname.startsWith(`${item.href}/`);
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    className={`rounded-lg px-3 py-1.5 text-sm transition ${
                      active
                        ? "bg-[var(--primary-subtle,rgba(59,130,246,0.12))] font-semibold text-[var(--primary)]"
                        : "text-[var(--text-secondary)] hover:bg-[var(--bg-hover,rgba(0,0,0,0.04))] hover:text-[var(--text-primary)]"
                    }`}
                  >
                    {item.href === "/platform" && (
                      <LayoutDashboard className="mr-1.5 inline h-4 w-4 align-[-2px]" aria-hidden />
                    )}
                    {item.label}
                  </Link>
                );
              })}
            </nav>
          </div>
          <button
            type="button"
            onClick={onLogout}
            className="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm text-[var(--text-secondary)] transition hover:bg-[var(--bg-hover,rgba(0,0,0,0.04))] hover:text-[var(--text-primary)]"
          >
            <LogOut className="h-4 w-4" aria-hidden />
            登出
          </button>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-4 py-8">{children}</main>
    </div>
  );
}
