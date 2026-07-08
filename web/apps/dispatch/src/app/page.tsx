"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

// 品牌後台根路徑一律進登入頁（2026-07-05 業主裁決:3000 不渲染對外 landing,
// 導流站=3002）。已登入者由 AuthGuard 依角色續導 /dashboard。
export default function DispatchRootRedirect() {
  const router = useRouter();
  useEffect(() => {
    router.replace("/login");
  }, [router]);
  return null;
}
