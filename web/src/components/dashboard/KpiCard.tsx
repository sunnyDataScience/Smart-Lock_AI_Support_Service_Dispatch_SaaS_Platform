import type { LucideIcon } from "lucide-react";

interface KpiCardProps {
  title: string;
  value: string;
  subtitle: string;
  subtitleColor?: string;
  valueColor?: string;
  accentColor: string;
  iconBgColor: string;
  icon: LucideIcon;
  progressBar?: { value: number; color: string };
}

export default function KpiCard({
  title,
  value,
  subtitle,
  subtitleColor = "#71717A",
  valueColor = "#18181B",
  accentColor,
  iconBgColor,
  icon: Icon,
  progressBar,
}: KpiCardProps) {
  return (
    <div className="flex flex-1 overflow-hidden rounded-lg border border-[var(--border)] bg-[var(--bg-surface)]">
      <div
        className="w-1 self-stretch rounded-l-sm"
        style={{ backgroundColor: accentColor }}
      />
      <div className="flex flex-1 items-center justify-between px-4 py-5 pl-4 pr-5">
        <div className="flex flex-col gap-1">
          <span className="text-[13px] text-[#71717A]">{title}</span>
          <span
            className="text-[36px] font-bold leading-none"
            style={{ color: valueColor }}
          >
            {value}
          </span>
          <span className="text-[12px]" style={{ color: subtitleColor }}>
            {subtitle}
          </span>
          {progressBar && (
            <div className="mt-1 h-[6px] w-full rounded-[3px] bg-[#E4E4E7]">
              <div
                className="h-full rounded-[3px]"
                style={{
                  width: `${progressBar.value}%`,
                  backgroundColor: progressBar.color,
                }}
              />
            </div>
          )}
        </div>
        <div
          className="flex h-10 w-10 items-center justify-center rounded-lg"
          style={{ backgroundColor: iconBgColor }}
        >
          <Icon className="h-5 w-5" style={{ color: accentColor }} />
        </div>
      </div>
    </div>
  );
}
