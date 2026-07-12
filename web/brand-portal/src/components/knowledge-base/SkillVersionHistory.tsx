"use client";

import { useCallback, useEffect, useState } from "react";
import { useToast } from "@/components/ui/Toast";
import { friendlyError } from "@/lib/apiError";
import {
  listRevisions,
  rollbackSkill,
  STATUS_LABEL,
  SOURCE_LABEL,
  type SkillRevision,
} from "@/lib/skills-api";

interface Props {
  skillName: string;
  isAdmin: boolean;
  onView: (version: number) => void;
  onChanged: () => void;
}

function fmt(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return `${String(d.getMonth() + 1).padStart(2, "0")}/${String(d.getDate()).padStart(2, "0")} ${String(
    d.getHours(),
  ).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
}

export default function SkillVersionHistory({ skillName, isAdmin, onView, onChanged }: Props) {
  const { toast } = useToast();
  const [revs, setRevs] = useState<SkillRevision[]>([]);
  const [busy, setBusy] = useState(false);

  const reload = useCallback(async () => {
    try {
      setRevs(await listRevisions(skillName));
    } catch {
      /* 歷史載入失敗不阻斷編輯 */
    }
  }, [skillName]);

  useEffect(() => {
    void reload();
  }, [reload]);

  const handleRollback = async (version: number) => {
    if (!window.confirm(`確定回滾至 v${version}？將立即成為發佈中版本，約 60 秒生效。`)) return;
    setBusy(true);
    try {
      await rollbackSkill(skillName, version);
      toast({ title: `已回滾至 v${version}`, description: "約 60 秒內生效", variant: "success" });
      onChanged();
    } catch (e) {
      toast({ title: friendlyError(e), variant: "error" });
    } finally {
      setBusy(false);
    }
  };

  return (
    <aside className="hidden w-60 shrink-0 flex-col border-l border-[var(--border)] bg-[var(--bg-surface)] lg:flex">
      <div className="px-3 py-2 text-xs font-semibold uppercase tracking-wide text-[var(--text-tertiary)]">
        版本歷史
      </div>
      <div className="flex-1 overflow-auto">
        {revs.length === 0 && (
          <div className="px-3 py-4 text-xs text-[var(--text-tertiary)]">尚無版本</div>
        )}
        {revs.map((r) => (
          <div
            key={r.version}
            className="border-b border-[var(--border)] px-3 py-2.5 text-[13px]"
          >
            <div className="flex items-center justify-between">
              <button
                type="button"
                onClick={() => onView(r.version)}
                className="font-medium text-[var(--text-primary)] tabular-nums hover:text-[var(--primary)] hover:underline"
              >
                v{r.version}
              </button>
              <span
                className={`rounded px-1.5 py-0.5 text-[11px] ${
                  r.status === "published"
                    ? "bg-[var(--success)]/12 text-[var(--success)]"
                    : r.status === "draft"
                      ? "bg-[var(--warning)]/12 text-[var(--warning)]"
                      : "text-[var(--text-tertiary)]"
                }`}
              >
                {STATUS_LABEL[r.status]}
              </span>
            </div>
            <div className="mt-0.5 flex items-center justify-between text-[11px] text-[var(--text-tertiary)]">
              <span>
                {SOURCE_LABEL[r.source]} · {fmt(r.published_at ?? r.created_at)}
              </span>
              {isAdmin && r.status === "retired" && (
                <button
                  type="button"
                  onClick={() => handleRollback(r.version)}
                  disabled={busy}
                  className="font-medium text-[var(--primary)] hover:underline disabled:opacity-50"
                >
                  回滾
                </button>
              )}
            </div>
          </div>
        ))}
      </div>
    </aside>
  );
}
