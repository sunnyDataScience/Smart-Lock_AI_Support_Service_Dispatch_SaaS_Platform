"use client";

// CR-#18 PWA:註冊 service worker + 「加入主畫面」安裝提示(Android/桌面 Chrome)。
// iOS Safari 無 beforeinstallprompt → 顯示手動加入說明(分享→加入主畫面)。

import { useEffect, useState } from "react";

interface BeforeInstallPromptEvent extends Event {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: "accepted" | "dismissed" }>;
}

const DISMISS_KEY = "smartlock-pwa-install-dismissed";

export default function PwaProvider() {
  const [deferred, setDeferred] = useState<BeforeInstallPromptEvent | null>(null);
  const [show, setShow] = useState(false);
  const [iosHint, setIosHint] = useState(false);

  useEffect(() => {
    // 1. 註冊 service worker(prod build 才有 sw.js;dev 也可註冊,失敗靜默)
    if ("serviceWorker" in navigator) {
      navigator.serviceWorker.register("/sw.js").catch(() => {
        /* 註冊失敗不影響網頁使用 */
      });
    }

    // 已安裝(standalone)或先前關閉過 → 不打擾
    const standalone =
      window.matchMedia("(display-mode: standalone)").matches ||
      // iOS
      (window.navigator as unknown as { standalone?: boolean }).standalone === true;
    const dismissed = localStorage.getItem(DISMISS_KEY) === "1";
    if (standalone || dismissed) return;

    // UAT P2-1③:安裝橫幅只對行動裝置顯示(<768px,與 TechBottomNav 斷點一致)。
    // 桌面 Chrome 想安裝仍可用網址列的安裝 icon,不需橫幅打擾。
    if (window.innerWidth >= 768) return;

    // 2. Android:攔截 beforeinstallprompt,改由我們的按鈕觸發
    const onPrompt = (e: Event) => {
      e.preventDefault();
      // UAT P2-1①:Chrome 可能在同一 SPA session 換頁時重新觸發本事件,
      // mount 時的 dismissed 檢查擋不住 → 觸發當下再驗一次,確保「暫不」後本裝置不再出現。
      if (localStorage.getItem(DISMISS_KEY) === "1") return;
      setDeferred(e as BeforeInstallPromptEvent);
      setShow(true);
    };
    window.addEventListener("beforeinstallprompt", onPrompt);

    // 3. iOS Safari(無 beforeinstallprompt)→ 顯示手動加入提示
    const ua = window.navigator.userAgent;
    const isIos = /iphone|ipad|ipod/i.test(ua);
    const isSafari = /safari/i.test(ua) && !/crios|fxios|edgios/i.test(ua);
    if (isIos && isSafari) {
      setIosHint(true);
      setShow(true);
    }

    return () => window.removeEventListener("beforeinstallprompt", onPrompt);
  }, []);

  function dismiss() {
    setShow(false);
    localStorage.setItem(DISMISS_KEY, "1");
  }

  async function install() {
    if (!deferred) return;
    await deferred.prompt();
    await deferred.userChoice;
    setDeferred(null);
    setShow(false);
    localStorage.setItem(DISMISS_KEY, "1");
  }

  if (!show) return null;

  return (
    // UAT P2-1②:停靠在底部導航(h-14 + safe-area)上方,不再蓋住導航與操作鈕;
    // z-40 低於 Modal/Drawer(z-50),避免壓住彈窗。md:hidden 保險(行動裝置限定)。
    <div className="fixed inset-x-3 bottom-[calc(4rem+env(safe-area-inset-bottom,0px))] z-40 mx-auto max-w-sm rounded-2xl border border-[var(--border)] bg-[var(--bg-surface)] p-4 shadow-lg md:hidden">
      <div className="flex items-start gap-3">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src="/icons/icon-192.png" alt="" className="h-11 w-11 shrink-0 rounded-xl" />
        <div className="min-w-0 flex-1">
          <p className="text-[14px] font-semibold text-[var(--text-primary)]">把師傅站裝到手機主畫面</p>
          {iosHint ? (
            <p className="mt-0.5 text-[12px] leading-relaxed text-[var(--text-secondary)]">
              點下方分享鍵 <span aria-hidden>􀈂</span> →「加入主畫面」,開啟即全螢幕、接單更快。
            </p>
          ) : (
            <p className="mt-0.5 text-[12px] leading-relaxed text-[var(--text-secondary)]">
              安裝後像 APP 一樣一鍵開啟,不用每次找網址。
            </p>
          )}
          <div className="mt-2.5 flex items-center gap-2">
            {!iosHint && (
              <button
                type="button"
                onClick={install}
                className="rounded-xl bg-[var(--primary)] px-4 py-1.5 text-[13px] font-semibold text-white"
              >
                加入主畫面
              </button>
            )}
            <button
              type="button"
              onClick={dismiss}
              className="rounded-xl px-3 py-1.5 text-[13px] text-[var(--text-secondary)]"
            >
              {iosHint ? "知道了" : "暫不"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
