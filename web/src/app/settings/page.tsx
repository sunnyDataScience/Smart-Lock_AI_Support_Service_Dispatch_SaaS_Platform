"use client";

import { useEffect, useState } from "react";
import {
  User,
  Shield,
  Calculator,
  Settings as SettingsIcon,
  Upload,
  ChevronDown,
} from "lucide-react";
import Sidebar from "@/components/layout/Sidebar";
import PricingForm from "@/components/settings/PricingForm";
import SystemConfigForm from "@/components/settings/SystemConfigForm";
import ThemeToggle from "@/components/theme/ThemeToggle";
import { ApiError, api, getCurrentSession, type CurrentSession } from "@/lib/api";

const ROLE_LABELS: Record<string, string> = {
  admin: "系統管理員",
  reviewer: "審核員",
  technician: "技師",
  brand_oem: "品牌 OEM",
  line_user: "LINE 使用者",
};

function deriveName(email: string | null, userId: string | null): string {
  if (email) {
    const at = email.indexOf("@");
    return at > 0 ? email.slice(0, at) : email;
  }
  if (userId) return `User ${userId.slice(0, 6)}`;
  return "—";
}

function avatarChar(session: CurrentSession | null): string {
  if (!session) return "?";
  if (session.email) return session.email[0].toUpperCase();
  if (session.userId) return session.userId[0].toUpperCase();
  return "?";
}

type TabId = "profile" | "security" | "pricing" | "system";

interface Tab {
  id: TabId;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
}

const tabs: Tab[] = [
  { id: "system", label: "系統設定", icon: SettingsIcon },
  { id: "pricing", label: "報價規則", icon: Calculator },
  { id: "profile", label: "個人資料", icon: User },
  { id: "security", label: "帳戶安全", icon: Shield },
];

function ProfileForm() {
  const [session, setSession] = useState<CurrentSession | null>(null);

  useEffect(() => {
    setSession(getCurrentSession());
  }, []);

  const name = deriveName(session?.email ?? null, session?.userId ?? null);
  const email = session?.email ?? "—";
  const role = session?.role
    ? (ROLE_LABELS[session.role] ?? session.role)
    : "—";
  const userId = session?.userId ?? "—";
  const tenantId = session?.tenantId ?? "—";

  return (
    <div className="flex flex-1 flex-col gap-6 overflow-auto rounded-xl border border-[var(--border)] bg-[var(--bg-surface)] p-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span className="text-xl font-bold text-[var(--text-primary)]">
            個人資料
          </span>
          <span className="rounded bg-[#F1F5F9] px-2 py-[2px] text-[11px] text-[var(--text-secondary)]">
            來自 JWT；待 /users/me endpoint 上線後補齊姓名 / 電話 / 偏好
          </span>
        </div>
        <span className="text-[13px] text-[var(--text-secondary)]">
          目前登入身分由 access token 解碼
        </span>
      </div>

      <div className="h-px w-full bg-[var(--border)]" />

      {/* Avatar */}
      <div className="flex items-center gap-5">
        <div className="flex h-20 w-20 items-center justify-center rounded-full bg-[var(--primary)] text-2xl font-semibold text-white">
          {avatarChar(session)}
        </div>
        <div className="flex flex-col gap-2">
          <span className="text-base font-semibold text-[var(--text-primary)]">
            {name}
          </span>
          <span className="text-[13px] text-[var(--text-secondary)]">
            {role}
          </span>
          <button
            disabled
            title="即將推出"
            className="flex cursor-not-allowed items-center gap-[6px] rounded-lg border border-[var(--border)] px-[14px] py-[6px] opacity-60"
          >
            <Upload className="h-[14px] w-[14px] text-[var(--text-secondary)]" />
            <span className="text-[13px] font-medium text-[var(--text-secondary)]">
              上傳頭像
            </span>
          </button>
        </div>
      </div>

      {/* Form Fields */}
      <div className="flex flex-col gap-5">
        <div className="flex gap-5">
          <FormField label="顯示名稱" value={name} />
          <FormField label="電子郵件" value={email} />
        </div>

        <div className="flex gap-5">
          <FormField label="使用者 ID" value={userId} mono />
          <FormField label="角色" value={role} />
        </div>

        <div className="flex gap-5">
          <FormField label="租戶 ID" value={tenantId} mono />
          <SelectField label="時區" value="(UTC+8) 台北" disabled />
        </div>

        <div className="flex gap-5">
          <SelectField label="語言" value="繁體中文" disabled />
          <ThemeField />
        </div>

        <div className="flex gap-5">
          <FormField label="聯絡電話" value="—" placeholder="待 /users/me 上線" />
          <div className="flex-1" />
        </div>
      </div>

      <div className="h-px w-full bg-[var(--border)]" />

      {/* Action Buttons */}
      <div className="flex justify-end gap-3">
        <button
          disabled
          title="即將推出"
          className="cursor-not-allowed rounded-lg border border-[var(--border)] px-5 py-[10px] opacity-60"
        >
          <span className="text-sm font-medium text-[var(--text-secondary)]">
            取消
          </span>
        </button>
        <button
          disabled
          title="即將推出"
          className="cursor-not-allowed rounded-lg bg-[var(--primary)] px-5 py-[10px] opacity-60"
        >
          <span className="text-sm font-medium text-white">儲存變更</span>
        </button>
      </div>
    </div>
  );
}

function SecurityForm() {
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
      return "請填寫所有密碼欄位";
    }
    if (newPassword.length < 8 || newPassword.length > 72) {
      return "新密碼長度須介於 8–72 字元";
    }
    if (newPassword !== confirmPassword) {
      return "兩次輸入的新密碼不一致";
    }
    if (currentPassword === newPassword) {
      return "新密碼不可與目前密碼相同";
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
      setSuccess("密碼已更新");
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
    } catch (e) {
      setError(
        e instanceof ApiError
          ? `${e.errorCode} (${e.status})：${e.message}`
          : e instanceof Error
            ? e.message
            : String(e),
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
            帳戶安全
          </span>
          <span className="rounded bg-[#F1F5F9] px-2 py-[2px] text-[11px] text-[var(--text-secondary)]">
            密碼變更已上線；2FA / 登入裝置管理待後續模組
          </span>
        </div>
        <span className="text-[13px] text-[var(--text-secondary)]">
          管理密碼與登入安全設定
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
            label="目前密碼"
            value={currentPassword}
            onChange={setCurrentPassword}
            placeholder="輸入目前密碼"
            disabled={submitting}
          />
          <div className="flex-1" />
        </div>
        <div className="flex gap-5">
          <PasswordInput
            label="新密碼"
            value={newPassword}
            onChange={setNewPassword}
            placeholder="輸入新密碼（8–72 字元）"
            disabled={submitting}
          />
          <PasswordInput
            label="確認新密碼"
            value={confirmPassword}
            onChange={setConfirmPassword}
            placeholder="再次輸入新密碼"
            disabled={submitting}
          />
        </div>
      </div>

      <div className="h-px w-full bg-[var(--border)]" />

      <div className="flex flex-col gap-4">
        <div className="flex items-center gap-2">
          <span className="text-base font-semibold text-[var(--text-primary)]">
            雙重驗證（2FA）
          </span>
          <span className="rounded-md bg-[#FEF3C7] px-2 py-[2px] text-[10px] font-semibold text-[#92400E]">
            待接入
          </span>
        </div>
        <div className="flex items-center justify-between rounded-lg border border-dashed border-[var(--border)] bg-[#F8FAFC] p-4">
          <div className="flex flex-col gap-1">
            <span className="text-sm font-medium text-[var(--text-secondary)]">
              Authenticator App
            </span>
            <span className="text-[13px] text-[var(--text-secondary)]">
              需後端 TOTP enrol / verify endpoint；本期暫未提供
            </span>
          </div>
          <span className="rounded-md bg-[#F1F5F9] px-2 py-1 text-xs font-semibold text-[var(--text-secondary)]">
            未啟用
          </span>
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
            取消
          </span>
        </button>
        <button
          type="button"
          onClick={handleSubmit}
          disabled={submitting}
          className="rounded-lg bg-[var(--primary)] px-5 py-[10px] hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-60"
        >
          <span className="text-sm font-medium text-white">
            {submitting ? "更新中…" : "更新密碼"}
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
  return (
    <div className="flex flex-1 flex-col gap-[6px]">
      <span className="text-[13px] font-semibold text-[var(--text-primary)]">
        外觀主題
      </span>
      <div className="flex h-10 items-center">
        <ThemeToggle variant="segmented" />
      </div>
    </div>
  );
}

function SelectField({
  label,
  value,
  disabled,
}: {
  label: string;
  value: string;
  disabled?: boolean;
}) {
  return (
    <div className="flex flex-1 flex-col gap-[6px]">
      <span className="text-[13px] font-semibold text-[var(--text-primary)]">
        {label}
      </span>
      <div
        className={`flex h-10 items-center justify-between rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] px-3 ${
          disabled ? "cursor-not-allowed opacity-60" : ""
        }`}
        title={disabled ? "即將推出" : undefined}
      >
        <span className="text-sm text-[var(--text-primary)]">{value}</span>
        <ChevronDown className="h-4 w-4 text-[var(--text-secondary)]" />
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
                系統設定
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
                      {tab.label}
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
