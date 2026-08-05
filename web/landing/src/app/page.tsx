"use client";

import {
  ArrowRight,
  Bot,
  Building2,
  Check,
  CheckCircle2,
  ClipboardList,
  Clock3,
  Image as ImageIcon,
  Link2,
  Lock,
  MapPin,
  MessageSquareText,
  Minus,
  Phone,
  Smartphone,
  Sparkles,
  Wrench,
} from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { auth } from "@/lib/api";
import { APP_MODE, brandApplyHref, dispatchLoginHref, techRegisterHref } from "@/lib/appMode";
import LocaleToggle from "@/components/i18n/LocaleToggle";
import ThemeToggle from "@/components/theme/ThemeToggle";
import { useTranslations } from "@/components/i18n/LocaleProvider";

// 一頁式平台介紹 landing(2026-07-07 soft UI 改版;動線不變,對齊 20260702 會議 §三
// 「landing 掛申請窗口、半自動化導入」):
//   - 師傅 CTA → 師傅站註冊(techRegisterHref)
//   - 品牌 CTA → platform 站 /platform/apply(brandApplyHref;意向申請,核准後人工開站)
//   - 既有使用者由右上「登入」進派工 portal
// 版面:soft UI(大圓角/軟陰影/粉彩 chip,tokens 在 globals.css `.lp` scope,深淺色皆備)。
// 區段:hero 雙 CTA → 運作流程 → 工單看板預覽 → 全通路接單 → AI 客服對話 → 方案比較
//       → 師傅招募帶 → 尾 CTA。
// `/` 在 AuthGuard PUBLIC_PATHS;tech build 導 /tech-login、dispatch build 不渲染(同前)。

const TECH_REGISTER_HREF = techRegisterHref();
const LOGIN_HREF = dispatchLoginHref();
const BRAND_APPLY_HREF = brandApplyHref();

/** 區段 eyebrow 小標(pill) */
function Eyebrow({ label }: { label: string }) {
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full bg-[var(--lp-primary-soft)] px-3.5 py-1.5 text-xs font-bold text-[var(--lp-primary)]">
      <Sparkles className="h-3.5 w-3.5" aria-hidden />
      {label}
    </span>
  );
}

export default function Home() {
  const t = useTranslations("landing");
  const router = useRouter();
  const [authed, setAuthed] = useState(false);

  // tech build:師傅 stack 只有一條入口,landing 直接進 /tech-login。
  useEffect(() => {
    if (APP_MODE === "tech") router.replace("/tech-login");
  }, [router]);

  // token 只能在 client 讀(localStorage);已登入者頂部顯示「進入後台」捷徑。
  useEffect(() => {
    if (APP_MODE !== "landing") setAuthed(Boolean(auth.getAccessToken()));
  }, []);

  // tech / dispatch build 皆非對外行銷容器,不渲染 landing(同改版前行為)。
  if (APP_MODE === "tech" || APP_MODE === "dispatch") return null;

  const heroChips = ["heroChip1", "heroChip2", "heroChip3"];

  const steps = [
    { icon: MessageSquareText, titleKey: "s1Title", descKey: "s1Desc" },
    { icon: ClipboardList, titleKey: "s2Title", descKey: "s2Desc" },
    { icon: CheckCircle2, titleKey: "s3Title", descKey: "s3Desc" },
  ];

  const omni = [
    { icon: MessageSquareText, titleKey: "omni1Title", descKey: "omni1Desc", chip: "teal" },
    { icon: Link2, titleKey: "omni2Title", descKey: "omni2Desc", chip: "sky" },
    { icon: Phone, titleKey: "omni3Title", descKey: "omni3Desc", chip: "violet" },
    { icon: Smartphone, titleKey: "omni4Title", descKey: "omni4Desc", chip: "amber" },
  ] as const;

  const aiBadges = ["aiB1", "aiB2", "aiB3", "aiB4"];

  // 方案比較:8 個功能列 × 3 方案(true=含);獨立部署為全方案架構標配。
  const priceFeatures: { key: string; plans: [boolean, boolean, boolean] }[] = [
    { key: "pf1", plans: [true, true, true] },
    { key: "pf2", plans: [true, true, true] },
    { key: "pf3", plans: [true, true, true] },
    { key: "pf4", plans: [true, true, true] },
    { key: "pf6", plans: [true, true, true] },
    { key: "pf8", plans: [true, true, true] },
    { key: "pf5", plans: [false, true, true] },
    { key: "pf7", plans: [false, false, true] },
  ];
  const plans = [
    { name: "p1Name", audience: "p1For", price: "p1Price", featured: false, col: 0 },
    { name: "p2Name", audience: "p2For", price: "p2Price", featured: true, col: 1 },
    { name: "p3Name", audience: "p3For", price: "p3Price", featured: false, col: 2 },
  ];

  const techPoints = ["techP1", "techP2", "techP3"];

  const chipCls: Record<string, string> = {
    teal: "bg-[var(--lp-chip-teal)] text-[var(--lp-chip-teal-ink)]",
    sky: "bg-[var(--lp-chip-sky)] text-[var(--lp-chip-sky-ink)]",
    violet: "bg-[var(--lp-chip-violet)] text-[var(--lp-chip-violet-ink)]",
    amber: "bg-[var(--lp-chip-amber)] text-[var(--lp-chip-amber-ink)]",
    rose: "bg-[var(--lp-chip-rose)] text-[var(--lp-chip-rose-ink)]",
  };

  return (
    <div className="lp min-h-screen bg-[var(--lp-bg)] text-[var(--text-primary)]">
      {/* ── 頂部導覽 ── */}
      <header className="sticky top-0 z-40 border-b border-[var(--border)] bg-[var(--lp-bg)]/85 backdrop-blur">
        <div className="mx-auto flex h-14 w-full max-w-[1120px] items-center gap-3 px-4">
          <div className="flex items-center gap-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-[var(--lp-primary)]">
              <Lock className="h-4 w-4 text-[var(--lp-primary-contrast)]" aria-hidden />
            </div>
            <span className="text-[15px] font-bold tracking-tight">SmartLock</span>
          </div>
          <div className="ml-auto flex items-center gap-2">
            <LocaleToggle />
            <ThemeToggle />
            {authed ? (
              <Link
                href="/dashboard"
                className="inline-flex h-9 cursor-pointer items-center gap-1 rounded-full bg-[var(--lp-primary)] px-4 text-[13px] font-semibold text-[var(--lp-primary-contrast)] transition hover:bg-[var(--lp-primary-hover)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--lp-ring)]"
              >
                {t("enterBackend")}
                <ArrowRight className="h-3.5 w-3.5" aria-hidden />
              </Link>
            ) : (
              <Link
                href={LOGIN_HREF}
                className="inline-flex h-9 cursor-pointer items-center rounded-full border border-[var(--border)] bg-[var(--lp-card)] px-4 text-[13px] font-semibold transition hover:border-[var(--lp-primary)] hover:text-[var(--lp-primary)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--lp-ring)]"
              >
                {t("navLogin")}
              </Link>
            )}
          </div>
        </div>
      </header>

      {/* WCAG 2.4.1 Bypass Blocks：LocaleChrome.tsx 的 href="#main-content" 需要
          這個錨點才跳得到。tabIndex={-1} 不可省——沒有它 <main> 不可聚焦，
          skip link 只會捲動而不移動鍵盤焦點，等於沒作用。 */}
      <main id="main-content" tabIndex={-1}>
        {/* ── Hero + 雙 CTA ── */}
        <section className="relative overflow-hidden">
          {/* 柔和色塊背景(裝飾) */}
          <div
            aria-hidden
            className="pointer-events-none absolute -left-32 -top-24 h-[420px] w-[420px] rounded-full"
            style={{ background: "radial-gradient(closest-side, var(--lp-blob-a), transparent)" }}
          />
          <div
            aria-hidden
            className="pointer-events-none absolute -right-40 top-24 h-[480px] w-[480px] rounded-full"
            style={{ background: "radial-gradient(closest-side, var(--lp-blob-b), transparent)" }}
          />

          <div className="relative mx-auto flex w-full max-w-[1120px] flex-col items-center px-4 pb-16 pt-16 text-center sm:pt-20">
            <span className="mb-5 inline-flex items-center gap-1.5 rounded-full border border-[var(--border)] bg-[var(--lp-card)] px-4 py-1.5 text-xs font-semibold text-[var(--text-secondary)] shadow-[var(--lp-shadow-sm)]">
              <Lock className="h-3 w-3 text-[var(--lp-primary)]" aria-hidden />
              {t("heroEyebrow")}
            </span>
            <h1 className="max-w-[760px] text-4xl font-extrabold leading-tight tracking-tight sm:text-5xl">
              {t("heroTitle")}
            </h1>
            <p className="mt-5 max-w-[640px] text-[15px] leading-relaxed text-[var(--text-secondary)]">
              {t("heroSubtitle")}
            </p>

            {/* 信任 chip */}
            <div className="mt-6 flex flex-wrap items-center justify-center gap-2">
              {heroChips.map((k) => (
                <span
                  key={k}
                  className="inline-flex items-center gap-1.5 rounded-full bg-[var(--lp-primary-soft)] px-3.5 py-1.5 text-xs font-semibold text-[var(--lp-primary)]"
                >
                  <CheckCircle2 className="h-3.5 w-3.5" aria-hidden />
                  {t(k)}
                </span>
              ))}
            </div>

            {/* 雙 CTA 卡 */}
            <div className="mt-10 grid w-full max-w-[760px] grid-cols-1 gap-4 sm:grid-cols-2">
              <a
                href={TECH_REGISTER_HREF}
                className="group flex cursor-pointer flex-col items-start gap-2 rounded-3xl bg-[var(--lp-primary)] p-6 text-left text-[var(--lp-primary-contrast)] shadow-[var(--lp-shadow)] transition hover:bg-[var(--lp-primary-hover)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--lp-ring)]"
              >
                <span className="flex h-11 w-11 items-center justify-center rounded-2xl bg-white/20">
                  <Wrench className="h-5 w-5" aria-hidden />
                </span>
                <span className="mt-1 flex items-center gap-1.5 text-[15px] font-bold">
                  {t("ctaTech")}
                  <ArrowRight className="h-4 w-4 transition group-hover:translate-x-0.5" aria-hidden />
                </span>
                <span className="text-[13px] opacity-85">{t("ctaTechHint")}</span>
              </a>

              <a
                href={BRAND_APPLY_HREF}
                className="group flex cursor-pointer flex-col items-start gap-2 rounded-3xl border-2 border-[var(--border)] bg-[var(--lp-card)] p-6 text-left shadow-[var(--lp-shadow-sm)] transition hover:border-[var(--lp-primary)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--lp-ring)]"
              >
                <span className="flex h-11 w-11 items-center justify-center rounded-2xl bg-[var(--lp-accent-soft)] text-[var(--lp-accent)]">
                  <Building2 className="h-5 w-5" aria-hidden />
                </span>
                <span className="mt-1 flex items-center gap-1.5 text-[15px] font-bold">
                  {t("ctaBrand")}
                  <ArrowRight
                    className="h-4 w-4 text-[var(--text-disabled)] transition group-hover:translate-x-0.5 group-hover:text-[var(--lp-primary)]"
                    aria-hidden
                  />
                </span>
                <span className="text-[13px] text-[var(--text-secondary)]">{t("ctaBrandHint")}</span>
              </a>
            </div>

            {/* 已申請品牌 → 免 email 進度查詢入口(platform 站 /platform/apply?mode=lookup) */}
            <a
              href={`${BRAND_APPLY_HREF}?mode=lookup`}
              className="mt-4 text-[13px] font-medium text-[var(--text-secondary)] underline-offset-4 transition hover:text-[var(--lp-primary)] hover:underline focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--lp-ring)]"
            >
              {t("brandLookupLink")}
            </a>
          </div>
        </section>

        {/* ── 運作流程(三步驟細帶) ── */}
        <section className="mx-auto w-full max-w-[1120px] px-4 pb-16">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            {steps.map(({ icon: Icon, titleKey, descKey }, i) => (
              <div
                key={titleKey}
                className="relative rounded-3xl bg-[var(--lp-card)] p-5 shadow-[var(--lp-shadow-sm)]"
              >
                <span
                  aria-hidden
                  className="absolute right-5 top-4 text-3xl font-extrabold text-[var(--text-disabled)]/30"
                >
                  {i + 1}
                </span>
                <span className="flex h-10 w-10 items-center justify-center rounded-2xl bg-[var(--lp-primary-soft)] text-[var(--lp-primary)]">
                  <Icon className="h-5 w-5" aria-hidden />
                </span>
                <h3 className="mt-3 text-[15px] font-bold">{t(titleKey)}</h3>
                <p className="mt-1.5 text-[13px] leading-relaxed text-[var(--text-secondary)]">
                  {t(descKey)}
                </p>
              </div>
            ))}
          </div>
        </section>

        {/* ── 工單管理預覽 ── */}
        <section className="border-t border-[var(--border)] bg-[var(--lp-card)]/60">
          <div className="mx-auto w-full max-w-[1120px] px-4 py-16">
            <div className="flex flex-col items-center text-center">
              <Eyebrow label={t("secWo")} />
              <h2 className="mt-4 text-2xl font-extrabold sm:text-3xl">{t("woTitle")}</h2>
              <p className="mt-3 max-w-[620px] text-[14px] leading-relaxed text-[var(--text-secondary)]">
                {t("woDesc")}
              </p>
            </div>

            {/* 看板 mock(展示用,非互動) */}
            <div className="mt-10 grid grid-cols-1 gap-4 md:grid-cols-3" aria-hidden>
              {/* 待派工 */}
              <div className="rounded-3xl bg-[var(--lp-bg)] p-4 shadow-[var(--lp-shadow-sm)]">
                <div className="flex items-center gap-2 px-1 pb-3">
                  <span className="h-2.5 w-2.5 rounded-full bg-[var(--lp-chip-amber-ink)]" />
                  <span className="text-[13px] font-bold">{t("woCol1")}</span>
                </div>
                <div className="rounded-2xl bg-[var(--lp-card)] p-4 shadow-[var(--lp-shadow-sm)]">
                  <div className="flex items-start justify-between gap-2">
                    <p className="text-[14px] font-semibold leading-snug">{t("woT1Title")}</p>
                    <span className={`shrink-0 rounded-full px-2 py-0.5 text-[11px] font-bold ${chipCls.rose}`}>
                      {t("woT1Tag")}
                    </span>
                  </div>
                  <p className="mt-2 flex items-center gap-1 text-[12px] text-[var(--text-secondary)]">
                    <MapPin className="h-3.5 w-3.5" />
                    {t("woT1Meta")}
                  </p>
                  <p className="mt-1.5 flex items-center gap-1 text-[12px] text-[var(--lp-chip-amber-ink)]">
                    <Clock3 className="h-3.5 w-3.5" />
                    SLA 02:00
                  </p>
                </div>
              </div>

              {/* 進行中 */}
              <div className="rounded-3xl bg-[var(--lp-bg)] p-4 shadow-[var(--lp-shadow-sm)]">
                <div className="flex items-center gap-2 px-1 pb-3">
                  <span className="h-2.5 w-2.5 rounded-full bg-[var(--lp-chip-sky-ink)]" />
                  <span className="text-[13px] font-bold">{t("woCol2")}</span>
                </div>
                <div className="rounded-2xl bg-[var(--lp-card)] p-4 shadow-[var(--lp-shadow-sm)]">
                  <p className="text-[14px] font-semibold leading-snug">{t("woT2Title")}</p>
                  <p className="mt-2 flex items-center gap-1 text-[12px] text-[var(--text-secondary)]">
                    <MapPin className="h-3.5 w-3.5" />
                    {t("woT2Meta")}
                  </p>
                  <p className={`mt-2 inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[12px] font-semibold ${chipCls.sky}`}>
                    <Wrench className="h-3.5 w-3.5" />
                    {t("woT2Tech")}
                  </p>
                </div>
              </div>

              {/* 已完成 */}
              <div className="rounded-3xl bg-[var(--lp-bg)] p-4 shadow-[var(--lp-shadow-sm)]">
                <div className="flex items-center gap-2 px-1 pb-3">
                  <span className="h-2.5 w-2.5 rounded-full bg-[var(--lp-chip-teal-ink)]" />
                  <span className="text-[13px] font-bold">{t("woCol3")}</span>
                </div>
                <div className="rounded-2xl bg-[var(--lp-card)] p-4 shadow-[var(--lp-shadow-sm)]">
                  <p className="text-[14px] font-semibold leading-snug">{t("woT3Title")}</p>
                  <p className="mt-2 flex items-center gap-1 text-[12px] text-[var(--text-secondary)]">
                    <MapPin className="h-3.5 w-3.5" />
                    {t("woT3Meta")}
                  </p>
                  <p className={`mt-2 inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[12px] font-semibold ${chipCls.teal}`}>
                    <CheckCircle2 className="h-3.5 w-3.5" />
                    {t("woT3Tech")}
                  </p>
                </div>
              </div>
            </div>

            <ul className="mx-auto mt-8 grid max-w-[880px] grid-cols-1 gap-3 sm:grid-cols-3">
              {(["woB1", "woB2", "woB3"] as const).map((k) => (
                <li key={k} className="flex items-start gap-2 text-[13px] leading-relaxed text-[var(--text-secondary)]">
                  <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-[var(--lp-primary)]" aria-hidden />
                  {t(k)}
                </li>
              ))}
            </ul>
          </div>
        </section>

        {/* ── 全通路接單 ── */}
        <section className="mx-auto w-full max-w-[1120px] px-4 py-16">
          <div className="flex flex-col items-center text-center">
            <Eyebrow label={t("secOmni")} />
            <h2 className="mt-4 text-2xl font-extrabold sm:text-3xl">{t("omniTitle")}</h2>
            <p className="mt-3 max-w-[620px] text-[14px] leading-relaxed text-[var(--text-secondary)]">
              {t("omniDesc")}
            </p>
          </div>
          <div className="mt-10 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {omni.map(({ icon: Icon, titleKey, descKey, chip }) => (
              <div
                key={titleKey}
                className="rounded-3xl bg-[var(--lp-card)] p-5 shadow-[var(--lp-shadow-sm)] transition hover:-translate-y-0.5 hover:shadow-[var(--lp-shadow)] motion-reduce:transition-none motion-reduce:hover:translate-y-0"
              >
                <span className={`flex h-11 w-11 items-center justify-center rounded-2xl ${chipCls[chip]}`}>
                  <Icon className="h-5 w-5" aria-hidden />
                </span>
                <h3 className="mt-3 text-[15px] font-bold">{t(titleKey)}</h3>
                <p className="mt-1.5 text-[13px] leading-relaxed text-[var(--text-secondary)]">
                  {t(descKey)}
                </p>
              </div>
            ))}
          </div>
        </section>

        {/* ── AI 客服對話 ── */}
        <section className="border-t border-[var(--border)] bg-[var(--lp-card)]/60">
          <div className="mx-auto grid w-full max-w-[1120px] grid-cols-1 items-center gap-10 px-4 py-16 lg:grid-cols-2">
            <div>
              <Eyebrow label={t("secAi")} />
              <h2 className="mt-4 text-2xl font-extrabold sm:text-3xl">{t("aiTitle")}</h2>
              <p className="mt-3 max-w-[520px] text-[14px] leading-relaxed text-[var(--text-secondary)]">
                {t("aiDesc")}
              </p>
              <div className="mt-6 flex flex-wrap gap-2">
                {aiBadges.map((k) => (
                  <span
                    key={k}
                    className="inline-flex items-center gap-1.5 rounded-full bg-[var(--lp-primary-soft)] px-3.5 py-1.5 text-[12px] font-semibold text-[var(--lp-primary)]"
                  >
                    <Sparkles className="h-3.5 w-3.5" aria-hidden />
                    {t(k)}
                  </span>
                ))}
              </div>
            </div>

            {/* LINE 風格對話 mock(展示用) */}
            <div className="rounded-3xl bg-[var(--lp-card)] p-5 shadow-[var(--lp-shadow)]" aria-hidden>
              <div className="flex items-center gap-2 border-b border-[var(--border)] pb-3">
                <span className="flex h-9 w-9 items-center justify-center rounded-2xl bg-[var(--lp-primary-soft)] text-[var(--lp-primary)]">
                  <Bot className="h-5 w-5" />
                </span>
                <div>
                  <p className="text-[13px] font-bold">SmartLock AI</p>
                  <p className="flex items-center gap-1 text-[11px] text-[var(--lp-primary)]">
                    <span className="h-1.5 w-1.5 rounded-full bg-current" />
                    Online・24hr
                  </p>
                </div>
              </div>
              <div className="mt-4 flex flex-col gap-3">
                <div className="flex justify-end">
                  <div className="max-w-[85%] rounded-2xl rounded-br-md bg-[var(--lp-primary)] px-4 py-2.5 text-[13px] leading-relaxed text-[var(--lp-primary-contrast)]">
                    {t("aiChatU1")}
                    <span className="mt-2 flex items-center gap-1.5 rounded-xl bg-white/15 px-2.5 py-1.5 text-[11px]">
                      <ImageIcon className="h-3.5 w-3.5" />
                      {t("aiChatPhoto")}・IMG_2041.jpg
                    </span>
                  </div>
                </div>
                <div className="flex justify-start">
                  <div className="max-w-[85%] rounded-2xl rounded-bl-md bg-[var(--lp-bg)] px-4 py-2.5 text-[13px] leading-relaxed">
                    {t("aiChatA1")}
                  </div>
                </div>
                <div className="flex justify-end">
                  <div className="max-w-[85%] rounded-2xl rounded-br-md bg-[var(--lp-primary)] px-4 py-2.5 text-[13px] leading-relaxed text-[var(--lp-primary-contrast)]">
                    {t("aiChatU2")}
                  </div>
                </div>
                <div className="flex justify-start">
                  <div className="max-w-[85%] rounded-2xl rounded-bl-md bg-[var(--lp-bg)] px-4 py-2.5 text-[13px] leading-relaxed">
                    {t("aiChatA2")}
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* ── 方案比較 ── */}
        <section className="mx-auto w-full max-w-[1120px] px-4 py-16">
          <div className="flex flex-col items-center text-center">
            <Eyebrow label={t("secPrice")} />
            <h2 className="mt-4 text-2xl font-extrabold sm:text-3xl">{t("priceTitle")}</h2>
            <p className="mt-3 max-w-[640px] text-[14px] leading-relaxed text-[var(--text-secondary)]">
              {t("priceDesc")}
            </p>
          </div>

          <div className="mt-10 grid grid-cols-1 gap-4 md:grid-cols-3">
            {plans.map(({ name, audience, price, featured, col }) => (
              <div
                key={name}
                className={`relative flex flex-col rounded-3xl bg-[var(--lp-card)] p-6 ${
                  featured
                    ? "shadow-[var(--lp-shadow)] ring-2 ring-[var(--lp-primary)]"
                    : "shadow-[var(--lp-shadow-sm)]"
                }`}
              >
                {featured && (
                  <span className="absolute -top-3 left-1/2 -translate-x-1/2 rounded-full bg-[var(--lp-primary)] px-3.5 py-1 text-[11px] font-bold text-[var(--lp-primary-contrast)]">
                    {t("priceRecommended")}
                  </span>
                )}
                <h3 className="text-[17px] font-extrabold">{t(name)}</h3>
                <p className="mt-0.5 text-[12px] text-[var(--text-secondary)]">{t(audience)}</p>
                <p className="mt-4 text-2xl font-extrabold text-[var(--lp-primary)]">{t(price)}</p>
                <ul className="mt-5 flex flex-col gap-2.5 border-t border-[var(--border)] pt-5">
                  {priceFeatures.map(({ key, plans: cols }) => (
                    <li
                      key={key}
                      className={`flex items-start gap-2 text-[13px] leading-snug ${
                        cols[col] ? "" : "text-[var(--text-disabled)]"
                      }`}
                    >
                      {cols[col] ? (
                        <Check className="mt-0.5 h-4 w-4 shrink-0 text-[var(--lp-primary)]" aria-hidden />
                      ) : (
                        <Minus className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
                      )}
                      {t(key)}
                    </li>
                  ))}
                </ul>
                <a
                  href={BRAND_APPLY_HREF}
                  className={`mt-6 inline-flex h-11 cursor-pointer items-center justify-center gap-1.5 rounded-full text-[13.5px] font-bold transition focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--lp-ring)] ${
                    featured
                      ? "bg-[var(--lp-primary)] text-[var(--lp-primary-contrast)] hover:bg-[var(--lp-primary-hover)]"
                      : "border border-[var(--border)] hover:border-[var(--lp-primary)] hover:text-[var(--lp-primary)]"
                  }`}
                >
                  {t("priceCta")}
                  <ArrowRight className="h-4 w-4" aria-hidden />
                </a>
              </div>
            ))}
          </div>
          <p className="mt-6 text-center text-[12px] text-[var(--text-disabled)]">{t("priceNote")}</p>
        </section>

        {/* ── 師傅招募帶 ── */}
        <section className="border-t border-[var(--border)] bg-[var(--lp-card)]/60">
          <div className="mx-auto flex w-full max-w-[1120px] flex-col items-center gap-6 px-4 py-16 sm:flex-row sm:justify-between">
            <div className="max-w-[560px]">
              <h2 className="text-2xl font-extrabold">{t("techSectionTitle")}</h2>
              <ul className="mt-4 flex flex-col gap-2.5">
                {techPoints.map((k) => (
                  <li key={k} className="flex items-start gap-2 text-[14px] text-[var(--text-secondary)]">
                    <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-[var(--lp-primary)]" aria-hidden />
                    {t(k)}
                  </li>
                ))}
              </ul>
            </div>
            <a
              href={TECH_REGISTER_HREF}
              className="inline-flex h-12 shrink-0 cursor-pointer items-center gap-2 rounded-full bg-[var(--lp-primary)] px-7 text-sm font-bold text-[var(--lp-primary-contrast)] shadow-[var(--lp-shadow-sm)] transition hover:bg-[var(--lp-primary-hover)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--lp-ring)]"
            >
              <Wrench className="h-4 w-4" aria-hidden />
              {t("ctaTech")}
            </a>
          </div>
        </section>

        {/* ── 尾 CTA ── */}
        <section className="mx-auto w-full max-w-[1120px] px-4 py-16">
          <div className="flex flex-col items-center gap-5 rounded-3xl bg-[var(--lp-primary)] px-6 py-12 text-center text-[var(--lp-primary-contrast)] shadow-[var(--lp-shadow)]">
            <h2 className="max-w-[560px] text-2xl font-extrabold sm:text-3xl">{t("finalTitle")}</h2>
            <p className="max-w-[520px] text-[14px] leading-relaxed opacity-85">{t("finalDesc")}</p>
            <div className="mt-2 flex flex-col gap-3 sm:flex-row">
              <a
                href={BRAND_APPLY_HREF}
                className="inline-flex h-12 cursor-pointer items-center justify-center gap-2 rounded-full bg-[var(--lp-primary-contrast)] px-7 text-sm font-bold text-[var(--lp-primary)] transition hover:opacity-90 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-white"
              >
                <Building2 className="h-4 w-4" aria-hidden />
                {t("ctaBrand")}
              </a>
              <a
                href={TECH_REGISTER_HREF}
                className="inline-flex h-12 cursor-pointer items-center justify-center gap-2 rounded-full border-2 border-current px-7 text-sm font-bold transition hover:opacity-80 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-white"
              >
                <Wrench className="h-4 w-4" aria-hidden />
                {t("ctaTech")}
              </a>
            </div>
          </div>
        </section>
      </main>

      <footer className="border-t border-[var(--border)] py-8 text-center text-xs text-[var(--text-disabled)]">
        {t("footer")}
      </footer>
    </div>
  );
}
