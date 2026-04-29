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
import { getCurrentSession, type CurrentSession } from "@/lib/api";

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
          <FormField label="聯絡電話" value="—" placeholder="待 /users/me 上線" />
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
  return (
    <div className="flex flex-1 flex-col gap-6 overflow-auto rounded-xl border border-[var(--border)] bg-[var(--bg-surface)] p-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span className="text-xl font-bold text-[var(--text-primary)]">
            帳戶安全
          </span>
          <span className="rounded bg-[#F1F5F9] px-2 py-[2px] text-[11px] text-[var(--text-secondary)]">
            示意（待密碼變更 / 2FA endpoint 上線）
          </span>
        </div>
        <span className="text-[13px] text-[var(--text-secondary)]">
          管理密碼與登入安全設定
        </span>
      </div>

      <div className="h-px w-full bg-[var(--border)]" />

      <div className="flex flex-col gap-5">
        <div className="flex gap-5">
          <FormField label="目前密碼" value="••••••••" type="password" />
          <div className="flex-1" />
        </div>
        <div className="flex gap-5">
          <FormField label="新密碼" value="" placeholder="輸入新密碼" type="password" />
          <FormField label="確認新密碼" value="" placeholder="再次輸入新密碼" type="password" />
        </div>
      </div>

      <div className="h-px w-full bg-[var(--border)]" />

      <div className="flex flex-col gap-4">
        <span className="text-base font-semibold text-[var(--text-primary)]">
          雙重驗證（2FA）
        </span>
        <div className="flex items-center justify-between rounded-lg border border-[var(--border)] p-4">
          <div className="flex flex-col gap-1">
            <span className="text-sm font-medium text-[var(--text-primary)]">
              Authenticator App
            </span>
            <span className="text-[13px] text-[var(--text-secondary)]">
              使用 Google Authenticator 或類似應用程式
            </span>
          </div>
          <span className="rounded-md bg-[#DCFCE7] px-2 py-1 text-xs font-semibold text-[#16A34A]">
            已啟用
          </span>
        </div>
      </div>

      <div className="h-px w-full bg-[var(--border)]" />

      <div className="flex justify-end gap-3">
        <button className="rounded-lg border border-[var(--border)] px-5 py-[10px]">
          <span className="text-sm font-medium text-[var(--text-secondary)]">
            取消
          </span>
        </button>
        <button className="rounded-lg bg-[var(--primary)] px-5 py-[10px]">
          <span className="text-sm font-medium text-white">更新密碼</span>
        </button>
      </div>
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
