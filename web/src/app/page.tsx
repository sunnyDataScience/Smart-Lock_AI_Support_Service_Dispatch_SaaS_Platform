"use client";

import {
  ArrowRight,
  Bot,
  Building2,
  CheckCircle2,
  ClipboardList,
  Lock,
  MapPin,
  MessageSquareText,
  Receipt,
  Route,
  Smartphone,
  Wrench,
  X,
} from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { auth } from "@/lib/api";
import { APP_MODE, PEER_PORTAL_URL } from "@/lib/appMode";
import VendorRegisterForm from "@/components/auth/VendorRegisterForm";
import LocaleToggle from "@/components/i18n/LocaleToggle";
import ThemeToggle from "@/components/theme/ThemeToggle";
import { useTranslations } from "@/components/i18n/LocaleProvider";

// 一頁式平台介紹 landing(2026-07-05 業主需求,對齊 20260702 會議 §三
// 「landing 掛申請窗口、半自動化導入」):
//   - 師傅 CTA → 跳師傅註冊(/tech-login?tab=register;dispatch build 有配
//     PEER_PORTAL_URL 時指對方 portal)
//   - 品牌 CTA → 彈出品牌基本資料表單(共用 VendorRegisterForm →
//     POST /vendors/register,送出即進後台「廠商審核」待核准流程)
//   - 既有使用者由右上「登入」進 /login(登入註冊同框頁保留)
// `/` 在 AuthGuard PUBLIC_PATHS(未登入可看);tech build 的 `/` 直接導
// /tech-login(師傅 stack 不渲染行銷頁)。

// CR-0112 雙 stack:dispatch build 的師傅連結指向對方 portal(有配 PEER 時)。
const TECH_PORTAL_BASE =
  APP_MODE === "dispatch" && PEER_PORTAL_URL ? PEER_PORTAL_URL : "";
const TECH_REGISTER_HREF = `${TECH_PORTAL_BASE}/tech-login?tab=register`;

export default function Home() {
  const t = useTranslations("landing");
  const tR = useTranslations("register");
  const router = useRouter();
  const [authed, setAuthed] = useState(false);
  const [applyOpen, setApplyOpen] = useState(false);

  // tech build:師傅 stack 只有一條入口,landing 直接進 /tech-login。
  useEffect(() => {
    if (APP_MODE === "tech") router.replace("/tech-login");
  }, [router]);

  // token 只能在 client 讀(localStorage);已登入者頂部顯示「進入後台」捷徑。
  useEffect(() => {
    setAuthed(Boolean(auth.getAccessToken()));
  }, []);

  // modal 開啟時鎖背景捲動
  useEffect(() => {
    document.body.style.overflow = applyOpen ? "hidden" : "";
    return () => {
      document.body.style.overflow = "";
    };
  }, [applyOpen]);

  if (APP_MODE === "tech") return null;

  const features = [
    { icon: Bot, titleKey: "f1Title", descKey: "f1Desc" },
    { icon: Route, titleKey: "f2Title", descKey: "f2Desc" },
    { icon: Smartphone, titleKey: "f3Title", descKey: "f3Desc" },
    { icon: Receipt, titleKey: "f4Title", descKey: "f4Desc" },
  ];

  const steps = [
    { icon: MessageSquareText, titleKey: "s1Title", descKey: "s1Desc" },
    { icon: ClipboardList, titleKey: "s2Title", descKey: "s2Desc" },
    { icon: CheckCircle2, titleKey: "s3Title", descKey: "s3Desc" },
  ];

  const techPoints = ["techP1", "techP2", "techP3"];

  return (
    <div className="min-h-screen bg-[var(--bg-page)] text-[var(--text-primary)]">
      {/* ── 頂部導覽 ── */}
      <header className="sticky top-0 z-40 border-b border-[var(--border)] bg-[var(--bg-surface)]/90 backdrop-blur">
        <div className="mx-auto flex h-14 w-full max-w-[1080px] items-center gap-3 px-4">
          <div className="flex items-center gap-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-[var(--primary)]">
              <Lock className="h-4 w-4 text-white" />
            </div>
            <span className="text-[15px] font-bold tracking-tight">SmartLock</span>
          </div>
          <div className="ml-auto flex items-center gap-2">
            <LocaleToggle />
            <ThemeToggle />
            {authed ? (
              <Link
                href="/dashboard"
                className="inline-flex h-9 items-center gap-1 rounded-lg bg-[var(--primary)] px-3 text-[13px] font-medium text-white transition hover:bg-[var(--primary-hover)]"
              >
                {t("enterBackend")}
                <ArrowRight className="h-3.5 w-3.5" />
              </Link>
            ) : (
              <Link
                href="/login"
                className="inline-flex h-9 items-center rounded-lg border border-[var(--border)] px-3 text-[13px] font-medium text-[var(--text-primary)] transition hover:border-[var(--border-focus)]"
              >
                {t("navLogin")}
              </Link>
            )}
          </div>
        </div>
      </header>

      <main>
        {/* ── Hero + 雙 CTA ── */}
        <section className="mx-auto flex w-full max-w-[1080px] flex-col items-center px-4 pb-14 pt-16 text-center">
          <span className="mb-4 inline-flex items-center gap-1.5 rounded-full border border-[var(--border)] bg-[var(--bg-surface)] px-3 py-1 text-xs font-medium text-[var(--text-secondary)]">
            <Lock className="h-3 w-3 text-[var(--primary)]" />
            {t("heroEyebrow")}
          </span>
          <h1 className="max-w-[720px] text-4xl font-bold leading-tight tracking-tight sm:text-5xl">
            {t("heroTitle")}
          </h1>
          <p className="mt-5 max-w-[640px] text-[15px] leading-relaxed text-[var(--text-secondary)]">
            {t("heroSubtitle")}
          </p>

          <div className="mt-9 grid w-full max-w-[720px] grid-cols-1 gap-4 sm:grid-cols-2">
            {/* 師傅接單 CTA */}
            <a
              href={TECH_REGISTER_HREF}
              className="group flex flex-col items-start gap-2 rounded-2xl border-2 border-[var(--primary)] bg-[var(--primary)] p-5 text-left text-white shadow-sm transition hover:bg-[var(--primary-hover)]"
            >
              <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-white/15">
                <Wrench className="h-5 w-5" />
              </span>
              <span className="mt-1 flex items-center gap-1.5 text-[15px] font-bold">
                {t("ctaTech")}
                <ArrowRight className="h-4 w-4 transition group-hover:translate-x-0.5" />
              </span>
              <span className="text-[13px] text-white/85">{t("ctaTechHint")}</span>
            </a>

            {/* 品牌申請 CTA */}
            <button
              type="button"
              onClick={() => setApplyOpen(true)}
              className="group flex flex-col items-start gap-2 rounded-2xl border-2 border-[var(--border)] bg-[var(--bg-surface)] p-5 text-left shadow-sm transition hover:border-[var(--primary)]"
            >
              <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-[var(--bg-page)] text-[var(--primary)] transition group-hover:bg-[var(--primary)] group-hover:text-white">
                <Building2 className="h-5 w-5" />
              </span>
              <span className="mt-1 flex items-center gap-1.5 text-[15px] font-bold text-[var(--text-primary)]">
                {t("ctaBrand")}
                <ArrowRight className="h-4 w-4 text-[var(--text-disabled)] transition group-hover:translate-x-0.5 group-hover:text-[var(--primary)]" />
              </span>
              <span className="text-[13px] text-[var(--text-secondary)]">
                {t("ctaBrandHint")}
              </span>
            </button>
          </div>
        </section>

        {/* ── 平台能力 ── */}
        <section className="border-t border-[var(--border)] bg-[var(--bg-surface)]">
          <div className="mx-auto w-full max-w-[1080px] px-4 py-14">
            <h2 className="text-center text-2xl font-bold">{t("featuresTitle")}</h2>
            <div className="mt-8 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
              {features.map(({ icon: Icon, titleKey, descKey }) => (
                <div
                  key={titleKey}
                  className="rounded-2xl border border-[var(--border)] bg-[var(--bg-page)] p-5"
                >
                  <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-[var(--bg-surface)] text-[var(--primary)]">
                    <Icon className="h-5 w-5" />
                  </span>
                  <h3 className="mt-3 text-[15px] font-semibold">{t(titleKey)}</h3>
                  <p className="mt-1.5 text-[13px] leading-relaxed text-[var(--text-secondary)]">
                    {t(descKey)}
                  </p>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* ── 運作流程 ── */}
        <section className="mx-auto w-full max-w-[1080px] px-4 py-14">
          <h2 className="text-center text-2xl font-bold">{t("howTitle")}</h2>
          <div className="mt-8 grid grid-cols-1 gap-4 sm:grid-cols-3">
            {steps.map(({ icon: Icon, titleKey, descKey }, i) => (
              <div
                key={titleKey}
                className="relative rounded-2xl border border-[var(--border)] bg-[var(--bg-surface)] p-5"
              >
                <span className="absolute right-4 top-4 text-3xl font-bold text-[var(--text-disabled)]/40">
                  {i + 1}
                </span>
                <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-[var(--bg-page)] text-[var(--primary)]">
                  <Icon className="h-5 w-5" />
                </span>
                <h3 className="mt-3 text-[15px] font-semibold">{t(titleKey)}</h3>
                <p className="mt-1.5 text-[13px] leading-relaxed text-[var(--text-secondary)]">
                  {t(descKey)}
                </p>
              </div>
            ))}
          </div>
        </section>

        {/* ── 師傅招募帶 ── */}
        <section className="border-t border-[var(--border)] bg-[var(--bg-surface)]">
          <div className="mx-auto flex w-full max-w-[1080px] flex-col items-center gap-6 px-4 py-14 sm:flex-row sm:justify-between">
            <div className="max-w-[560px]">
              <h2 className="text-2xl font-bold">{t("techSectionTitle")}</h2>
              <ul className="mt-4 flex flex-col gap-2">
                {techPoints.map((k) => (
                  <li
                    key={k}
                    className="flex items-start gap-2 text-[14px] text-[var(--text-secondary)]"
                  >
                    <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-[var(--primary)]" />
                    {t(k)}
                  </li>
                ))}
              </ul>
            </div>
            <a
              href={TECH_REGISTER_HREF}
              className="inline-flex h-11 shrink-0 items-center gap-2 rounded-xl bg-[var(--primary)] px-6 text-sm font-semibold text-white transition hover:bg-[var(--primary-hover)]"
            >
              <Wrench className="h-4 w-4" />
              {t("ctaTech")}
            </a>
          </div>
        </section>

        {/* ── 品牌導入帶 ── */}
        <section className="mx-auto flex w-full max-w-[1080px] flex-col items-center gap-4 px-4 py-14 text-center">
          <MapPin className="h-8 w-8 text-[var(--primary)]" />
          <h2 className="text-2xl font-bold">{t("brandSectionTitle")}</h2>
          <p className="max-w-[560px] text-[14px] leading-relaxed text-[var(--text-secondary)]">
            {t("brandSectionDesc")}
          </p>
          <button
            type="button"
            onClick={() => setApplyOpen(true)}
            className="mt-2 inline-flex h-11 items-center gap-2 rounded-xl bg-[var(--primary)] px-6 text-sm font-semibold text-white transition hover:bg-[var(--primary-hover)]"
          >
            <Building2 className="h-4 w-4" />
            {t("ctaBrand")}
          </button>
        </section>
      </main>

      <footer className="border-t border-[var(--border)] py-8 text-center text-xs text-[var(--text-disabled)]">
        {t("footer")}
      </footer>

      {/* ── 品牌申請 modal(品牌基本資料 → /vendors/register 待核准) ── */}
      {applyOpen && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
          onClick={(e) => {
            if (e.target === e.currentTarget) setApplyOpen(false);
          }}
        >
          <div className="max-h-[90vh] w-full max-w-[440px] overflow-y-auto rounded-2xl border border-[var(--border)] bg-[var(--bg-surface)] p-6 shadow-lg">
            <div className="mb-4 flex items-center justify-between">
              <h3 className="text-lg font-bold">{t("applyTitle")}</h3>
              <button
                type="button"
                onClick={() => setApplyOpen(false)}
                aria-label={t("applyClose")}
                className="flex h-8 w-8 items-center justify-center rounded-lg text-[var(--text-secondary)] transition hover:bg-[var(--bg-page)]"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
            <p className="mb-4 text-[13px] leading-relaxed text-[var(--text-secondary)]">
              {t("applyDesc")}
            </p>
            <VendorRegisterForm
              onDone={() => setApplyOpen(false)}
              doneActionLabel={t("applyClose")}
            />
            <p className="mt-4 text-center text-xs text-[var(--text-disabled)]">
              {tR("haveAccount")}{" "}
              <Link href="/login" className="font-medium text-[var(--primary)] hover:underline">
                {t("navLogin")}
              </Link>
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
