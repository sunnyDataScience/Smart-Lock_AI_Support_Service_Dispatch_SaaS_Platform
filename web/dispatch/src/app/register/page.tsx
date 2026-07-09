"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

// 20260702 會議決議 2:入口濃縮為兩條、登入與註冊同框 —— 獨立註冊頁已拆併:
//   廠商(品牌/經銷/鎖店)註冊 → /login?tab=register
//   鎖匠師傅註冊            → /tech-login?tab=register
// 本頁保留 redirect 到 landing 讓使用者選身分,不破壞既有書籤/連結。
export default function RegisterRedirect() {
  const router = useRouter();
  useEffect(() => {
    router.replace("/");
  }, [router]);
  return null;
}
