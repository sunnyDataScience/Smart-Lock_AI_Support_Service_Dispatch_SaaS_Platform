"use client";

import { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { auth } from "@/lib/api";
import { SidebarProvider } from "./SidebarContext";
import RbacChangedBanner from "@/components/realtime/RbacChangedBanner";

const PUBLIC_PATHS = new Set(["/login"]);

export default function AuthGuard({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const isPublic = PUBLIC_PATHS.has(pathname);
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
    setChecked(true);
  }, [isPublic, router]);

  useEffect(() => {
    const onStorage = (e: StorageEvent) => {
      if (
        e.key === "smartlock.access_token" &&
        !e.newValue &&
        !PUBLIC_PATHS.has(pathname)
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
