"use client";

import { use, useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ChevronLeft, Pencil, Trash2 } from "lucide-react";
import Sidebar from "@/components/layout/Sidebar";
import { useTranslations } from "@/components/i18n/LocaleProvider";
import { ApiError, api } from "@/lib/api";
import { formatRelative } from "@/lib/format";
import type { components } from "@/types/api.generated";

type CaseEntry = components["schemas"]["CaseEntry"];
type CaseEntryEnvelope = components["schemas"]["CaseEntryEnvelope"];
type EmbeddingStatus = CaseEntry["embedding_status"];

export default function CaseDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const router = useRouter();
  const tF = useTranslations("kb.cases.form");
  const tD = useTranslations("kb.cases.detail");
  const tC = useTranslations("kb.cases");

  const EMBEDDING_LABEL: Record<EmbeddingStatus, { text: string; bg: string; color: string }> = useMemo(
    () => ({
      processing: { text: tD("embedProcessing"), bg: "#FEF3C7", color: "#92400E" },
      ready: { text: tD("embedReady"), bg: "#D1FAE5", color: "#065F46" },
      failed: { text: tD("embedFailed"), bg: "#FEE2E2", color: "#991B1B" },
    }),
    [tD],
  );

  const [entry, setEntry] = useState<CaseEntry | null>(null);
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [deleting, setDeleting] = useState(false);

  const fetchCase = useCallback(async () => {
    setLoading(true);
    setNotFound(false);
    setError(null);
    try {
      const res = await api.get<CaseEntryEnvelope>(`/api/v1/knowledge-base/cases/${id}`);
      if (!res.data) {
        setNotFound(true);
      } else {
        setEntry(res.data);
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

  const onDelete = async () => {
    if (!entry) return;
    if (!window.confirm(tD("confirmDelete", { title: entry.title }))) return;
    setDeleting(true);
    setError(null);
    try {
      await api.delete(`/api/v1/knowledge-base/cases/${id}`);
      router.replace("/knowledge-base/cases");
    } catch (e) {
      setError(
        e instanceof ApiError
          ? `${e.errorCode} (${e.status})：${e.message}`
          : e instanceof Error
            ? e.message
            : String(e),
      );
      setDeleting(false);
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
            {tF("backToList")}
          </Link>
          <div className="flex items-start justify-between gap-4">
            <h1 className="text-2xl font-bold text-[var(--text-primary)]">
              {loading ? tD("loading") : entry?.title ?? tD("fallbackTitle")}
            </h1>
            {entry && (
              <div className="flex items-center gap-2">
                <Link
                  href={`/knowledge-base/cases/${id}/edit`}
                  className="flex h-9 items-center gap-1.5 rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] px-4 text-sm font-medium text-[var(--text-primary)] hover:border-[var(--primary)]"
                >
                  <Pencil className="h-4 w-4" />
                  {tD("edit")}
                </Link>
                <button
                  type="button"
                  onClick={onDelete}
                  disabled={deleting}
                  className="flex h-9 items-center gap-1.5 rounded-lg border border-red-200 bg-red-50 px-4 text-sm font-medium text-red-700 hover:border-red-400 disabled:opacity-50"
                >
                  <Trash2 className="h-4 w-4" />
                  {deleting ? tD("deleting") : tD("delete")}
                </button>
              </div>
            )}
          </div>
        </div>

        <div className="flex-1 overflow-auto px-8 py-6">
          {error && (
            <div className="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
              {error}
            </div>
          )}

          {notFound ? (
            <div className="flex h-60 flex-col items-center justify-center gap-2 rounded-lg border border-dashed border-[var(--border)] text-[var(--text-secondary)]">
              <p className="text-base">{tD("notFoundTitle")}</p>
              <p className="text-sm">{tD("notFoundDesc")}</p>
            </div>
          ) : entry ? (
            <div className="flex flex-col gap-6">
              <div className="flex flex-wrap gap-2">
                <span className="rounded bg-[#EFF6FF] px-[10px] py-1 text-xs font-medium text-[var(--primary)]">
                  {entry.brand}
                </span>
                {entry.model && (
                  <span className="rounded bg-[#EFF6FF] px-[10px] py-1 text-xs font-medium text-[var(--primary)]">
                    {entry.model}
                  </span>
                )}
                {entry.verified ? (
                  <span className="rounded bg-[#D1FAE5] px-[10px] py-1 text-xs font-medium text-[#065F46]">
                    {tC("verifiedCheck")}
                  </span>
                ) : (
                  <span className="rounded bg-[#F1F5F9] px-[10px] py-1 text-xs font-medium text-[var(--text-secondary)]">
                    {tC("unverified")}
                  </span>
                )}
                <span
                  className="rounded px-[10px] py-1 text-xs font-medium"
                  style={{
                    backgroundColor: EMBEDDING_LABEL[entry.embedding_status].bg,
                    color: EMBEDDING_LABEL[entry.embedding_status].color,
                  }}
                >
                  {EMBEDDING_LABEL[entry.embedding_status].text}
                </span>
                {entry.tags?.map((t) => (
                  <span
                    key={t}
                    className="rounded bg-[var(--bg-page)] px-[10px] py-1 text-xs font-medium text-[var(--text-secondary)]"
                  >
                    #{t}
                  </span>
                ))}
              </div>

              <section className="rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] p-5">
                <h2 className="mb-3 text-sm font-semibold text-[var(--text-secondary)]">
                  {tD("problemTitle")}
                </h2>
                <p className="whitespace-pre-wrap text-[15px] leading-relaxed text-[var(--text-primary)]">
                  {entry.problem_description}
                </p>
              </section>

              <section className="rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] p-5">
                <h2 className="mb-3 text-sm font-semibold text-[var(--text-secondary)]">
                  {tD("solutionTitle")}
                </h2>
                <p className="whitespace-pre-wrap text-[15px] leading-relaxed text-[var(--text-primary)]">
                  {entry.solution}
                </p>
              </section>

              <div className="flex flex-wrap items-center gap-x-6 gap-y-1 text-xs text-[var(--text-secondary)]">
                <span>{tD("createdAt", { time: new Date(entry.created_at).toLocaleString("zh-TW") })}</span>
                <span>{tD("updatedAt", { time: formatRelative(entry.updated_at) })}</span>
                <span className="font-mono text-[11px]">{tD("id", { id: entry.id })}</span>
              </div>
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}
