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
import { mdTitle } from "@/lib/skill-labels";

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
  const [forked, setForked] = useState(false); // 從非草稿版本明確「建立草稿」後可編輯
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [historyKey, setHistoryKey] = useState(0); // 觸發歷史面板重載
  const [newPath, setNewPath] = useState("");

  // 只有「草稿」或明確 fork 才可編輯——避免檢視舊版本時誤存覆蓋現有草稿（review finding 7）
  const editable = viewingStatus === "draft" || forked;

  const applyDetail = useCallback((d: SkillDetail) => {
    setFiles(d.files ?? {});
    setViewingVersion(d.version);
    setViewingStatus(d.status);
    setDraftVersion(d.status === "draft" ? d.version : null);
    setDirty(false);
    setForked(false);
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
    if (!editable) return;
    setFiles((prev) => ({ ...prev, [selected]: value }));
    setDirty(true);
  };

  // 從檢視中的（發佈中）版本 fork 出可編輯草稿。此時 latest=published＝無現存草稿，
  // 存檔會 INSERT 新草稿，不會覆蓋他人草稿（若有草稿，mount 會載入草稿而非走此路徑）。
  const forkToDraft = () => {
    setForked(true);
    setDirty(true);
  };

  const addFile = () => {
    if (!editable) return;
    let path = newPath.trim();
    if (!path) return;
    // UI 只收短檔名（新增列標題已標明「參考文件」）；自動補 references/ 前綴與 .md 副檔名
    if (!path.startsWith("references/")) path = `references/${path}`;
    if (!path.endsWith(".md")) path = `${path}.md`;
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
    if (path === SKILL_MD || !editable) return;
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
    // 無可發佈內容（檢視發佈中版本、無編輯、無草稿）→ 不製造多餘版本＋agent 重同步（finding 8）
    if (!dirty && draftVersion == null) {
      toast({ title: "目前無草稿可發佈（此為發佈中版本）", variant: "warning" });
      return;
    }
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
          {!editable && <span className="text-[var(--text-tertiary)]">· 唯讀</span>}
          {dirty && <span className="text-[var(--warning)]">· 未儲存變更</span>}
        </div>
        <div className="flex items-center gap-2">
          {!editable && viewingStatus === "published" && (
            <button
              type="button"
              onClick={forkToDraft}
              className="rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] px-4 py-2 text-sm font-medium text-[var(--text-primary)] transition-colors hover:bg-[var(--bg-page)]"
            >
              以此版本建立草稿
            </button>
          )}
          {editable && (
            <button
              type="button"
              onClick={handleSave}
              disabled={busy || !dirty}
              className="rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] px-4 py-2 text-sm font-medium text-[var(--text-primary)] transition-colors hover:bg-[var(--bg-page)] disabled:cursor-not-allowed disabled:opacity-50"
            >
              存草稿
            </button>
          )}
          {isAdmin && (
            <button
              type="button"
              onClick={handlePublish}
              disabled={busy || (!dirty && draftVersion == null)}
              className="rounded-lg bg-[var(--primary)] px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-[var(--primary-hover)] disabled:cursor-not-allowed disabled:opacity-50"
            >
              發佈
            </button>
          )}
        </div>
      </div>

      <div className="flex flex-1 overflow-hidden">
        {/* File list — 主檔 / 參考文件分組（顯示層短檔名；資料層 path 不變） */}
        <aside className="flex w-52 shrink-0 flex-col border-r border-[var(--border)] bg-[var(--bg-surface)] md:w-60">
          <div className="flex-1 overflow-auto py-2">
            <div className="px-3 pb-1 pt-1 text-[11px] font-semibold uppercase tracking-wider text-[var(--text-tertiary)]">
              主檔
            </div>
            {fileList.filter((p) => !isReferenceFile(p)).map((path) => (
              <FileRow
                key={path}
                path={path}
                label={path}
                selected={selected === path}
                onSelect={() => setSelected(path)}
              />
            ))}
            <div className="px-3 pb-1 pt-4 text-[11px] font-semibold uppercase tracking-wider text-[var(--text-tertiary)]">
              參考文件（references/）
            </div>
            {fileList.filter(isReferenceFile).length === 0 && (
              <div className="px-3 py-1.5 text-[12px] text-[var(--text-disabled)]">
                尚無參考文件
              </div>
            )}
            {fileList.filter(isReferenceFile).map((path) => (
              <FileRow
                key={path}
                path={path}
                // #10 口語化:顯示 md 首個標題(如「預約安裝流程」),抽不到退檔名
                label={mdTitle(files[path], path.replace(/^references\//, ""))}
                selected={selected === path}
                onSelect={() => setSelected(path)}
                onRemove={() => removeFile(path)}
              />
            ))}
          </div>
          <div className="border-t border-[var(--border)] p-2.5">
            <div className="mb-1.5 text-[11px] font-medium text-[var(--text-tertiary)]">
              新增參考文件
            </div>
            <div className="flex gap-1.5">
              <input
                value={newPath}
                onChange={(e) => setNewPath(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && addFile()}
                placeholder="檔名.md"
                className="min-w-0 flex-1 rounded-md border border-[var(--border)] bg-[var(--bg-page)] px-2 py-1.5 text-xs text-[var(--text-primary)] placeholder:text-[var(--text-disabled)] focus:border-[var(--border-focus)] focus:outline-none focus:ring-1 focus:ring-[var(--border-focus)]"
              />
              <button
                type="button"
                onClick={addFile}
                className="shrink-0 rounded-md bg-[var(--primary)] px-2.5 py-1.5 text-xs font-medium text-white transition-colors hover:bg-[var(--primary-hover)]"
              >
                新增
              </button>
            </div>
          </div>
        </aside>

        {/* Editor */}
        <div className="flex flex-1 flex-col overflow-hidden">
          <textarea
            value={files[selected] ?? ""}
            onChange={(e) => onEdit(e.target.value)}
            readOnly={!editable}
            spellCheck={false}
            className="flex-1 resize-none bg-[var(--bg-page)] p-4 font-mono text-[13px] leading-relaxed text-[var(--text-primary)] focus:outline-none read-only:opacity-70"
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

/** 檔案列表列：檔案 icon + 短檔名 + 選中左指示條 + hover 刪除（僅參考文件） */
function FileRow({
  path,
  label,
  selected,
  onSelect,
  onRemove,
}: {
  path: string;
  label: string;
  selected: boolean;
  onSelect: () => void;
  onRemove?: () => void;
}) {
  return (
    <div
      className={`group relative flex items-center gap-2 py-1.5 pl-3 pr-2 text-[13px] transition-colors ${
        selected
          ? "bg-[var(--primary-light)]/50 text-[var(--primary)]"
          : "text-[var(--text-secondary)] hover:bg-[var(--bg-page)]"
      }`}
    >
      {selected && (
        <span className="absolute inset-y-1 left-0 w-[3px] rounded-r bg-[var(--primary)]" aria-hidden="true" />
      )}
      <svg
        width="14"
        height="14"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
        className="shrink-0 opacity-70"
        aria-hidden="true"
      >
        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
        <path d="M14 2v6h6" />
      </svg>
      <button
        type="button"
        onClick={onSelect}
        className={`flex-1 truncate text-left font-mono ${selected ? "font-semibold" : ""}`}
        title={path}
      >
        {label}
      </button>
      {onRemove && (
        <button
          type="button"
          onClick={onRemove}
          className="hidden shrink-0 rounded px-1 text-[var(--text-tertiary)] hover:bg-[var(--error)]/10 hover:text-[var(--error)] group-hover:block"
          aria-label={`刪除 ${path}`}
        >
          ×
        </button>
      )}
    </div>
  );
}
