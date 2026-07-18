"use client";

import { useEffect, useState } from "react";
import { Save, RefreshCw } from "lucide-react";
import { api } from "@/lib/api";
import { friendlyError } from "@/lib/apiError";
import { useLocale, useTranslations } from "@/components/i18n/LocaleProvider";
import type { components } from "@/types/api.generated";

type SystemConfig = components["schemas"]["SystemConfig"];

const DEFAULT_CONFIG: SystemConfig = {
  rag: { similarity_threshold: 0.85, max_results: 3, chunk_size: 800, chunk_overlap: 100 },
  llm: { model: "vertex_ai/gemini-2.5-pro", temperature: 0.2, max_tokens: 1024, system_prompt_version: "v1.0" },
  resolution: { faq_confidence_threshold: 0.7, rag_confidence_threshold: 0.6, auto_escalation_enabled: true },
  line_bot: { greeting_message_enabled: true, max_conversation_turns: 30 },
};

type Section = "rag" | "llm" | "resolution" | "line_bot";

function NumberField({
  label, value, onChange, min, max, step, unit,
}: {
  label: string; value: number | undefined; onChange: (v: number) => void;
  min?: number; max?: number; step?: number; unit?: string;
}) {
  return (
    <label className="flex flex-1 flex-col gap-[6px]">
      <span className="text-[13px] font-semibold text-[var(--text-primary)]">
        {label}
        {unit && <span className="ml-1 font-normal text-[var(--text-secondary)]">({unit})</span>}
      </span>
      <input
        type="number"
        value={value ?? ""}
        min={min}
        max={max}
        step={step ?? 1}
        onChange={(e) => onChange(parseFloat(e.target.value))}
        className="h-10 rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] px-3 text-sm text-[var(--text-primary)] outline-none focus:border-[var(--primary)]"
      />
    </label>
  );
}

function TextField({
  label, value, onChange,
}: {
  label: string; value: string | undefined; onChange: (v: string) => void;
}) {
  return (
    <label className="flex flex-1 flex-col gap-[6px]">
      <span className="text-[13px] font-semibold text-[var(--text-primary)]">{label}</span>
      <input
        type="text"
        value={value ?? ""}
        onChange={(e) => onChange(e.target.value)}
        className="h-10 rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] px-3 font-['IBM_Plex_Mono'] text-[13px] text-[var(--text-primary)] outline-none focus:border-[var(--primary)]"
      />
    </label>
  );
}

function ToggleField({
  label, value, onChange,
}: {
  label: string; value: boolean | undefined; onChange: (v: boolean) => void;
}) {
  return (
    <label className="flex flex-1 cursor-pointer items-center justify-between rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] px-4 py-3">
      <span className="text-[13px] font-semibold text-[var(--text-primary)]">{label}</span>
      <button
        type="button"
        onClick={() => onChange(!value)}
        className={`relative h-6 w-11 rounded-full transition-colors ${
          value ? "bg-[var(--primary)]" : "bg-[#CBD5E1]"
        }`}
      >
        <span
          className={`absolute top-[2px] h-5 w-5 rounded-full bg-white shadow transition-all ${
            value ? "left-[22px]" : "left-[2px]"
          }`}
        />
      </button>
    </label>
  );
}

function SectionCard({
  title, description, children,
}: {
  title: string; description: string; children: React.ReactNode;
}) {
  return (
    <div className="flex flex-col gap-4 rounded-lg border border-[var(--border)] bg-[#F8FAFC] p-5">
      <div className="flex flex-col gap-1">
        <span className="text-base font-semibold text-[var(--text-primary)]">{title}</span>
        <span className="text-[12px] text-[var(--text-secondary)]">{description}</span>
      </div>
      <div className="flex flex-col gap-4">{children}</div>
    </div>
  );
}

export default function SystemConfigForm() {
  const t = useTranslations("components.settings.systemConfigForm");
  const tSec = useTranslations("components.settings.systemConfigForm.sections");
  const { locale } = useLocale();
  const [config, setConfig] = useState<SystemConfig>(DEFAULT_CONFIG);
  const [original, setOriginal] = useState<SystemConfig>(DEFAULT_CONFIG);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [savedAt, setSavedAt] = useState<Date | null>(null);

  const fetchConfig = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.get<SystemConfig>("/api/v1/config");
      setConfig(res);
      setOriginal(res);
    } catch (e) {
      setError(
        friendlyError(e),
      );
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchConfig();
  }, []);

  const updateSection = <S extends Section>(
    section: S,
    patch: Partial<NonNullable<SystemConfig[S]>>,
  ) => {
    setConfig((prev) => ({
      ...prev,
      [section]: { ...(prev[section] ?? {}), ...patch },
    }));
  };

  const dirty = JSON.stringify(config) !== JSON.stringify(original);

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    try {
      const res = await api.patch<SystemConfig>("/api/v1/config", config);
      setConfig(res);
      setOriginal(res);
      setSavedAt(new Date());
    } catch (e) {
      setError(
        friendlyError(e),
      );
    } finally {
      setSaving(false);
    }
  };

  const handleReset = () => {
    setConfig(original);
    setError(null);
  };

  return (
    <div className="flex flex-1 flex-col gap-6 overflow-auto rounded-xl border border-[var(--border)] bg-[var(--bg-surface)] p-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span className="text-xl font-bold text-[var(--text-primary)]">{t("title")}</span>
          <button
            onClick={fetchConfig}
            disabled={loading || saving}
            className="flex h-8 w-8 items-center justify-center rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] hover:bg-[var(--bg-page)] disabled:cursor-not-allowed disabled:opacity-50"
            title={t("refresh")}
          >
            <RefreshCw
              className={`h-[14px] w-[14px] text-[var(--text-secondary)] ${loading ? "animate-spin" : ""}`}
            />
          </button>
          <span
            className="flex items-center gap-[6px] rounded-full px-3 py-1 text-xs font-medium"
            style={{
              backgroundColor: error ? "#FEE2E2" : "#DCFCE7",
              color: error ? "#B91C1C" : "#15803D",
            }}
          >
            <span
              className="h-[6px] w-[6px] rounded-full"
              style={{ backgroundColor: error ? "#DC2626" : "#22C55E" }}
            />
            {error ? t("connection.fail") : t("connection.ok")}
          </span>
        </div>
        <span className="text-[13px] text-[var(--text-secondary)]">
          {savedAt
            ? t("savedAt", { time: savedAt.toLocaleTimeString(locale, { hour12: false }) })
            : t("subtitle")}
        </span>
      </div>

      <div className="h-px w-full bg-[var(--border)]" />

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      <SectionCard title={tSec("rag.title")} description={tSec("rag.desc")}>
        <div className="flex gap-4">
          <NumberField
            label={tSec("rag.similarity")}
            value={config.rag?.similarity_threshold ?? undefined}
            onChange={(v) => updateSection("rag", { similarity_threshold: v })}
            min={0} max={1} step={0.01}
          />
          <NumberField
            label={tSec("rag.maxResults")}
            value={config.rag?.max_results ?? undefined}
            onChange={(v) => updateSection("rag", { max_results: Math.round(v) })}
            min={1} max={20}
          />
        </div>
        <div className="flex gap-4">
          <NumberField
            label={tSec("rag.chunkSize")}
            value={config.rag?.chunk_size ?? undefined}
            onChange={(v) => updateSection("rag", { chunk_size: Math.round(v) })}
            min={100} max={4000} unit={tSec("rag.unitChars")}
          />
          <NumberField
            label={tSec("rag.chunkOverlap")}
            value={config.rag?.chunk_overlap ?? undefined}
            onChange={(v) => updateSection("rag", { chunk_overlap: Math.round(v) })}
            min={0} max={500} unit={tSec("rag.unitChars")}
          />
        </div>
      </SectionCard>

      <SectionCard title={tSec("llm.title")} description={tSec("llm.desc")}>
        <div className="flex gap-4">
          <TextField
            label={tSec("llm.model")}
            value={config.llm?.model ?? undefined}
            onChange={(v) => updateSection("llm", { model: v })}
          />
          <TextField
            label={tSec("llm.promptVersion")}
            value={config.llm?.system_prompt_version ?? undefined}
            onChange={(v) => updateSection("llm", { system_prompt_version: v })}
          />
        </div>
        <div className="flex gap-4">
          <NumberField
            label={tSec("llm.temperature")}
            value={config.llm?.temperature ?? undefined}
            onChange={(v) => updateSection("llm", { temperature: v })}
            min={0} max={2} step={0.1}
          />
          <NumberField
            label={tSec("llm.maxTokens")}
            value={config.llm?.max_tokens ?? undefined}
            onChange={(v) => updateSection("llm", { max_tokens: Math.round(v) })}
            min={1} max={8192}
          />
        </div>
      </SectionCard>

      <SectionCard title={tSec("resolution.title")} description={tSec("resolution.desc")}>
        <div className="flex gap-4">
          <NumberField
            label={tSec("resolution.faqThreshold")}
            value={config.resolution?.faq_confidence_threshold ?? undefined}
            onChange={(v) => updateSection("resolution", { faq_confidence_threshold: v })}
            min={0} max={1} step={0.01}
          />
          <NumberField
            label={tSec("resolution.ragThreshold")}
            value={config.resolution?.rag_confidence_threshold ?? undefined}
            onChange={(v) => updateSection("resolution", { rag_confidence_threshold: v })}
            min={0} max={1} step={0.01}
          />
        </div>
        <ToggleField
          label={tSec("resolution.autoEscalate")}
          value={config.resolution?.auto_escalation_enabled ?? undefined}
          onChange={(v) => updateSection("resolution", { auto_escalation_enabled: v })}
        />
      </SectionCard>

      <SectionCard title={tSec("line_bot.title")} description={tSec("line_bot.desc")}>
        <ToggleField
          label={tSec("line_bot.greeting")}
          value={config.line_bot?.greeting_message_enabled ?? undefined}
          onChange={(v) => updateSection("line_bot", { greeting_message_enabled: v })}
        />
        <NumberField
          label={tSec("line_bot.maxTurns")}
          value={config.line_bot?.max_conversation_turns ?? undefined}
          onChange={(v) => updateSection("line_bot", { max_conversation_turns: Math.round(v) })}
          min={1} max={200}
        />
      </SectionCard>

      <div className="h-px w-full bg-[var(--border)]" />

      <div className="flex justify-end gap-3">
        <button
          onClick={handleReset}
          disabled={!dirty || saving}
          className="rounded-lg border border-[var(--border)] px-5 py-[10px] disabled:cursor-not-allowed disabled:opacity-50"
        >
          <span className="text-sm font-medium text-[var(--text-secondary)]">{t("reset")}</span>
        </button>
        <button
          onClick={handleSave}
          disabled={!dirty || saving}
          className="flex items-center gap-2 rounded-lg bg-[var(--primary)] px-5 py-[10px] disabled:cursor-not-allowed disabled:opacity-50"
        >
          <Save className="h-4 w-4 text-white" />
          <span className="text-sm font-medium text-white">{saving ? t("saving") : t("save")}</span>
        </button>
      </div>
    </div>
  );
}
