// SmartLock 師傅站 Service Worker(CR-#18 PWA 中繼方案)。
// 目標:①滿足 PWA 可安裝條件 ②app-shell 離線可開(斷網顯示離線頁而非瀏覽器錯誤)。
// 刻意保守:API 一律 network-only(工單/派單是即時資料,絕不快取舊資料);
// 只快取靜態 shell。版本號 bump 即汰換舊快取。

const CACHE = "smartlock-tech-v1";
const SHELL = ["/home", "/offline.html", "/icons/icon-192.png"];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting()),
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim()),
  );
});

self.addEventListener("fetch", (event) => {
  const { request } = event;
  if (request.method !== "GET") return;

  const url = new URL(request.url);
  // 即時資料絕不快取:API / 跨域(api:8002)一律直連網路
  const isApi = url.pathname.startsWith("/api/") || url.pathname.startsWith("/tenants/");
  if (isApi || url.origin !== self.location.origin) return;

  // 導航請求(頁面):network-first,斷網退離線頁
  if (request.mode === "navigate") {
    event.respondWith(
      fetch(request).catch(() =>
        caches.match(request).then((r) => r || caches.match("/offline.html")),
      ),
    );
    return;
  }

  // 靜態資源(_next/static、icons):cache-first(有雜湊,安全)
  if (url.pathname.startsWith("/_next/static") || url.pathname.startsWith("/icons/")) {
    event.respondWith(
      caches.match(request).then(
        (cached) =>
          cached ||
          fetch(request).then((res) => {
            const copy = res.clone();
            caches.open(CACHE).then((c) => c.put(request, copy));
            return res;
          }),
      ),
    );
  }
});
