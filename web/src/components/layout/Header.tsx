"use client";

import { Search, Bell, RefreshCw } from "lucide-react";

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

        <div className="h-[10px] w-[10px] rounded-full bg-[var(--success)]" />

        <button className="relative flex h-10 w-10 items-center justify-center rounded-lg">
          <Bell className="h-5 w-5 text-[var(--text-secondary)]" />
          <span className="absolute right-1 top-1 flex h-[18px] w-[18px] items-center justify-center rounded-full bg-[var(--error)] text-[11px] font-semibold text-white">
            3
          </span>
        </button>

        <button className="flex h-10 w-10 items-center justify-center rounded-lg">
          <RefreshCw className="h-5 w-5 text-[var(--text-secondary)]" />
        </button>
      </div>
    </header>
  );
}
