"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

// 平台 console 只服務 /platform 頁群;根路徑導 console 登入
// (原 crossModeRedirect platform 模式行為)。
export default function PlatformRootRedirect() {
  const router = useRouter();
  useEffect(() => {
    router.replace("/platform/login");
  }, [router]);
  return null;
}
