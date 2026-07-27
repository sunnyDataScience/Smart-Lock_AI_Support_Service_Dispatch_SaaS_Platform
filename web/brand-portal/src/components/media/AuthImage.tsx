"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";
import { ImageOff } from "lucide-react";
import { auth } from "@/lib/api";
import { apiBaseUrl } from "@/lib/runtimeConfig";

/**
 * AuthImage — 需認證媒體的通用圖片元件（CR-0178 UAT-0720 輪次 C 抽出）。
 *
 * 背景：`/api/v1/media/{id}` 需 Bearer token + X-Tenant-ID，<img src> 直連 401。
 * 本元件統一「帶 token fetch → blob URL」模式；絕對 URL（客服手附外部連結、
 * 日後 GCS 簽名 URL）直接使用。原三處同款複本（MediaGallery.MediaThumb、
 * ChatTimeline.AuthChatImage、各頁裸連結）收斂於此。
 *
 * loading/error 佔位可由呼叫端覆寫（loadingNode/errorNode）——預設為淺色卡片
 * 配色；深色泡泡背景（ChatTimeline）需傳入自己的佔位。
 */
export function AuthImage({
  url,
  alt,
  className,
  onClick,
  loadingNode,
  errorNode,
}: {
  url: string;
  alt: string;
  className?: string;
  onClick?: () => void;
  loadingNode?: ReactNode;
  errorNode?: ReactNode;
}) {
  const [src, setSrc] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);
  const objectUrlRef = useRef<string | null>(null);

  useEffect(() => {
    setFailed(false);
    if (/^https?:\/\//.test(url)) {
      setSrc(url);
      return;
    }
    let cancelled = false;
    const ac = new AbortController();
    // || 而非 ??：docker build 會把未設的 env 烘成空字串，?? 接不住（lib/api.ts 同款）
    const baseUrl = apiBaseUrl();
    const token = auth.getAccessToken();

    (async () => {
      try {
        const res = await fetch(`${baseUrl}${url}`, {
          headers: {
            Authorization: token ? `Bearer ${token}` : "",
            "X-Tenant-ID": auth.getTenantId(),
          },
          signal: ac.signal,
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const blob = await res.blob();
        const objUrl = URL.createObjectURL(blob);
        objectUrlRef.current = objUrl;
        if (!cancelled) setSrc(objUrl);
      } catch {
        if (!cancelled) setFailed(true);
      }
    })();

    return () => {
      cancelled = true;
      ac.abort();
      if (objectUrlRef.current) {
        URL.revokeObjectURL(objectUrlRef.current);
        objectUrlRef.current = null;
      }
    };
  }, [url]);

  if (failed) {
    return (
      <>
        {errorNode ?? (
          <div className="flex items-center gap-1 rounded-md border border-[var(--border)] bg-[var(--bg-page)] px-3 py-2 text-[12px] text-[var(--text-disabled)]">
            <ImageOff className="h-4 w-4" />
            照片載入失敗
          </div>
        )}
      </>
    );
  }
  if (!src) {
    return (
      <>
        {loadingNode ?? (
          <div className="flex h-[96px] w-[96px] items-center justify-center rounded-md border border-[var(--border)] bg-[var(--bg-page)] text-[12px] text-[var(--text-disabled)]">
            載入中…
          </div>
        )}
      </>
    );
  }
  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={src}
      alt={alt}
      decoding="async"
      className={className ?? "max-h-[240px] rounded-md"}
      onClick={onClick}
    />
  );
}

/**
 * AuthImageLightbox — 最小放大檢視（沿 MediaGallery lightbox 先例：
 * fixed 遮罩、點背景關閉、內部重掛 AuthImage 重 fetch 一次）。
 * blob URL 不可開新分頁（unmount/revoke 即失效，且新分頁補不了 auth header）。
 */
export function AuthImageLightbox({
  url,
  alt,
  onClose,
}: {
  url: string;
  alt: string;
  onClose: () => void;
}) {
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 p-4"
      onClick={onClose}
    >
      <button
        onClick={onClose}
        className="absolute right-4 top-4 rounded-full bg-white/10 px-3 py-1 text-[14px] text-white hover:bg-white/20"
        aria-label="關閉預覽"
      >
        ✕
      </button>
      <div onClick={(e) => e.stopPropagation()}>
        <AuthImage
          url={url}
          alt={alt}
          className="max-h-[90vh] max-w-[90vw] rounded-lg object-contain"
        />
      </div>
    </div>
  );
}
