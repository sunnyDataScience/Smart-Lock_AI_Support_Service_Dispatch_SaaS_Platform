"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ChevronLeft } from "lucide-react";
import Sidebar from "@shared/components/layout/Sidebar";
import { useTranslations } from "@shared/components/i18n/LocaleProvider";
import { api, tenantPath } from "@shared/lib/api";
import { friendlyError } from "@shared/lib/apiError";
import type { KBDocument } from "@shared/lib/kb-adapter";
import type { components } from "@shared/types/api.generated";

type CaseEntryEnvelope = components["schemas"]["CaseEntryEnvelope"];
type CaseEntryCreateRequest = components["schemas"]["CaseEntryCreateRequest"];

export default function NewCasePage() {
  const router = useRouter();
  const tF = useTranslations("kb.cases.form");

  const [title, setTitle] = useState("");
  const [brand, setBrand] = useState("");
  const [model, setModel] = useState("");
  const [tagsInput, setTagsInput] = useState("");
  const [problemDescription, setProblemDescription] = useState("");
  const [solution, setSolution] = useState("");

  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (submitting) return;
    setError(null);

    if (!title.trim() || !brand.trim() || !problemDescription.trim() || !solution.trim()) {
      setError(tF("validateRequired"));
      return;
    }

    const tags = tagsInput
      .split(",")
      .map((t) => t.trim())
      .filter(Boolean);

    const body: CaseEntryCreateRequest = {
      title: title.trim(),
      brand: brand.trim(),
      problem_description: problemDescription.trim(),
      solution: solution.trim(),
      ...(model.trim() ? { model: model.trim() } : {}),
      ...(tags.length > 0 ? { tags } : {}),
    };

    setSubmitting(true);
    try {
      // CR-0005 step 3/3：v2 POST 走 kb_v2.py:ingestKBDocument（doc_type=case）
      // 返回 KBDocument（meta-wrap）；用 doc.id 導頁
      const doc = await api.post<KBDocument>(
        tenantPath("/kb/documents"),
        { ...body, doc_type: "case" },
      );
      if (!doc?.id) throw new Error(tF("errorNoData"));
      router.replace(`/knowledge-base/cases/${doc.id}`);
    } catch (e) {
      setError(
        friendlyError(e),
      );
      setSubmitting(false);
    }
  };

  return (
    <div className="flex h-full bg-[var(--bg-page)]">
      <Sidebar />

      <div className="flex flex-1 flex-col overflow-hidden">
        <div className="flex flex-col gap-3 border-b border-[var(--border)] bg-[var(--bg-surface)] pl-14 pr-4 md:px-8 pt-5 pb-4">
          <Link
            href="/knowledge-base/cases"
            className="flex w-fit items-center gap-1 text-[13px] text-[var(--text-secondary)] hover:text-[var(--primary)]"
          >
            <ChevronLeft className="h-4 w-4" />
            {tF("back")}
          </Link>
          <h1 className="text-2xl font-bold text-[var(--text-primary)]">{tF("newTitle")}</h1>
        </div>

        <div className="flex-1 overflow-auto px-8 py-6">
          <form onSubmit={onSubmit} className="flex max-w-3xl flex-col gap-5">
            {error && (
              <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                {error}
              </div>
            )}

            <Field label={tF("title")} required>
              <input
                type="text"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                maxLength={200}
                placeholder={tF("titlePlaceholder")}
                className={inputCls}
              />
            </Field>

            <div className="grid grid-cols-2 gap-5">
              <Field label={tF("brand")} required>
                <input
                  type="text"
                  value={brand}
                  onChange={(e) => setBrand(e.target.value)}
                  placeholder={tF("brandPlaceholder")}
                  className={inputCls}
                />
              </Field>
              <Field label={tF("model")}>
                <input
                  type="text"
                  value={model}
                  onChange={(e) => setModel(e.target.value)}
                  placeholder={tF("modelPlaceholder")}
                  className={inputCls}
                />
              </Field>
            </div>

            <Field label={tF("tags")}>
              <input
                type="text"
                value={tagsInput}
                onChange={(e) => setTagsInput(e.target.value)}
                placeholder={tF("tagsPlaceholder")}
                className={inputCls}
              />
            </Field>

            <Field label={tF("problem")} required>
              <textarea
                value={problemDescription}
                onChange={(e) => setProblemDescription(e.target.value)}
                rows={5}
                placeholder={tF("problemPlaceholder")}
                className={textareaCls}
              />
            </Field>

            <Field label={tF("solution")} required>
              <textarea
                value={solution}
                onChange={(e) => setSolution(e.target.value)}
                rows={8}
                placeholder={tF("solutionPlaceholder")}
                className={textareaCls}
              />
            </Field>

            <div className="flex items-center gap-3">
              <button
                type="submit"
                disabled={submitting}
                className="flex h-10 items-center rounded-lg bg-[var(--primary)] px-6 text-sm font-semibold text-white hover:bg-[var(--primary-hover)] disabled:opacity-50"
              >
                {submitting ? tF("creating") : tF("createSubmit")}
              </button>
              <Link
                href="/knowledge-base/cases"
                className="flex h-10 items-center rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] px-6 text-sm font-medium text-[var(--text-primary)] hover:border-[var(--primary)]"
              >
                {tF("cancel")}
              </Link>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}

const inputCls =
  "h-10 w-full rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] px-3 text-sm text-[var(--text-primary)] outline-none transition focus:border-[var(--primary)]";

const textareaCls =
  "w-full rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] px-3 py-2 text-sm leading-relaxed text-[var(--text-primary)] outline-none transition focus:border-[var(--primary)]";

function Field({
  label,
  required,
  children,
}: {
  label: string;
  required?: boolean;
  children: React.ReactNode;
}) {
  return (
    <label className="flex flex-col gap-1.5">
      <span className="text-sm font-medium text-[var(--text-primary)]">
        {label}
        {required && <span className="ml-1 text-red-500">*</span>}
      </span>
      {children}
    </label>
  );
}
