"use client";

import { useState } from "react";
import {
  User,
  Shield,
  Calculator,
  TrendingUp,
  Upload,
  ChevronDown,
} from "lucide-react";
import Sidebar from "@/components/layout/Sidebar";
import PricingForm from "@/components/settings/PricingForm";

type TabId = "profile" | "security" | "pricing" | "surcharge";

interface Tab {
  id: TabId;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
}

const tabs: Tab[] = [
  { id: "profile", label: "個人資料", icon: User },
  { id: "security", label: "帳戶安全", icon: Shield },
  { id: "pricing", label: "報價規則 V2.0", icon: Calculator },
  { id: "surcharge", label: "加價規則 V2.0", icon: TrendingUp },
];

function ProfileForm() {
  return (
    <div className="flex flex-1 flex-col gap-6 overflow-auto rounded-xl border border-[var(--border)] bg-[var(--bg-surface)] p-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <span className="text-xl font-bold text-[var(--text-primary)]">
          個人資料
        </span>
        <span className="text-[13px] text-[var(--text-secondary)]">
          管理您的個人資訊與偏好設定
        </span>
      </div>

      <div className="h-px w-full bg-[var(--border)]" />

      {/* Avatar */}
      <div className="flex items-center gap-5">
        <div className="flex h-20 w-20 items-center justify-center rounded-full bg-[#E2E8F0]">
          <User className="h-8 w-8 text-[var(--text-secondary)]" />
        </div>
        <div className="flex flex-col gap-2">
          <span className="text-base font-semibold text-[var(--text-primary)]">
            王小明
          </span>
          <span className="text-[13px] text-[var(--text-secondary)]">
            系統管理員
          </span>
          <button className="flex items-center gap-[6px] rounded-lg border border-[var(--border)] px-[14px] py-[6px]">
            <Upload className="h-[14px] w-[14px] text-[var(--text-secondary)]" />
            <span className="text-[13px] font-medium text-[var(--text-secondary)]">
              上傳頭像
            </span>
          </button>
        </div>
      </div>

      {/* Form Fields */}
      <div className="flex flex-col gap-5">
        {/* Row 1: Name & Email */}
        <div className="flex gap-5">
          <FormField label="姓名" value="王小明" />
          <FormField label="電子郵件" value="wang.xiaoming@smartlock.com" />
        </div>

        {/* Row 2: Phone & Timezone */}
        <div className="flex gap-5">
          <FormField label="聯絡電話" value="0912-345-678" mono />
          <SelectField label="時區" value="(UTC+8) 台北" />
        </div>

        {/* Row 3: Language */}
        <div className="flex gap-5">
          <SelectField label="語言" value="繁體中文" />
          <div className="flex-1" />
        </div>
      </div>

      <div className="h-px w-full bg-[var(--border)]" />

      {/* Action Buttons */}
      <div className="flex justify-end gap-3">
        <button className="rounded-lg border border-[var(--border)] px-5 py-[10px]">
          <span className="text-sm font-medium text-[var(--text-secondary)]">
            取消
          </span>
        </button>
        <button className="rounded-lg bg-[var(--primary)] px-5 py-[10px]">
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
        <span className="text-xl font-bold text-[var(--text-primary)]">
          帳戶安全
        </span>
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

function SurchargeForm() {
  return (
    <div className="flex flex-1 flex-col gap-6 overflow-auto rounded-xl border border-[var(--border)] bg-[var(--bg-surface)] p-6">
      <div className="flex items-center justify-between">
        <span className="text-xl font-bold text-[var(--text-primary)]">
          加價規則 V2.0
        </span>
        <span className="text-[13px] text-[var(--text-secondary)]">
          管理特殊時段與條件加價
        </span>
      </div>

      <div className="h-px w-full bg-[var(--border)]" />

      <div className="overflow-hidden rounded-lg border border-[var(--border)]">
        <div className="flex items-center bg-[#F8FAFC] px-4 py-3">
          <div className="w-[200px]">
            <span className="text-xs font-semibold text-[var(--text-secondary)]">
              加價條件
            </span>
          </div>
          <div className="flex flex-1 justify-center">
            <span className="text-xs font-semibold text-[var(--text-secondary)]">
              加價比例
            </span>
          </div>
          <div className="flex flex-1 justify-center">
            <span className="text-xs font-semibold text-[var(--text-secondary)]">
              適用時段
            </span>
          </div>
          <div className="flex flex-1 justify-center">
            <span className="text-xs font-semibold text-[var(--text-secondary)]">
              狀態
            </span>
          </div>
        </div>
        {[
          { condition: "夜間服務", rate: "+50%", time: "22:00 - 06:00", active: true },
          { condition: "假日服務", rate: "+30%", time: "週六、日及國定假日", active: true },
          { condition: "緊急派工", rate: "+80%", time: "2 小時內到場", active: true },
          { condition: "偏遠地區", rate: "+20%", time: "距離 > 30km", active: false },
        ].map((row) => (
          <div
            key={row.condition}
            className="flex items-center border-t border-[var(--border)] px-4 py-3"
          >
            <div className="w-[200px]">
              <span className="text-[13px] font-medium text-[var(--text-primary)]">
                {row.condition}
              </span>
            </div>
            <div className="flex flex-1 justify-center">
              <span className="font-['IBM_Plex_Mono'] text-[13px] font-semibold text-[var(--primary)]">
                {row.rate}
              </span>
            </div>
            <div className="flex flex-1 justify-center">
              <span className="text-[13px] text-[var(--text-secondary)]">
                {row.time}
              </span>
            </div>
            <div className="flex flex-1 justify-center">
              <span
                className={`rounded-md px-2 py-1 text-xs font-semibold ${
                  row.active
                    ? "bg-[#DCFCE7] text-[#16A34A]"
                    : "bg-[#F1F5F9] text-[var(--text-secondary)]"
                }`}
              >
                {row.active ? "啟用" : "停用"}
              </span>
            </div>
          </div>
        ))}
      </div>

      <div className="h-px w-full bg-[var(--border)]" />

      <div className="flex justify-end gap-3">
        <button className="rounded-lg border border-[var(--border)] px-5 py-[10px]">
          <span className="text-sm font-medium text-[var(--text-secondary)]">
            重置為預設
          </span>
        </button>
        <button className="rounded-lg bg-[var(--primary)] px-5 py-[10px]">
          <span className="text-sm font-medium text-white">儲存規則</span>
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

function SelectField({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-1 flex-col gap-[6px]">
      <span className="text-[13px] font-semibold text-[var(--text-primary)]">
        {label}
      </span>
      <div className="flex h-10 items-center justify-between rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] px-3">
        <span className="text-sm text-[var(--text-primary)]">{value}</span>
        <ChevronDown className="h-4 w-4 text-[var(--text-secondary)]" />
      </div>
    </div>
  );
}

const tabContent: Record<TabId, React.ComponentType> = {
  profile: ProfileForm,
  security: SecurityForm,
  pricing: PricingForm,
  surcharge: SurchargeForm,
};

export default function SettingsPage() {
  const [activeTab, setActiveTab] = useState<TabId>("profile");

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
