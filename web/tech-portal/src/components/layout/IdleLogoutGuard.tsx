"use client";

import { useEffect, useRef } from "react";
import { auth, getCurrentSession, logout, logoutPlatformAdmin } from "@/lib/api";

/**
 * IdleLogoutGuard — 閒置逾時自動登出（業主裁決 2026-07-13：機制＝閒置逾時、時長＝60 分鐘）。
 *
 * 為何需要：目前 access token 60 分、refresh token 30 天且每次刷新滾動換新，
 * 401 由 api 層靜默 refresh → 只要 30 天內操作過就無限續命，等於永不自動登出。
 * 對經手客戶 PII 的營運後台過寬，故加「無操作逾時即登出」的前端安全控制。
 *
 * 設計要點：
 *  - **走既有 logout()**（brand/tech）/ logoutPlatformAdmin()（platform）→ 伺服器端撤銷
 *    refresh token（jti/revoked），非只清前端；否則 refresh token 仍有效 30 天＝沒真的登出。
 *  - **跨分頁共享活動時間戳**（localStorage，非機密）：任一分頁有操作即刷新共享時間戳，
 *    其他分頁讀同一值 → 一個分頁在用、閒置分頁不會把整個 session 登出。
 *  - **背景分頁補正**：背景 setInterval 會被瀏覽器節流，改以「時間戳 vs now」判定，
 *    並在 visibilitychange→visible / focus 立即檢查 → 背景放置逾時、切回即登出。
 *  - 掛在 AuthGuard 認證 subtree 內 → 只在已登入頁面作用，登入/公開頁不掛。
 */

// 單一旋鈕：閒置上限。可用 NEXT_PUBLIC_IDLE_LOGOUT_MINUTES 覆寫（build 期注入），預設 60 分。
const IDLE_LIMIT_MS =
  (Number(process.env.NEXT_PUBLIC_IDLE_LOGOUT_MINUTES) || 60) * 60 * 1000;
const ACTIVITY_KEY = "smartlock.last_activity"; // 跨分頁共享最後活動時間戳（非機密，僅 UX）
const CHECK_INTERVAL_MS = 30 * 1000; // 每 30s 檢查一次
const WRITE_THROTTLE_MS = 5 * 1000; // 活動時間戳最多每 5s 寫一次（避免高頻寫 localStorage）
const LOGOUT_MAX_WAIT_MS = 3 * 1000; // 伺服器登出最多等 3s，逾時仍導頁（避免卡在死頁）

function loginPathFor(pathname: string): string {
  if (pathname.startsWith("/platform")) return "/platform/login";
  if (/^\/(home|pool|my-orders|account|tech-login)(\/|$)/.test(pathname)) return "/tech-login";
  return "/login";
}

export default function IdleLogoutGuard() {
  const lastWriteRef = useRef(0);
  const loggingOutRef = useRef(false);

  useEffect(() => {
    const write = (t: number) => {
      lastWriteRef.current = t;
      try {
        localStorage.setItem(ACTIVITY_KEY, String(t));
      } catch {
        /* localStorage 不可用（隱私模式等）→ 退化為單分頁 setInterval 判定 */
      }
    };
    // 掛載即記一次活動：剛登入 / 剛導航皆屬活動，避免被上一輪殘留的舊時間戳誤判閒置。
    write(Date.now());

    const markActivity = () => {
      const t = Date.now();
      if (t - lastWriteRef.current < WRITE_THROTTLE_MS) return; // 節流
      write(t);
    };

    const readLast = (): number => {
      try {
        const v = localStorage.getItem(ACTIVITY_KEY);
        const n = v ? Number(v) : lastWriteRef.current;
        return Number.isFinite(n) && n > 0 ? n : lastWriteRef.current;
      } catch {
        return lastWriteRef.current;
      }
    };

    const doLogout = () => {
      if (loggingOutRef.current || !auth.getAccessToken()) return;
      loggingOutRef.current = true;
      const target = loginPathFor(window.location.pathname);
      const finish = () => {
        if (window.location.pathname !== target) {
          window.location.replace(`${target}?reason=idle`);
        } else {
          window.location.reload();
        }
      };
      // 走既有 logout（撤銷後端 refresh token）；platform_admin 走平台端點。
      const revoke =
        getCurrentSession()?.role === "platform_admin" ? logoutPlatformAdmin() : logout();
      const timeout = new Promise<void>((resolve) =>
        window.setTimeout(resolve, LOGOUT_MAX_WAIT_MS),
      );
      void Promise.race([revoke, timeout]).finally(finish);
    };

    const check = () => {
      if (!auth.getAccessToken()) return; // 別處已登出 → 不重複觸發
      if (Date.now() - readLast() >= IDLE_LIMIT_MS) doLogout();
    };

    // 有意義的互動才算活動（不含純 mousemove 游標飄移）。passive：不影響捲動效能。
    const activityEvents: (keyof WindowEventMap)[] = [
      "pointerdown",
      "keydown",
      "scroll",
      "wheel",
      "touchstart",
    ];
    activityEvents.forEach((ev) =>
      window.addEventListener(ev, markActivity, { passive: true }),
    );
    const onVisible = () => {
      if (document.visibilityState === "visible") check();
    };
    document.addEventListener("visibilitychange", onVisible);
    window.addEventListener("focus", check);
    const timer = window.setInterval(check, CHECK_INTERVAL_MS);

    return () => {
      activityEvents.forEach((ev) => window.removeEventListener(ev, markActivity));
      document.removeEventListener("visibilitychange", onVisible);
      window.removeEventListener("focus", check);
      window.clearInterval(timer);
    };
  }, []);

  return null;
}
