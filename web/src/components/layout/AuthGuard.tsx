"use client";

import { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { auth } from "@/lib/api";

const PUBLIC_PATHS = new Set(["/login", "/tech-login"]);

// 技師端路由：未登入時導向 /tech-login，已登入時 /tech-login → /pool
const TECH_ROUTE_PREFIXES = ["/pool", "/my-orders", "/account", "/tech-login"];

function isTechRoute(pathname: string): boolean {
  return TECH_ROUTE_PREFIXES.some(
    (p) => pathname === p || pathname.startsWith(p + "/"),
  );
}

export default function AuthGuard({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const isPublic = PUBLIC_PATHS.has(pathname);
  const [checked, setChecked] = useState(false);

  useEffect(() => {
    const token = auth.getAccessToken();
    const tech = isTechRoute(pathname);

    if (!token && !isPublic) {
      router.replace(tech ? "/tech-login" : "/login");
      return;
    }
    if (token && isPublic) {
      router.replace(pathname === "/tech-login" ? "/pool" : "/dashboard");
      return;
    }
    setChecked(true);
  }, [isPublic, pathname, router]);

  useEffect(() => {
    const onStorage = (e: StorageEvent) => {
      if (
        e.key === "smartlock.access_token" &&
        !e.newValue &&
        !PUBLIC_PATHS.has(pathname)
      ) {
        router.replace(isTechRoute(pathname) ? "/tech-login" : "/login");
      }
    };
    window.addEventListener("storage", onStorage);
    return () => window.removeEventListener("storage", onStorage);
  }, [pathname, router]);

  if (isPublic) return <>{children}</>;
  if (!checked) return null;
  return <>{children}</>;
}
