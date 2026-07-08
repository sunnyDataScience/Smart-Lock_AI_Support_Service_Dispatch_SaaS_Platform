"use client";

import { ArrowLeft } from "lucide-react";
import { useRouter } from "next/navigation";
import { useTranslations } from "@shared/components/i18n/LocaleProvider";

// 角色入口頁（login / tech-login / tech-register / vendor-login）共用的「返回上一頁」。
// 2026-07-05：由固定回 `/`（返回首頁）改為 router.back()（返回上一頁）——
//   多為「landing → 選身分頁 → 註冊頁」的動線，回上一頁比回首頁直覺；
//   無歷史（直接開頁）時退回 `/` 以免卡住。
// tone="onDark" 供深色/漸層背景（如 tech-login 藍頂）。
export default function BackToHome({
  className = "",
  tone = "default",
}: {
  className?: string;
  tone?: "default" | "onDark";
}) {
  const t = useTranslations("landing");
  const router = useRouter();
  const color =
    tone === "onDark"
      ? "text-white/85 hover:text-white"
      : "text-[var(--text-secondary)] hover:text-[var(--text-primary)]";

  function goBack() {
    if (typeof window !== "undefined" && window.history.length > 1) {
      router.back();
    } else {
      router.push("/");
    }
  }

  return (
    <button
      type="button"
      onClick={goBack}
      className={`inline-flex items-center gap-1 text-[13px] font-medium transition ${color} ${className}`}
    >
      <ArrowLeft className="h-4 w-4" />
      {t("backToHome")}
    </button>
  );
}
