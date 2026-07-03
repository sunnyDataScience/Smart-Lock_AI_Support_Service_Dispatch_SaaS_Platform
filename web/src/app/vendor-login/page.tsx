"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

// 20260702 會議決議 2:入口濃縮為兩條 —— 廠商登入已併入「品牌 / 經銷 / 鎖店」
// 入口(/login,登入表單同時涵蓋後台角色與廠商帳號)。本頁保留 redirect,
// 不破壞既有書籤/連結。
export default function VendorLoginRedirect() {
  const router = useRouter();
  useEffect(() => {
    router.replace("/login");
  }, [router]);
  return null;
}
