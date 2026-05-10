"use client";

import { use, useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ChevronLeft } from "lucide-react";
import Sidebar from "@/components/layout/Sidebar";
import { useTranslations } from "@/components/i18n/LocaleProvider";
import { ApiError, api } from "@/lib/api";
import type { components } from "@/types/api.generated";

type CaseEntry = components["schemas"]["CaseEntry"];
type CaseEntryEnvelope = components["schemas"]["CaseEntryEnvelope"];
type CaseEntryUpdateRequest = components["schemas"]["CaseEntryUpdateRequest"];

export default function EditCasePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const router = useRouter();
  const tF = useTranslations("kb.cases.form");
  const tD = useTranslations("kb.cases.detail");

  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [notFound, setNotFound] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [title, setTitle] = useState("");
  const [brand, setBrand] = useState("");
  const [model, setModel] = useState("");
  const [tagsInput, setTagsInput] = useState("");
  const [problemDescription, setProblemDescription] = useState("");
  const [solution, setSolution] = useState("");
  const [verified, setVerified] = useState(false);

  const fillForm = (entry: CaseEntry) => {
    setTitle(entry.title);
    setBrand(entry.brand);
    setModel(entry.model ?? "");
    setTagsInput(entry.tags?.join(", ") ?? "");
    setProblemDescription(entry.problem_description);
    setSolution(entry.solution);
    setVerified(entry.verified);
  };

  const fetchCase = useCallback(async () => {
    setLoading(true);
    setError(null);
    setNotFound(false);
    try {
      const res = await api.get<CaseEntryEnvelope>(`/api/v1/knowledge-base/cases/${id}`);
      if (!res.data) {
        setNotFound(true);
      } else {
        fillForm(res.data);
      }
    } catch (e) {
      if (e instanceof ApiError && e.status === 404) {
        setNotFound(true);
      } else {
        setError(
          e instanceof ApiError
            ? `${e.errorCode} (${e.status})：${e.message}`
            : e instanceof Error
              ? e.message
              : String(e),
        );
      }
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    fetchCase();
  }, [fetchCase]);

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

    const body: CaseEntryUpdateRequest = {
      title: title.trim(),
      brand: brand.trim(),
      model: model.trim() || undefined,
      tags,
      problem_description: problemDescription.trim(),
      solution: solution.trim(),
      verified,
    };

    setSubmitting(true);
    try {
      await api.put<CaseEntryEnvelope>(`/api/v1/knowledge-base/cases/${id}`, body);
      router.replace(`/knowledge-base/cases/${id}`);
    } catch (e) {
      setError(
        e instanceof ApiError
          ? `${e.errorCode} (${e.status})：${e.message}`
          : e instanceof Error
            ? e.message
            : String(e),
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
            href={`/knowledge-base/cases/${id}`}
            className="flex w-fit items-center gap-1 text-[13px] text-[var(--text-secondary)] hover:text-[var(--primary)]"
          >
            <ChevronLeft className="h-4 w-4" />
            {tF("backToDetail")}
          </Link>
          <h1 className="text-2xl font-bold text-[var(--text-primary)]">{tF("editTitle")}</h1>
        </div>

        <div className="flex-1 overflow-auto px-8 py-6">
          {loading ? (
            <div className="text-sm text-[var(--text-secondary)]">{tD("loading")}</div>
          ) : notFound ? (
            <div className="flex h-60 flex-col items-center justify-center gap-2 rounded-lg border border-dashed border-[var(--border)] text-[var(--text-secondary)]">
              <p className="text-base">{tD("notFoundTitle")}</p>
              <p className="text-sm">{tD("notFoundDescShort")}</p>
            </div>
          ) : (
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
                  className={inputCls}
                />
              </Field>

              <div className="grid grid-cols-2 gap-5">
                <Field label={tF("brand")} required>
                  <input
                    type="text"
                    value={brand}
                    onChange={(e) => setBrand(e.target.value)}
                    className={inputCls}
                  />
                </Field>
                <Field label={tF("model")}>
                  <input
                    type="text"
                    value={model}
                    onChange={(e) => setModel(e.target.value)}
                    className={inputCls}
                  />
                </Field>
              </div>

              <Field label={tF("tags")}>
                <input
                  type="text"
                  value={tagsInput}
                  onChange={(e) => setTagsInput(e.target.value)}
                  className={inputCls}
                />
              </Field>

              <Field label={tF("problem")} required>
                <textarea
                  value={problemDescription}
                  onChange={(e) => setProblemDescription(e.target.value)}
                  rows={5}
                  className={textareaCls}
                />
              </Field>

              <Field label={tF("solution")} required>
                <textarea
                  value={solution}
                  onChange={(e) => setSolution(e.target.value)}
                  rows={8}
                  className={textareaCls}
                />
              </Field>

              <label className="flex items-center gap-2 text-sm text-[var(--text-primary)]">
                <input
                  type="checkbox"
                  checked={verified}
                  onChange={(e) => setVerified(e.target.checked)}
                  className="h-4 w-4 rounded border-[var(--border)]"
                />
                {tF("verifiedCheckbox")}
              </label>

              <div className="flex items-center gap-3">
                <button
                  type="submit"
                  disabled={submitting}
                  className="flex h-10 items-center rounded-lg bg-[var(--primary)] px-6 text-sm font-semibold text-white hover:bg-[var(--primary-hover)] disabled:opacity-50"
                >
                  {submitting ? tF("saving") : tF("saveSubmit")}
                </button>
                <Link
                  href={`/knowledge-base/cases/${id}`}
                  className="flex h-10 items-center rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] px-6 text-sm font-medium text-[var(--text-primary)] hover:border-[var(--primary)]"
                >
                  {tF("cancel")}
                </Link>
              </div>
            </form>
          )}
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
