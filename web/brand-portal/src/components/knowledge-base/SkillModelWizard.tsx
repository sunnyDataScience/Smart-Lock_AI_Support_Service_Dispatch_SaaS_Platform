"use client";

// #10 新增精靈(業主拍板 2026-07-18):讓不懂 markdown 的品牌小編用表單新增
// 「型號知識」——填品牌/型號/描述+三區塊內容,前端組標準 md(frontmatter+H1+章節)
// 落 references/{品牌}/{型號}.md,走既有 draft→admin 發佈流程。
// 可攜性紅線:產出即標準 Agent Skills 格式,無框架自訂欄位。

import { useState } from "react";
import {
  Modal,
  ModalContent,
  ModalDescription,
  ModalFooter,
  ModalHeader,
  ModalTitle,
} from "@/components/ui/Modal";

const NEW_BRAND = "__new__";
// 與後端 skill_service._REL_PATH_SEG_RE 黑名單一致:檔名不可含控制字元與
// <>:"|?*,另 / 與 \ 是路徑分隔不可入名。空格/連字號/中文皆合法保留
// (AS-920、藍寶堅尼3D人臉辨識 均為既有實檔命名慣例)
const BAD_CHARS_RE = /[<>:"|?*/\\\u0000-\u001f\u007f]/g;

interface Props {
  open: boolean;
  onClose: () => void;
  /** 既有品牌目錄名(建樹層算好傳入),供下拉選 */
  brands: string[];
  /** 既有全部檔案路徑,擋重複 */
  existingPaths: string[];
  /** 組好 (path, content) 交回編輯器:加入檔案樹+選中+立即存草稿 */
  onSubmit: (path: string, content: string) => void;
}

interface SectionDef {
  key: "setup" | "faq" | "troubleshoot";
  label: string;
  heading: string;
  placeholder: string;
}

const SECTIONS: SectionDef[] = [
  {
    key: "setup",
    label: "設定步驟",
    heading: "## 設定步驟",
    placeholder: "例:1. 進入設定模式…\n2. 依語音指示註冊指紋…",
  },
  {
    key: "faq",
    label: "常見問題",
    heading: "## 常見問題",
    placeholder: "例:Q:電池沒電怎麼開門?\nA:以 Type-C 行動電源接觸應急供電孔…",
  },
  {
    key: "troubleshoot",
    label: "故障排除",
    heading: "## 故障排除",
    placeholder: "例:按鍵無反應 → 先確認電池極性;仍無反應則…",
  },
];

function sanitizeName(raw: string): string {
  return raw.replace(BAD_CHARS_RE, "").trim();
}

export default function SkillModelWizard({
  open,
  onClose,
  brands,
  existingPaths,
  onSubmit,
}: Props) {
  const [brandSel, setBrandSel] = useState<string>(brands[0] ?? NEW_BRAND);
  const [newBrand, setNewBrand] = useState("");
  const [model, setModel] = useState("");
  const [desc, setDesc] = useState("");
  const [sections, setSections] = useState<Record<string, string>>({});
  const [touched, setTouched] = useState(false);

  const brand = sanitizeName(brandSel === NEW_BRAND ? newBrand : brandSel);
  const modelName = sanitizeName(model);
  const path = brand && modelName ? `references/${brand}/${modelName}.md` : "";
  const duplicate = !!path && existingPaths.includes(path);
  const hasContent = SECTIONS.some((s) => (sections[s.key] ?? "").trim());
  const valid = !!brand && !!modelName && !!desc.trim() && hasContent && !duplicate;

  function reset() {
    setBrandSel(brands[0] ?? NEW_BRAND);
    setNewBrand("");
    setModel("");
    setDesc("");
    setSections({});
    setTouched(false);
  }

  function buildMarkdown(): string {
    const parts = [
      "---",
      `brand: ${brand}`,
      `model: ${modelName}`,
      `description: ${desc.trim()}`,
      "---",
      "",
      `# ${brand} ${modelName}`,
      "",
    ];
    for (const s of SECTIONS) {
      const body = (sections[s.key] ?? "").trim();
      if (!body) continue;
      parts.push(s.heading, "", body, "");
    }
    return parts.join("\n");
  }

  function submit() {
    if (!valid) {
      setTouched(true);
      return;
    }
    onSubmit(path, buildMarkdown());
    reset();
  }

  const inputCls =
    "w-full rounded-lg border border-[var(--border)] bg-[var(--bg-page)] px-3 py-2 text-sm text-[var(--text-primary)] placeholder:text-[var(--text-disabled)] focus:border-[var(--border-focus)] focus:outline-none focus:ring-1 focus:ring-[var(--border-focus)]";

  return (
    <Modal
      open={open}
      onOpenChange={(o) => {
        if (!o) {
          reset();
          onClose();
        }
      }}
    >
      <ModalContent size="md">
        <ModalHeader>
          <ModalTitle>新增型號知識</ModalTitle>
          <ModalDescription>
            用表單填寫即可,不需要會 markdown。存為草稿後由管理員發佈,約 60 秒生效。
          </ModalDescription>
        </ModalHeader>

        <div className="flex flex-col gap-3.5 px-6 py-4">
          <div className="grid grid-cols-2 gap-3">
            <label className="flex flex-col gap-1">
              <span className="text-[13px] font-medium text-[var(--text-primary)]">
                品牌<span className="ml-0.5 text-[var(--error)]">*</span>
              </span>
              <select
                value={brandSel}
                onChange={(e) => setBrandSel(e.target.value)}
                className={inputCls}
              >
                {brands.map((b) => (
                  <option key={b} value={b}>
                    {b}
                  </option>
                ))}
                <option value={NEW_BRAND}>＋ 新品牌…</option>
              </select>
            </label>
            <label className="flex flex-col gap-1">
              <span className="text-[13px] font-medium text-[var(--text-primary)]">
                型號<span className="ml-0.5 text-[var(--error)]">*</span>
              </span>
              <input
                value={model}
                onChange={(e) => setModel(e.target.value)}
                placeholder="例:AS920"
                className={inputCls}
              />
            </label>
          </div>

          {brandSel === NEW_BRAND && (
            <label className="flex flex-col gap-1">
              <span className="text-[13px] font-medium text-[var(--text-primary)]">
                新品牌名稱<span className="ml-0.5 text-[var(--error)]">*</span>
              </span>
              <input
                value={newBrand}
                onChange={(e) => setNewBrand(e.target.value)}
                placeholder="例:Yale"
                className={inputCls}
              />
            </label>
          )}

          <label className="flex flex-col gap-1">
            <span className="text-[13px] font-medium text-[var(--text-primary)]">
              一句話描述<span className="ml-0.5 text-[var(--error)]">*</span>
            </span>
            <input
              value={desc}
              onChange={(e) => setDesc(e.target.value)}
              placeholder="例:指紋+卡片電子鎖,支援 App 遠端開門"
              className={inputCls}
            />
          </label>

          <div className="mt-1 text-[12px] font-medium text-[var(--text-tertiary)]">
            內容(至少填一項)
          </div>
          {SECTIONS.map((s) => (
            <label key={s.key} className="flex flex-col gap-1">
              <span className="text-[13px] font-medium text-[var(--text-primary)]">
                {s.label}
              </span>
              <textarea
                value={sections[s.key] ?? ""}
                onChange={(e) =>
                  setSections((prev) => ({ ...prev, [s.key]: e.target.value }))
                }
                placeholder={s.placeholder}
                rows={3}
                className={`${inputCls} resize-y font-normal`}
              />
            </label>
          ))}

          {touched && !valid && (
            <p className="text-[12px] text-[var(--error)]" role="alert">
              {duplicate
                ? `「${brand} / ${modelName}」已存在,請改用左欄開啟編輯`
                : "品牌、型號、描述必填,且內容至少填一項"}
            </p>
          )}
          {duplicate && !touched && (
            <p className="text-[12px] text-[var(--warning)]">
              「{brand} / {modelName}」已存在,送出前請先確認
            </p>
          )}
        </div>

        <ModalFooter>
          <button
            type="button"
            onClick={() => {
              reset();
              onClose();
            }}
            className="rounded-lg border border-[var(--border)] px-3.5 py-1.5 text-sm text-[var(--text-secondary)] transition hover:bg-[var(--bg-page)]"
          >
            取消
          </button>
          <button
            type="button"
            onClick={submit}
            className="rounded-lg bg-[var(--primary)] px-3.5 py-1.5 text-sm font-semibold text-white transition hover:bg-[var(--primary-hover)]"
          >
            存為草稿
          </button>
        </ModalFooter>
      </ModalContent>
    </Modal>
  );
}
