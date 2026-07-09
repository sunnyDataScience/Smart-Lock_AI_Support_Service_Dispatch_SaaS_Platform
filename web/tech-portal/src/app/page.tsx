"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

// 師傅站根路徑唯一入口 = /tech-login（原單 codebase 時代由 page.tsx 內
// APP_MODE==="tech" 分支導向，拆分後以薄頁保留同行為）。
export default function TechRootRedirect() {
  const router = useRouter();
  useEffect(() => {
    router.replace("/tech-login");
  }, [router]);
  return null;
}
