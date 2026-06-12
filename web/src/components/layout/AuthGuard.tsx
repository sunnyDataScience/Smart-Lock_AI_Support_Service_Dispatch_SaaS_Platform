"use client";

import { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { auth, getCurrentSession } from "@/lib/api";
import { canAccessRoute } from "@/lib/rolePolicy";
import { SidebarProvider } from "./SidebarContext";
import RbacChangedBanner from "@/components/realtime/RbacChangedBanner";

// 完整公開頁清單（AuthGuard 掛在 root layout 包整個 app，漏列就會被踢去 /login）：
//  - /login          admin/客服登入
//  - /tech-login     技師登入（漏列 → 技師永遠到不了自己的登入頁）
// 動態 token 公開頁用 prefix 比對（pathname 會帶 token segment）：
//  - /track/{token}         客戶查工單進度（public endpoint,token 簽章驗證）
//  - /scope-change/{token}  客戶確認加價/變更（public endpoint）
const PUBLIC_PATHS = new Set(["/login", "/tech-login"]);
const PUBLIC_PREFIXES = ["/track/", "/scope-change/"];

export default function AuthGuard({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const isPublic =
    PUBLIC_PATHS.has(pathname) ||
    PUBLIC_PREFIXES.some((p) => pathname.startsWith(p));
  const [checked, setChecked] = useState(false);

  useEffect(() => {
    const token = auth.getAccessToken();

    if (!token && !isPublic) {
      router.replace("/login");
      return;
    }
    if (token && isPublic) {
      router.replace("/dashboard");
      return;
    }
    // CR-0021：認證後的 role-based route gate。無權限 → 導 /dashboard（Q4）。
    // /dashboard 對所有後台角色開放,不會無限重導。
    if (token && !isPublic) {
      const role = getCurrentSession()?.role ?? null;
      if (!canAccessRoute(pathname, role)) {
        router.replace("/dashboard");
        return;
      }
    }
    setChecked(true);
  }, [isPublic, pathname, router]);

  useEffect(() => {
    const onStorage = (e: StorageEvent) => {
      const pathIsPublic =
        PUBLIC_PATHS.has(pathname) ||
        PUBLIC_PREFIXES.some((p) => pathname.startsWith(p));
      if (
        e.key === "smartlock.access_token" &&
        !e.newValue &&
        !pathIsPublic
      ) {
        router.replace("/login");
      }
    };
    window.addEventListener("storage", onStorage);
    return () => window.removeEventListener("storage", onStorage);
  }, [pathname, router]);

  if (isPublic) return <>{children}</>;
  if (!checked) return null;
  // SidebarProvider 掛在通過認證的 subtree 內，公開頁（如 login）
  // 不需要也不會錯掛
  // RbacChangedBanner 也只在認證後 subtree 渲染（fixed 定位，無 layout 影響；
  // 訂閱 /realtime/rbac 接權限變更事件，顯示 reload 提示）
  return (
    <SidebarProvider>
      <RbacChangedBanner />
      {children}
    </SidebarProvider>
  );
}
