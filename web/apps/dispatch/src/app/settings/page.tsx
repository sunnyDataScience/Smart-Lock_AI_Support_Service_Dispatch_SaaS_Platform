"use client";

import { useEffect, useState } from "react";
import {
  User,
  Shield,
  Calculator,
  Settings as SettingsIcon,
} from "lucide-react";
import Sidebar from "@shared/components/layout/Sidebar";
import PricingForm from "@/components/settings/PricingForm";
import SystemConfigForm from "@/components/settings/SystemConfigForm";
import ThemeToggle from "@shared/components/theme/ThemeToggle";
import LocaleToggle from "@shared/components/i18n/LocaleToggle";
import { useTranslations } from "@shared/components/i18n/LocaleProvider";
import { api, getCurrentSession, type CurrentSession } from "@shared/lib/api";
import { cacheInvalidate } from "@shared/lib/cache";
import { friendlyError } from "@shared/lib/apiError";

type TabId = "profile" | "security" | "pricing" | "system";

interface Tab {
  id: TabId;
  icon: React.ComponentType<{ className?: string }>;
}

// label 走 i18n key（settings.tabs.{id}），避免硬編 zh-TW
const tabs: Tab[] = [
  { id: "system", icon: SettingsIcon },
  { id: "pricing", icon: Calculator },
  { id: "profile", icon: User },
  { id: "security", icon: Shield },
];

interface MyProfile {
  display_name: string | null;
  email: string | null;
  phone: string | null;
  role: string | null;
}

function EditableField({
  label,
  value,
  onChange,
  placeholder,
  disabled,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  disabled?: boolean;
}) {
  return (
    <div className="flex flex-1 flex-col gap-[6px]">
      <span className="text-[13px] font-semibold text-[var(--text-primary)]">
        {label}
      </span>
      <input
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        disabled={disabled}
        className="h-10 rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] px-3 text-sm text-[var(--text-primary)] outline-none focus:border-[var(--primary)] disabled:cursor-not-allowed disabled:opacity-60 placeholder:text-[var(--text-disabled)]"
      />
    </div>
  );
}

function ProfileForm() {
  const tCommon = useTranslations("common");
  const tProfile = useTranslations("settings.profile");
  const tRole = useTranslations("role");
  const [session, setSession] = useState<CurrentSession | null>(null);
  const [displayName, setDisplayName] = useState("");
  const [phone, setPhone] = useState("");
  const [original, setOriginal] = useState({ name: "", phone: "" });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  useEffect(() => {
    setSession(getCurrentSession());
    (async () => {
      try {
        // 自助個人資料：display_name / phone 由 /auth/me 取真實 DB 值（非只 JWT）
        const res = await api.get<{ data: MyProfile }>("/api/v1/auth/me");
        const p = res.data;
        setDisplayName(p.display_name ?? "");
        setPhone(p.phone ?? "");
        setOriginal({ name: p.display_name ?? "", phone: p.phone ?? "" });
      } catch (e) {
        setError(friendlyError(e));
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const dash = tCommon("notAvailable");
  const email = session?.email ?? dash;
  const role = session?.role ? tRole(session.role) : dash;
  const userId = session?.userId ?? dash;
  const tenantId = session?.tenantId ?? dash;
  const dirty = displayName !== original.name || phone !== original.phone;
  const avatarText = (displayName || session?.email || "?")[0]?.toUpperCase() ?? "?";

  async function handleSave() {
    setError(null);
    setSuccess(null);
    if (!displayName.trim()) {
      setError(tProfile("nameRequired"));
      return;
    }
    setSaving(true);
    try {
      const res = await api.patch<{ data: MyProfile }>("/api/v1/auth/me", {
        display_name: displayName.trim(),
        phone: phone.trim(),
      });
      const p = res.data;
      setDisplayName(p.display_name ?? "");
      setPhone(p.phone ?? "");
      setOriginal({ name: p.display_name ?? "", phone: p.phone ?? "" });
      cacheInvalidate("GET:");
      setSuccess(tProfile("savedMsg"));
    } catch (e) {
      setError(friendlyError(e));
    } finally {
      setSaving(false);
    }
  }

  function handleCancel() {
    setDisplayName(original.name);
    setPhone(original.phone);
    setError(null);
    setSuccess(null);
  }

  return (
    <div className="flex flex-1 flex-col gap-6 overflow-auto rounded-xl border border-[var(--border)] bg-[var(--bg-surface)] p-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span className="text-xl font-bold text-[var(--text-primary)]">
            {tProfile("title")}
          </span>
        </div>
        <span className="text-[13px] text-[var(--text-secondary)]">
          {tProfile("metaSession")}
        </span>
      </div>

      <div className="h-px w-full bg-[var(--border)]" />

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}
      {success && (
        <div className="rounded-lg border border-green-200 bg-green-50 px-4 py-3 text-sm text-green-700">
          {success}
        </div>
      )}

      {/* Avatar */}
      <div className="flex items-center gap-5">
        <div className="flex h-20 w-20 items-center justify-center rounded-full bg-[var(--primary)] text-2xl font-semibold text-white">
          {avatarText}
        </div>
        <div className="flex flex-col gap-1">
          <span className="text-base font-semibold text-[var(--text-primary)]">
            {displayName || dash}
          </span>
          <span className="text-[13px] text-[var(--text-secondary)]">
            {role}
          </span>
        </div>
      </div>

      {/* Form Fields */}
      <div className="flex flex-col gap-5">
        <div className="flex gap-5">
          <EditableField
            label={tProfile("displayName")}
            value={displayName}
            onChange={setDisplayName}
            placeholder={tProfile("displayName")}
            disabled={loading || saving}
          />
          <FormField label={tProfile("email")} value={email} />
        </div>

        <div className="flex gap-5">
          <FormField label={tProfile("userId")} value={userId} mono />
          <FormField label={tProfile("role")} value={role} />
        </div>

        <div className="flex gap-5">
          <FormField label={tProfile("tenantId")} value={tenantId} mono />
          <FormField
            label={tProfile("timezone")}
            value={tProfile("timezoneTaipei")}
          />
        </div>

        <div className="flex gap-5">
          <LanguageField />
          <ThemeField />
        </div>

        <div className="flex gap-5">
          <EditableField
            label={tProfile("phone")}
            value={phone}
            onChange={setPhone}
            placeholder={tProfile("phonePlaceholder")}
            disabled={loading || saving}
          />
          <div className="flex-1" />
        </div>
      </div>

      <div className="h-px w-full bg-[var(--border)]" />

      {/* Action Buttons */}
      <div className="flex justify-end gap-3">
        <button
          type="button"
          onClick={handleCancel}
          disabled={!dirty || saving}
          className="rounded-lg border border-[var(--border)] px-5 py-[10px] hover:bg-[var(--bg-page)] disabled:cursor-not-allowed disabled:opacity-60"
        >
          <span className="text-sm font-medium text-[var(--text-secondary)]">
            {tCommon("cancel")}
          </span>
        </button>
        <button
          type="button"
          onClick={handleSave}
          disabled={!dirty || saving}
          className="rounded-lg bg-[var(--primary)] px-5 py-[10px] hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-60"
        >
          <span className="text-sm font-medium text-white">
            {saving ? tProfile("saving") : tCommon("saveChanges")}
          </span>
        </button>
      </div>
    </div>
  );
}

function SecurityForm() {
  const tCommon = useTranslations("common");
  const tSec = useTranslations("settings.security");
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  function reset() {
    setCurrentPassword("");
    setNewPassword("");
    setConfirmPassword("");
    setError(null);
    setSuccess(null);
  }

  function validate(): string | null {
    if (!currentPassword || !newPassword || !confirmPassword) {
      return tSec("validateMissing");
    }
    if (newPassword.length < 8 || newPassword.length > 72) {
      return tSec("validateLength");
    }
    if (newPassword !== confirmPassword) {
      return tSec("validateMismatch");
    }
    if (currentPassword === newPassword) {
      return tSec("validateSame");
    }
    return null;
  }

  async function handleSubmit() {
    setError(null);
    setSuccess(null);
    const v = validate();
    if (v) {
      setError(v);
      return;
    }
    setSubmitting(true);
    try {
      await api.post<unknown>("/api/v1/auth/change-password", {
        current_password: currentPassword,
        new_password: newPassword,
      });
      setSuccess(tSec("successMsg"));
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
    } catch (e) {
      setError(
        friendlyError(e),
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="flex flex-1 flex-col gap-6 overflow-auto rounded-xl border border-[var(--border)] bg-[var(--bg-surface)] p-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span className="text-xl font-bold text-[var(--text-primary)]">
            {tSec("title")}
          </span>
          <span className="rounded bg-[#F1F5F9] px-2 py-[2px] text-[11px] text-[var(--text-secondary)]">
            {tSec("metaCurrent")}
          </span>
        </div>
        <span className="text-[13px] text-[var(--text-secondary)]">
          {tSec("metaSubtitle")}
        </span>
      </div>

      <div className="h-px w-full bg-[var(--border)]" />

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}
      {success && (
        <div className="rounded-lg border border-green-200 bg-green-50 px-4 py-3 text-sm text-green-700">
          {success}
        </div>
      )}

      <div className="flex flex-col gap-5">
        <div className="flex gap-5">
          <PasswordInput
            label={tSec("currentPassword")}
            value={currentPassword}
            onChange={setCurrentPassword}
            placeholder={tSec("currentPasswordPlaceholder")}
            disabled={submitting}
          />
          <div className="flex-1" />
        </div>
        <div className="flex gap-5">
          <PasswordInput
            label={tSec("newPassword")}
            value={newPassword}
            onChange={setNewPassword}
            placeholder={tSec("newPasswordPlaceholder")}
            disabled={submitting}
          />
          <PasswordInput
            label={tSec("confirmPassword")}
            value={confirmPassword}
            onChange={setConfirmPassword}
            placeholder={tSec("confirmPasswordPlaceholder")}
            disabled={submitting}
          />
        </div>
      </div>

      <div className="h-px w-full bg-[var(--border)]" />

      <div className="flex justify-end gap-3">
        <button
          type="button"
          onClick={reset}
          disabled={submitting}
          className="rounded-lg border border-[var(--border)] px-5 py-[10px] hover:bg-[var(--bg-page)] disabled:cursor-not-allowed disabled:opacity-60"
        >
          <span className="text-sm font-medium text-[var(--text-secondary)]">
            {tCommon("cancel")}
          </span>
        </button>
        <button
          type="button"
          onClick={handleSubmit}
          disabled={submitting}
          className="rounded-lg bg-[var(--primary)] px-5 py-[10px] hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-60"
        >
          <span className="text-sm font-medium text-white">
            {submitting ? tSec("updating") : tSec("updatePassword")}
          </span>
        </button>
      </div>
    </div>
  );
}

function PasswordInput({
  label,
  value,
  onChange,
  placeholder,
  disabled,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  disabled?: boolean;
}) {
  return (
    <div className="flex flex-1 flex-col gap-[6px]">
      <span className="text-[13px] font-semibold text-[var(--text-primary)]">
        {label}
      </span>
      <input
        type="password"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        disabled={disabled}
        autoComplete="new-password"
        className="h-10 rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] px-3 text-sm text-[var(--text-primary)] outline-none focus:border-[var(--primary)] disabled:cursor-not-allowed disabled:opacity-60 placeholder:text-[var(--text-disabled)]"
      />
    </div>
  );
}

function FormField({
  label,
  value,
  mono,
  type,
  placeholder,
}: {
  label: string;
  value: string;
  mono?: boolean;
  type?: string;
  placeholder?: string;
}) {
  return (
    <div className="flex flex-1 flex-col gap-[6px]">
      <span className="text-[13px] font-semibold text-[var(--text-primary)]">
        {label}
      </span>
      <div className="flex h-10 items-center rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] px-3">
        <span
          className={`text-sm ${
            value
              ? "text-[var(--text-primary)]"
              : "text-[var(--text-disabled)]"
          } ${mono ? "font-['IBM_Plex_Mono']" : ""}`}
        >
          {value || placeholder || ""}
        </span>
      </div>
    </div>
  );
}

function ThemeField() {
  const t = useTranslations("settings.profile");
  return (
    <div className="flex flex-1 flex-col gap-[6px]">
      <span className="text-[13px] font-semibold text-[var(--text-primary)]">
        {t("theme")}
      </span>
      <div className="flex h-10 items-center">
        <ThemeToggle variant="segmented" />
      </div>
    </div>
  );
}

function LanguageField() {
  const t = useTranslations("settings.profile");
  return (
    <div className="flex flex-1 flex-col gap-[6px]">
      <span className="text-[13px] font-semibold text-[var(--text-primary)]">
        {t("language")}
      </span>
      <div className="flex h-10 items-center">
        <LocaleToggle variant="segmented" />
      </div>
    </div>
  );
}

const tabContent: Record<TabId, React.ComponentType> = {
  system: SystemConfigForm,
  pricing: PricingForm,
  profile: ProfileForm,
  security: SecurityForm,
};

export default function SettingsPage() {
  const tTabs = useTranslations("settings.tabs");
  const tTitle = useTranslations("settings");
  const [activeTab, setActiveTab] = useState<TabId>("system");

  const ActiveContent = tabContent[activeTab];

  return (
    <div className="flex h-full bg-[var(--bg-page)]">
      <Sidebar />

      <div className="flex flex-1 overflow-hidden p-6 pl-8 pr-8">
        <div className="flex flex-1 gap-6">
          {/* Left Tab Nav */}
          <div className="flex w-[220px] flex-col gap-1 rounded-xl border border-[var(--border)] bg-[var(--bg-surface)] py-4">
            <div className="px-4 pb-3">
              <span className="text-lg font-bold text-[var(--text-primary)]">
                {tTitle("title")}
              </span>
            </div>
            <div className="mx-0 h-px bg-[var(--border)]" />
            <div className="flex flex-col gap-1 pt-1">
              {tabs.map((tab) => {
                const isActive = activeTab === tab.id;
                const Icon = tab.icon;
                return (
                  <button
                    key={tab.id}
                    onClick={() => setActiveTab(tab.id)}
                    className={`mx-0 flex h-11 items-center gap-3 px-4 text-left ${
                      isActive
                        ? "border-l-[3px] border-l-[var(--primary)] bg-[#EFF6FF]"
                        : ""
                    }`}
                  >
                    <Icon
                      className={`h-5 w-5 ${
                        isActive
                          ? "text-[var(--primary)]"
                          : "text-[var(--text-secondary)]"
                      }`}
                    />
                    <span
                      className={`text-sm ${
                        isActive
                          ? "font-semibold text-[var(--primary)]"
                          : "font-medium text-[var(--text-secondary)]"
                      }`}
                    >
                      {tTabs(tab.id)}
                    </span>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Right Content */}
          <ActiveContent />
        </div>
      </div>
    </div>
  );
}
