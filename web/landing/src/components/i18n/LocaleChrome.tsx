"use client";

// UAT W6-6:英文模式下分頁標題仍「SmartLock 智慧鎖服務」、skip link 仍中文。
// metadata.title 是 build-time 靜態值(zh 預設),而 locale 存 localStorage 屬
// client 狀態 —— 只能在 client 端依語系同步 document.title;skip link 同理改為
// client 渲染取 t()。放在 LocaleProvider 內第一個子節點,維持 skip link 是
// 頁面第一個可 tab 元素(WCAG 2.4.1 Bypass Blocks)。

import { useEffect } from "react";
import { useLocale } from "./LocaleProvider";

export default function LocaleChrome() {
  const { locale, t } = useLocale();

  useEffect(() => {
    document.title = t("common.docTitle");
  }, [locale, t]);

  return (
    <a href="#main-content" className="skip-link">
      {t("common.skipToMain")}
    </a>
  );
}
