"use client";

import { useEffect, useRef, useState } from "react";
import { Languages, Check } from "lucide-react";
import { LOCALES, type Locale } from "@/i18n/config";
import { useLocale, useTranslations } from "./LocaleProvider";

/**
 * LocaleToggle — 語系切換元件
 *
 * 形狀鏡像 ThemeToggle：
 *   - "icon"（預設，給 Header 用）：圓鈕 + popover N 選
 *   - "segmented"（給 Settings 用）：button group 並排
 *
 * 自寫 popover 而非裝 @radix-ui/react-dropdown-menu — 與 ThemeToggle 同理由，
 * 不為 N 選項簡單彈窗新增依賴。
 *
 * a11y：
 *   - aria-label 動態反映當前語系（用 t("locale.current", { label }) 取在地化字串）
 *   - role="menu" + role="menuitemradio" + aria-checked
 *   - 點外面 / ESC 關閉
 */

interface LocaleToggleProps {
  variant?: "icon" | "segmented";
  /** dark 模式下 icon 配色（給深色 sidebar / header 用） */
  tone?: "light" | "dark";
}

export default function LocaleToggle({
  variant = "icon",
  tone = "light",
}: LocaleToggleProps) {
  const { locale, setLocale } = useLocale();

  if (variant === "segmented") {
    return <SegmentedToggle locale={locale} setLocale={setLocale} />;
  }
  return <IconToggle locale={locale} setLocale={setLocale} tone={tone} />;
}

// ─────────────────────────────────────────────────────────────────────────────
// Segmented — button group N 按鈕（給 Settings）
// ─────────────────────────────────────────────────────────────────────────────

function SegmentedToggle({
  locale,
  setLocale,
}: {
  locale: Locale;
  setLocale: (l: Locale) => void;
}) {
  const t = useTranslations("locale");
  return (
    <div
      role="radiogroup"
      aria-label={t("label")}
      className="inline-flex items-center gap-1 rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] p-1"
    >
      {LOCALES.map((opt) => {
        const active = locale === opt.code;
        return (
          <button
            key={opt.code}
            type="button"
            role="radio"
            aria-checked={active}
            onClick={() => setLocale(opt.code)}
            className={`flex items-center gap-[6px] rounded-md px-3 py-[6px] text-sm transition focus-visible:ring-2 focus-visible:ring-[var(--border-focus)] focus-visible:ring-offset-1 ${
              active
                ? "bg-[var(--primary)] text-[var(--text-inverse)] font-semibold"
                : "text-[var(--text-secondary)] hover:bg-[var(--surface-strong)]"
            }`}
          >
            <span>{opt.nativeLabel}</span>
          </button>
        );
      })}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Icon — 單一圓鈕 + popover（給 Header）
// ─────────────────────────────────────────────────────────────────────────────

function IconToggle({
  locale,
  setLocale,
  tone,
}: {
  locale: Locale;
  setLocale: (l: Locale) => void;
  tone: "light" | "dark";
}) {
  const t = useTranslations("locale");
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const currentLabel =
    LOCALES.find((l) => l.code === locale)?.nativeLabel ?? locale;

  useEffect(() => {
    if (!open) return;
    const onClick = (e: MouseEvent) => {
      if (!containerRef.current) return;
      if (!containerRef.current.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", onClick);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onClick);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  const iconColor =
    tone === "dark" ? "text-white" : "text-[var(--text-secondary)]";
  const hoverBg =
    tone === "dark" ? "hover:bg-[#334155]" : "hover:bg-[var(--surface-strong)]";

  return (
    <div ref={containerRef} className="relative">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-label={t("current", { label: currentLabel })}
        aria-haspopup="menu"
        aria-expanded={open}
        title={t("label")}
        className={`flex h-10 w-10 items-center justify-center rounded-lg focus-visible:ring-2 focus-visible:ring-[var(--border-focus)] focus-visible:ring-offset-1 ${hoverBg}`}
      >
        <Languages className={`h-5 w-5 ${iconColor}`} aria-hidden="true" />
      </button>

      {open && (
        <div
          role="menu"
          aria-label={t("menuLabel")}
          className="absolute right-0 top-[calc(100%+4px)] z-50 min-w-[180px] rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] p-1 shadow-[var(--shadow-popover)]"
        >
          {LOCALES.map((opt) => {
            const active = locale === opt.code;
            return (
              <button
                key={opt.code}
                type="button"
                role="menuitemradio"
                aria-checked={active}
                onClick={() => {
                  setLocale(opt.code);
                  setOpen(false);
                }}
                className="flex w-full items-center justify-between gap-2 rounded-md px-3 py-2 text-sm text-[var(--text-primary)] hover:bg-[var(--surface-strong)] focus-visible:bg-[var(--surface-strong)] focus-visible:outline-none"
              >
                <span>{opt.nativeLabel}</span>
                {active && (
                  <Check
                    className="h-4 w-4 text-[var(--primary)]"
                    aria-hidden="true"
                  />
                )}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
