import type { MetadataRoute } from "next";

// CR-#18 first step:師傅站 PWA(可安裝到主畫面、像 APP;RN 之前的中繼方案)。
// 業主會議 §七:「他不能 24 小時開網頁」——PWA 讓師傅把工作台裝到桌面,
// 開啟即全螢幕、無瀏覽器網址列,配合 LINE 推播(CR-0169)點連結直達。
export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "SmartLock 師傅站",
    short_name: "師傅站",
    description: "Smart Lock 師傅接單工作台——接單、回報、對帳一支手機完成",
    start_url: "/home",
    scope: "/",
    display: "standalone",
    orientation: "portrait",
    background_color: "#F8FAFC",
    theme_color: "#2563EB",
    lang: "zh-TW",
    categories: ["business", "productivity"],
    icons: [
      { src: "/icons/icon-192.png", sizes: "192x192", type: "image/png", purpose: "any" },
      { src: "/icons/icon-512.png", sizes: "512x512", type: "image/png", purpose: "any" },
      { src: "/icons/maskable-512.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
    ],
    shortcuts: [
      { name: "案件池", short_name: "接單", url: "/pool" },
      { name: "我的工單", short_name: "工單", url: "/my-orders" },
    ],
  };
}
