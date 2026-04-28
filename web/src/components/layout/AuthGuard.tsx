"use client";

import { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { auth } from "@/lib/api";

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
  return <>{children}</>;
}
