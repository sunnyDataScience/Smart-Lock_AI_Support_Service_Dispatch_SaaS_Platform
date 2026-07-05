"use client";

import { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { auth, getCurrentSession } from "@/lib/api";
import { crossModeRedirect } from "@/lib/appMode";
import { canAccessRoute, fallbackRouteForRole } from "@/lib/rolePolicy";
import { SidebarProvider } from "./SidebarContext";
import RbacChangedBanner from "@/components/realtime/RbacChangedBanner";

// 完整公開頁清單（AuthGuard 掛在 root layout 包整個 app，漏列就會被踢去 /login）：
//  - /                 角色導向 landing 主頁（未登入也要看得到，否則一進站就被踢 admin 登入）
//  - /login            admin/客服登入
//  - /tech-login       技師登入（漏列 → 技師永遠到不了自己的登入頁）
//  - /vendor-login     廠商登入（CR-0029；漏列 → 廠商到不了登入頁）
//  - /register         師傅/廠商雙路註冊（CR-0029；漏列 → 新註冊者本就未登入，會被踢回 /login，註冊完全不可達）
//  - /forgot-password  自助忘記密碼申請（CR-0025；漏列 → 忘記密碼者本就未登入，功能不可達）
//  - /reset-password   email 重設連結 ?token=...（CR-0025；漏列 → 信件連結點開被踢回 /login）
// 動態 token 公開頁用 prefix 比對（pathname 會帶 token segment）：
//  - /track/{token}         客戶查工單進度（public endpoint,token 簽章驗證）
//  - /scope-change/{token}  客戶確認加價/變更（public endpoint）
//  - /quotes/{token}        客戶查看/確認報價（public endpoint,purpose=quote_view,CR-0032 Phase C）
//  - /consent/{token}       客戶簽署三段施工免責同意（public endpoint,CR-0033）
const PUBLIC_PATHS = new Set([
  "/",
  "/login",
  "/tech-login",
  "/vendor-login",
  "/register",
  "/forgot-password",
  "/reset-password",
  "/platform/login", // CR-0114 平台 console 登入（漏列 → 平台管理員到不了登入頁）
]);
const PUBLIC_PREFIXES = ["/track/", "/scope-change/", "/quotes/", "/consent/"];

export default function AuthGuard({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const isPublic =
    PUBLIC_PATHS.has(pathname) ||
    PUBLIC_PREFIXES.some((p) => pathname.startsWith(p));
  const [checked, setChecked] = useState(false);

  useEffect(() => {
    // CR-0112 雙 stack 拆分:本 build(dispatch/tech)不服務的路由,導向對方
    // portal(絕對 URL 用 window.location,站內用 router)。all 模式恆為 null。
    const crossTarget = crossModeRedirect(pathname);
    if (crossTarget) {
      if (crossTarget.startsWith("http")) {
        window.location.assign(crossTarget);
      } else {
        router.replace(crossTarget);
      }
      return;
    }

    const token = auth.getAccessToken();

    if (!token && !isPublic) {
      // CR-0114:/platform 頁群未登入 → console 自己的登入頁（其餘照舊 /login）
      router.replace(pathname.startsWith("/platform") ? "/platform/login" : "/login");
      return;
    }
    if (token && isPublic) {
      // 已登入者進公開頁 → 依角色導回各自 portal（technician→/home、vendor→/vendor）
      const home = fallbackRouteForRole(getCurrentSession()?.role ?? null);
      // 防呆(2026-07-05):落點若不屬本 stack(crossModeRedirect 會把它導去別的
      // origin),代表此 token 是別站台殘留 —— 各 port 為獨立 origin,token 各自獨立,
      // 不可據此把人一路彈到別站台登入頁(師傅站殘留品牌 token → 原本 /dashboard →
      // 被 crossModeRedirect 導去 PEER 3000 → 3000 無 token → 3000/login)。
      // 清掉本 origin 殘留 token,留在當前公開頁。
      // all 模式 crossModeRedirect 恆 null → 此分支永不觸發,單庫部署行為零變化。
      if (crossModeRedirect(home)) {
        auth.clear();
        return;
      }
      router.replace(home);
      return;
    }
    // CR-0021：認證後的 role-based route gate。無權限 → 導該角色安全落點。
    // 落點必為該角色可存取路由（technician→/home、vendor→/vendor、後台→/dashboard），
    // 避免導 /dashboard 對 technician/vendor 再被拒 → checked 永不 true → 白畫面死鎖。
    if (token && !isPublic) {
      const role = getCurrentSession()?.role ?? null;
      if (!canAccessRoute(pathname, role)) {
        router.replace(fallbackRouteForRole(role));
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
        router.replace(pathname.startsWith("/platform") ? "/platform/login" : "/login");
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
