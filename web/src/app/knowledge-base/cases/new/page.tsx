"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ChevronLeft } from "lucide-react";
import Sidebar from "@/components/layout/Sidebar";
import { ApiError, api } from "@/lib/api";
import type { components } from "@/types/api.generated";

type CaseEntryEnvelope = components["schemas"]["CaseEntryEnvelope"];
type CaseEntryCreateRequest = components["schemas"]["CaseEntryCreateRequest"];

export default function NewCasePage() {
  const router = useRouter();

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
      setError("請填寫標題、品牌、問題描述、解決方案。");
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
      const res = await api.post<CaseEntryEnvelope>("/api/v1/knowledge-base/cases", body);
      if (!res.data) throw new Error("後端未回傳案例資料");
      router.replace(`/knowledge-base/cases/${res.data.id}`);
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
        <div className="flex flex-col gap-3 border-b border-[var(--border)] bg-[var(--bg-surface)] px-8 pt-5 pb-4">
          <Link
            href="/knowledge-base/cases"
            className="flex w-fit items-center gap-1 text-[13px] text-[var(--text-secondary)] hover:text-[var(--primary)]"
          >
            <ChevronLeft className="h-4 w-4" />
            取消
          </Link>
          <h1 className="text-2xl font-bold text-[var(--text-primary)]">新增案例</h1>
        </div>

        <div className="flex-1 overflow-auto px-8 py-6">
          <form onSubmit={onSubmit} className="flex max-w-3xl flex-col gap-5">
            {error && (
              <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                {error}
              </div>
            )}

            <Field label="標題" required>
              <input
                type="text"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                maxLength={200}
                placeholder="例：AI-99 門板未對齊導致無法上鎖"
                className={inputCls}
              />
            </Field>

            <div className="grid grid-cols-2 gap-5">
              <Field label="品牌" required>
                <input
                  type="text"
                  value={brand}
                  onChange={(e) => setBrand(e.target.value)}
                  placeholder="Chatlock / Dormakaba / KESO ..."
                  className={inputCls}
                />
              </Field>
              <Field label="型號">
                <input
                  type="text"
                  value={model}
                  onChange={(e) => setModel(e.target.value)}
                  placeholder="AI-99"
                  className={inputCls}
                />
              </Field>
            </div>

            <Field label="標籤（以逗號分隔）">
              <input
                type="text"
                value={tagsInput}
                onChange={(e) => setTagsInput(e.target.value)}
                placeholder="安裝, 門板, 機械"
                className={inputCls}
              />
            </Field>

            <Field label="問題描述" required>
              <textarea
                value={problemDescription}
                onChange={(e) => setProblemDescription(e.target.value)}
                rows={5}
                placeholder="顧客回報的具體現象..."
                className={textareaCls}
              />
            </Field>

            <Field label="解決方案" required>
              <textarea
                value={solution}
                onChange={(e) => setSolution(e.target.value)}
                rows={8}
                placeholder="處理步驟與最終結果..."
                className={textareaCls}
              />
            </Field>

            <div className="flex items-center gap-3">
              <button
                type="submit"
                disabled={submitting}
                className="flex h-10 items-center rounded-lg bg-[var(--primary)] px-6 text-sm font-semibold text-white hover:bg-[var(--primary-hover)] disabled:opacity-50"
              >
                {submitting ? "建立中…" : "建立案例"}
              </button>
              <Link
                href="/knowledge-base/cases"
                className="flex h-10 items-center rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] px-6 text-sm font-medium text-[var(--text-primary)] hover:border-[var(--primary)]"
              >
                取消
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
