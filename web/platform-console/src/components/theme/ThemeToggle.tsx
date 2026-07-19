"use client";

import { useEffect, useRef, useState } from "react";
import { Monitor, Moon, Sun, Check } from "lucide-react";
import { useTranslations } from "@/components/i18n/LocaleProvider";
import { useTheme, type Theme } from "./ThemeProvider";

/**
 * ThemeToggle — 主題切換元件
 *
 * 兩種變體：
 *   - "icon"（預設，給 Header 用）：icon-only 按鈕 + popover 三選
 *   - "segmented"（給 Settings 用）：button group 三按鈕並排
 *
 * 為什麼自寫 popover 而不裝 @radix-ui/react-dropdown-menu：
 *   專案沒裝 dropdown-menu，避免新增依賴。3 個選項的簡單彈窗用 native 即可。
 *   focus trap 不關鍵（按 ESC / 點外面關閉就夠用）。
 */

interface ThemeOption {
  value: Theme;
  /** i18n key（theme namespace）— UAT R3：:3003 主題選單/aria-label 接 i18n（鏡像 :3000 W6-1 修法） */
  labelKey: "light" | "dark" | "system";
  icon: typeof Sun;
}

const OPTIONS: readonly ThemeOption[] = [
  { value: "light", labelKey: "light", icon: Sun },
  { value: "dark", labelKey: "dark", icon: Moon },
  { value: "system", labelKey: "system", icon: Monitor },
] as const;

function getCurrentIcon(theme: Theme) {
  return OPTIONS.find((opt) => opt.value === theme)?.icon ?? Monitor;
}

interface ThemeToggleProps {
  /**
   * 視覺變體：
   *   - "icon"：只顯示一個圓鈕，點開彈三選（給 Header 等空間有限處）
   *   - "segmented"：button group 三按鈕並排（給 Settings 表單）
   */
  variant?: "icon" | "segmented";
  /** dark 模式下 icon 配色（給深色 sidebar / header 用） */
  tone?: "light" | "dark";
}

export default function ThemeToggle({
  variant = "icon",
  tone = "light",
}: ThemeToggleProps) {
  const { theme, setTheme } = useTheme();

  if (variant === "segmented") {
    return <SegmentedToggle theme={theme} setTheme={setTheme} />;
  }
  return <IconToggle theme={theme} setTheme={setTheme} tone={tone} />;
}

// ─────────────────────────────────────────────────────────────────────────────
// Segmented — button group 三按鈕（給 Settings）
// ─────────────────────────────────────────────────────────────────────────────

function SegmentedToggle({
  theme,
  setTheme,
}: {
  theme: Theme;
  setTheme: (t: Theme) => void;
}) {
  const t = useTranslations("theme");
  return (
    <div
      role="radiogroup"
      aria-label={t("label")}
      className="inline-flex items-center gap-1 rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] p-1"
    >
      {OPTIONS.map((opt) => {
        const Icon = opt.icon;
        const active = theme === opt.value;
        return (
          <button
            key={opt.value}
            type="button"
            role="radio"
            aria-checked={active}
            onClick={() => setTheme(opt.value)}
            className={`flex items-center gap-[6px] rounded-md px-3 py-[6px] text-sm transition focus-visible:ring-2 focus-visible:ring-[var(--border-focus)] focus-visible:ring-offset-1 ${
              active
                ? "bg-[var(--primary)] text-[var(--text-inverse)] font-semibold"
                : "text-[var(--text-secondary)] hover:bg-[var(--surface-strong)]"
            }`}
          >
            <Icon className="h-4 w-4" aria-hidden="true" />
            <span>{t(opt.labelKey)}</span>
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
  theme,
  setTheme,
  tone,
}: {
  theme: Theme;
  setTheme: (t: Theme) => void;
  tone: "light" | "dark";
}) {
  const t = useTranslations("theme");
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const CurrentIcon = getCurrentIcon(theme);

  // 點外面 / ESC 關閉 popover
  useEffect(() => {
    if (!open) return;

    const onClick = (e: MouseEvent) => {
      if (!containerRef.current) return;
      if (!containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
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

  const iconColor = tone === "dark"
    ? "text-white"
    : "text-[var(--text-secondary)]";
  const hoverBg = tone === "dark"
    ? "hover:bg-[#334155]"
    : "hover:bg-[var(--surface-strong)]";

  return (
    <div ref={containerRef} className="relative">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-label={t("current", {
          label: t(OPTIONS.find((o) => o.value === theme)?.labelKey ?? "system"),
        })}
        aria-haspopup="menu"
        aria-expanded={open}
        title={t("label")}
        className={`flex h-10 w-10 items-center justify-center rounded-lg focus-visible:ring-2 focus-visible:ring-[var(--border-focus)] focus-visible:ring-offset-1 ${hoverBg}`}
      >
        <CurrentIcon className={`h-5 w-5 ${iconColor}`} aria-hidden="true" />
      </button>

      {open && (
        <div
          role="menu"
          aria-label={t("menuLabel")}
          className="absolute right-0 top-[calc(100%+4px)] z-50 min-w-[160px] rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] p-1 shadow-[var(--shadow-popover)]"
        >
          {OPTIONS.map((opt) => {
            const Icon = opt.icon;
            const active = theme === opt.value;
            return (
              <button
                key={opt.value}
                type="button"
                role="menuitemradio"
                aria-checked={active}
                onClick={() => {
                  setTheme(opt.value);
                  setOpen(false);
                }}
                className="flex w-full items-center justify-between gap-2 rounded-md px-3 py-2 text-sm text-[var(--text-primary)] hover:bg-[var(--surface-strong)] focus-visible:bg-[var(--surface-strong)] focus-visible:outline-none"
              >
                <span className="flex items-center gap-2">
                  <Icon
                    className="h-4 w-4 text-[var(--text-secondary)]"
                    aria-hidden="true"
                  />
                  {t(opt.labelKey)}
                </span>
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
