"use client";

import { use } from "react";
import Link from "next/link";
import Sidebar from "@/components/layout/Sidebar";
import SkillEditor from "@/components/knowledge-base/SkillEditor";

export default function SkillEditPage({
  params,
}: {
  params: Promise<{ name: string }>;
}) {
  const { name } = use(params);
  const skillName = decodeURIComponent(name);

  return (
    <div className="flex h-full bg-[var(--bg-page)]">
      <Sidebar />

      <div className="flex flex-1 flex-col overflow-hidden">
        <div className="flex flex-col gap-2 border-b border-[var(--border)] bg-[var(--bg-surface)] pl-14 pr-4 md:px-8 pt-5 pb-4">
          <Link
            href="/knowledge-base/skills"
            className="inline-flex w-fit items-center gap-1.5 text-[13px] font-medium text-[var(--text-secondary)] transition-colors hover:text-[var(--primary)]"
          >
            <svg
              width="15"
              height="15"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              aria-hidden="true"
            >
              <path d="m15 18-6-6 6-6" />
            </svg>
            返回 AI 技能列表
          </Link>
          <h1 className="font-mono text-xl font-bold text-[var(--text-primary)]">{skillName}</h1>
        </div>

        <SkillEditor skillName={skillName} />
      </div>
    </div>
  );
}
