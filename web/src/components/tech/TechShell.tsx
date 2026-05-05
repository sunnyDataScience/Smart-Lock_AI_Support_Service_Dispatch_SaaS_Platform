"use client";

import type { ReactNode } from "react";
import DesktopMobileGuard from "./DesktopMobileGuard";
import TechBottomNav from "./TechBottomNav";

interface Props {
  title?: string;
  children: ReactNode;
}

export default function TechShell({ title, children }: Props) {
  return (
    <DesktopMobileGuard>
      <div className="flex min-h-screen w-full justify-center bg-[var(--bg-page)]">
        <div className="flex min-h-screen w-full max-w-[480px] flex-col bg-white shadow-sm">
          {title && (
            <header className="sticky top-0 z-20 flex h-14 items-center border-b border-[var(--border)] bg-white px-4">
              <h1 className="text-[18px] font-semibold text-[#1E293B]">
                {title}
              </h1>
            </header>
          )}
          <main className="flex-1 overflow-y-auto">{children}</main>
          <TechBottomNav />
        </div>
      </div>
    </DesktopMobileGuard>
  );
}
