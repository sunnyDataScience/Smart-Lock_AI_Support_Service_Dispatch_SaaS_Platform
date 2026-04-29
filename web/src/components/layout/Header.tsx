"use client";

import { Search } from "lucide-react";
import NotificationBell from "./NotificationBell";

interface HeaderProps {
  title: string;
  subtitle?: string;
}

export default function Header({ title, subtitle }: HeaderProps) {
  return (
    <header className="flex h-16 items-center justify-between border-b border-[var(--border)] bg-[var(--bg-surface)] px-6">
      <div className="flex items-center gap-4">
        <h1 className="text-[24px] font-semibold tracking-tight text-[#18181B]">
          {title}
        </h1>
        {subtitle && (
          <span className="text-[14px] text-[var(--text-secondary)]">
            {subtitle}
          </span>
        )}
      </div>

      <div className="flex items-center gap-4">
        <div className="flex w-[320px] items-center gap-2 rounded-xl border border-[#E4E4E7] px-3 py-0">
          <Search className="h-[18px] w-[18px] text-[#A1A1AA]" />
          <input
            type="text"
            placeholder="搜尋工單、技師、客戶..."
            className="h-10 flex-1 bg-transparent text-[14px] text-[#18181B] outline-none placeholder:text-[#A1A1AA]"
          />
        </div>

        <NotificationBell />
      </div>
    </header>
  );
}
