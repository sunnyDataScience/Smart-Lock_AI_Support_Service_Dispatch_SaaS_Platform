"use client";

import { ArrowLeft } from "lucide-react";
import Link from "next/link";
import { useTranslations } from "@/components/i18n/LocaleProvider";

// 角色入口頁（login / tech-login / vendor-login / register）共用的「返回首頁」連結。
// 從 landing 選錯身分可一鍵回 `/` 重選。tone="onDark" 供深色/漸層背景（如 tech-login 藍頂）。
export default function BackToHome({
  className = "",
  tone = "default",
}: {
  className?: string;
  tone?: "default" | "onDark";
}) {
  const t = useTranslations("landing");
  const color =
    tone === "onDark"
      ? "text-white/85 hover:text-white"
      : "text-[var(--text-secondary)] hover:text-[var(--text-primary)]";
  return (
    <Link
      href="/"
      className={`inline-flex items-center gap-1 text-[13px] font-medium transition ${color} ${className}`}
    >
      <ArrowLeft className="h-4 w-4" />
      {t("backToHome")}
    </Link>
  );
}
