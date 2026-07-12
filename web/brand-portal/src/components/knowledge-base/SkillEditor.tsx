"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useToast } from "@/components/ui/Toast";
import { friendlyError } from "@/lib/apiError";
import { getCurrentSession } from "@/lib/api";
import {
  getSkill,
  saveDraft,
  publishSkill,
  STATUS_LABEL,
  type SkillDetail,
  type SkillStatus,
} from "@/lib/skills-api";
import SkillVersionHistory from "@/components/knowledge-base/SkillVersionHistory";

const SKILL_MD = "SKILL.md";

function isReferenceFile(path: string): boolean {
  return path !== SKILL_MD;
}

interface Props {
  skillName: string;
}

export default function SkillEditor({ skillName }: Props) {
  const { toast } = useToast();
  const isAdmin = getCurrentSession()?.role === "admin";

  const [files, setFiles] = useState<Record<string, string>>({});
  const [selected, setSelected] = useState<string>(SKILL_MD);
  const [viewingVersion, setViewingVersion] = useState<number | null>(null);
  const [viewingStatus, setViewingStatus] = useState<SkillStatus>("draft");
  const [draftVersion, setDraftVersion] = useState<number | null>(null);
  const [dirty, setDirty] = useState(false);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [historyKey, setHistoryKey] = useState(0); // 觸發歷史面板重載
  const [newPath, setNewPath] = useState("");

  const applyDetail = useCallback((d: SkillDetail) => {
    setFiles(d.files ?? {});
    setViewingVersion(d.version);
    setViewingStatus(d.status);
    setDraftVersion(d.status === "draft" ? d.version : null);
    setDirty(false);
    setSelected((prev) => (d.files && prev in d.files ? prev : SKILL_MD));
  }, []);

  const load = useCallback(
    async (version?: number) => {
      setLoading(true);
      try {
        applyDetail(await getSkill(skillName, version));
      } catch (e) {
        toast({ title: friendlyError(e), variant: "error" });
      } finally {
        setLoading(false);
      }
    },
    [skillName, applyDetail, toast],
  );

  useEffect(() => {
    void load();
  }, [load]);

  const fileList = useMemo(() => {
    const keys = Object.keys(files);
    return [
      ...keys.filter((k) => k === SKILL_MD),
      ...keys.filter(isReferenceFile).sort(),
    ];
  }, [files]);

  const onEdit = (value: string) => {
    setFiles((prev) => ({ ...prev, [selected]: value }));
    setDirty(true);
  };

  const addFile = () => {
    const path = newPath.trim();
    if (!path) return;
    if (path in files) {
      toast({ title: "檔案已存在", variant: "warning" });
      return;
    }
    setFiles((prev) => ({ ...prev, [path]: "" }));
    setSelected(path);
    setNewPath("");
    setDirty(true);
  };

  const removeFile = (path: string) => {
    if (path === SKILL_MD) return;
    setFiles((prev) => {
      const next = { ...prev };
      delete next[path];
      return next;
    });
    if (selected === path) setSelected(SKILL_MD);
    setDirty(true);
  };

  const handleSave = async (): Promise<number | null> => {
    setBusy(true);
    try {
      const res = await saveDraft(skillName, files);
      setDraftVersion(res.version);
      setViewingVersion(res.version);
      setViewingStatus("draft");
      setDirty(false);
      setHistoryKey((k) => k + 1);
      toast({ title: `已存為草稿 v${res.version}`, variant: "success" });
      return res.version;
    } catch (e) {
      toast({ title: friendlyError(e), variant: "error" });
      return null;
    } finally {
      setBusy(false);
    }
  };

  const handlePublish = async () => {
    // 有未存變更 → 先存草稿再發佈
    let version = draftVersion;
    if (dirty || version == null) {
      version = await handleSave();
      if (version == null) return;
    }
    setBusy(true);
    try {
      await publishSkill(skillName, version);
      setHistoryKey((k) => k + 1);
      await load();
      toast({
        title: `已發佈 v${version}`,
        description: "約 60 秒內生效於 LINE 客服",
        variant: "success",
      });
    } catch (e) {
      toast({ title: friendlyError(e), variant: "error" });
    } finally {
      setBusy(false);
    }
  };

  if (loading) {
    return <div className="p-8 text-sm text-[var(--text-secondary)]">載入中…</div>;
  }

  return (
    <div className="flex flex-1 flex-col overflow-hidden">
      {/* Action bar */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[var(--border)] bg-[var(--bg-surface)] px-4 py-3 md:px-8">
        <div className="flex items-center gap-3 text-sm text-[var(--text-secondary)]">
          <span>
            檢視版本{" "}
            <span className="font-medium text-[var(--text-primary)] tabular-nums">
              v{viewingVersion}
            </span>
          </span>
          <span className="text-[var(--text-tertiary)]">·</span>
          <span>{STATUS_LABEL[viewingStatus]}</span>
          {dirty && <span className="text-[var(--warning)]">· 未儲存變更</span>}
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={handleSave}
            disabled={busy || !dirty}
            className="rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] px-4 py-2 text-sm font-medium text-[var(--text-primary)] transition-colors hover:bg-[var(--bg-page)] disabled:cursor-not-allowed disabled:opacity-50"
          >
            存草稿
          </button>
          {isAdmin && (
            <button
              type="button"
              onClick={handlePublish}
              disabled={busy}
              className="rounded-lg bg-[var(--primary)] px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-[var(--primary-hover)] disabled:cursor-not-allowed disabled:opacity-50"
            >
              發佈
            </button>
          )}
        </div>
      </div>

      <div className="flex flex-1 overflow-hidden">
        {/* File list */}
        <aside className="flex w-48 shrink-0 flex-col border-r border-[var(--border)] bg-[var(--bg-surface)] md:w-56">
          <div className="px-3 py-2 text-xs font-semibold uppercase tracking-wide text-[var(--text-tertiary)]">
            檔案
          </div>
          <div className="flex-1 overflow-auto">
            {fileList.map((path) => (
              <div
                key={path}
                className={`group flex items-center justify-between px-3 py-2 text-[13px] ${
                  selected === path
                    ? "bg-[var(--primary-light)]/50 text-[var(--primary)]"
                    : "text-[var(--text-secondary)] hover:bg-[var(--bg-page)]"
                }`}
              >
                <button
                  type="button"
                  onClick={() => setSelected(path)}
                  className="flex-1 truncate text-left font-mono"
                  title={path}
                >
                  {path}
                </button>
                {isReferenceFile(path) && (
                  <button
                    type="button"
                    onClick={() => removeFile(path)}
                    className="ml-1 hidden text-[var(--text-tertiary)] hover:text-[var(--error)] group-hover:block"
                    aria-label={`刪除 ${path}`}
                  >
                    ×
                  </button>
                )}
              </div>
            ))}
          </div>
          <div className="flex gap-1 border-t border-[var(--border)] p-2">
            <input
              value={newPath}
              onChange={(e) => setNewPath(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && addFile()}
              placeholder="references/…"
              className="min-w-0 flex-1 rounded border border-[var(--border)] bg-[var(--bg-page)] px-2 py-1 text-xs text-[var(--text-primary)] focus:border-[var(--border-focus)] focus:outline-none"
            />
            <button
              type="button"
              onClick={addFile}
              className="shrink-0 rounded border border-[var(--border)] px-2 py-1 text-xs text-[var(--text-secondary)] hover:bg-[var(--bg-page)]"
            >
              新增
            </button>
          </div>
        </aside>

        {/* Editor */}
        <div className="flex flex-1 flex-col overflow-hidden">
          <textarea
            value={files[selected] ?? ""}
            onChange={(e) => onEdit(e.target.value)}
            spellCheck={false}
            className="flex-1 resize-none bg-[var(--bg-page)] p-4 font-mono text-[13px] leading-relaxed text-[var(--text-primary)] focus:outline-none"
            placeholder={
              selected === SKILL_MD
                ? "# SKILL.md 需 YAML frontmatter（name / description）開頭"
                : ""
            }
          />
        </div>

        {/* Version history */}
        <SkillVersionHistory
          key={historyKey}
          skillName={skillName}
          isAdmin={isAdmin}
          onView={(v) => void load(v)}
          onChanged={() => {
            setHistoryKey((k) => k + 1);
            void load();
          }}
        />
      </div>
    </div>
  );
}
