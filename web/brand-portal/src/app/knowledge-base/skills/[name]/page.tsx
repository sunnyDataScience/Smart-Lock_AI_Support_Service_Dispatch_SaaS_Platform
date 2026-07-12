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
          <span className="text-[13px] text-[var(--text-secondary)]">
            <Link href="/knowledge-base/skills" className="hover:text-[var(--primary)] hover:underline">
              知識庫 &gt; AI 技能
            </Link>{" "}
            &gt; {skillName}
          </span>
          <h1 className="font-mono text-xl font-bold text-[var(--text-primary)]">{skillName}</h1>
        </div>

        <SkillEditor skillName={skillName} />
      </div>
    </div>
  );
}
