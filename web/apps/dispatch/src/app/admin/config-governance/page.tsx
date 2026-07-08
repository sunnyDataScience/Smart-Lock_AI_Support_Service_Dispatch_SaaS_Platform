"use client";

import { useCallback, useEffect, useState } from "react";
import { SlidersHorizontal, Check } from "lucide-react";
import Sidebar from "@shared/components/layout/Sidebar";
import { api, tenantPath, getCurrentSession } from "@shared/lib/api";
import { friendlyError } from "@shared/lib/apiError";

interface ActiveVersion {
  namespace: string;
  key: string;
  active_version_id: string | null;
  active_value: unknown;
  active_since: string | null;
}

// 常見 namespace 中文說明（CR-0036/0044/0045/0046）
const NS_HINT: Record<string, string> = {
  dispatch_commission: "派工佣金 / 結算費率",
  deposit_policy: "訂金政策",
  monthly_settlement: "月結參數",
  cancellation_policy: "取消費規則",
  tax_policy: "稅率 / 含稅模式",
  company_profile: "公司基本資料（PDF 文案）",
  discount_policy: "折扣政策",
  problemcard_policy: "問題卡完整度門檻",
  quote_policy: "報價政策 / 加價規則",
  completion_policy: "完工硬閘門檻",
};

const KEY = "default";

export default function ConfigGovernancePage() {
  const [namespaces, setNamespaces] = useState<string[]>([]);
  const [selected, setSelected] = useState<string>("");
  const [active, setActive] = useState<ActiveVersion | null>(null);
  const [draftValue, setDraftValue] = useState("");
  const [reason, setReason] = useState("");
  const [draftVersionId, setDraftVersionId] = useState<string | null>(null);
  const [approverId, setApproverId] = useState("");
  const [strategy, setStrategy] = useState<"instant" | "canary_5_50_100">("instant");
  const [error, setError] = useState<string | null>(null);
  const [ok, setOk] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const res = await api.get<{ items: string[] }>(tenantPath("/m18/configs"));
        setNamespaces(res.items ?? []);
        if (res.items?.length) setSelected(res.items[0]);
      } catch (e) {
        setError(fmt(e));
      }
    })();
  }, []);

  const loadActive = useCallback(async (ns: string) => {
    setError(null);
    setOk(null);
    setDraftVersionId(null);
    try {
      const res = await api.get<ActiveVersion>(tenantPath(`/m18/configs/${ns}/${KEY}`));
      setActive(res);
      setDraftValue(res.active_value != null ? JSON.stringify(res.active_value, null, 2) : "{\n  \n}");
    } catch (e) {
      setError(fmt(e));
      setActive(null);
    }
  }, []);

  useEffect(() => {
    if (selected) loadActive(selected);
  }, [selected, loadActive]);

  async function createDraft() {
    let parsed: unknown;
    try {
      parsed = JSON.parse(draftValue);
    } catch {
      setError("設定值不是合法 JSON");
      return;
    }
    if (reason.trim().length < 1) {
      setError("請填寫變更理由");
      return;
    }
    setBusy(true);
    setError(null);
    setOk(null);
    try {
      const res = await api.put<{ version_id?: string; id?: string }>(
        tenantPath(`/m18/configs/${selected}/${KEY}`),
        { proposed_value: parsed, reason: reason.trim() },
        { headers: { "X-Initiator": getCurrentSession()?.userId ?? "operator" } },
      );
      const vid = res.version_id || res.id || null;
      setDraftVersionId(vid);
      setOk(`草稿已建立${vid ? `（version ${vid.slice(0, 8)}）` : ""}。下一步：填覆核人後啟動上線。`);
    } catch (e) {
      setError(fmt(e));
    } finally {
      setBusy(false);
    }
  }

  async function startRollout() {
    if (!draftVersionId) return;
    const initiator = getCurrentSession()?.userId ?? "operator";
    if (!approverId.trim() || approverId.trim() === initiator) {
      setError("請填寫覆核人，且須與發起人為不同人員（職責分離）");
      return;
    }
    setBusy(true);
    setError(null);
    setOk(null);
    try {
      await api.post(
        tenantPath(`/m18/configs/${selected}/${KEY}/versions/${draftVersionId}:start-rollout`),
        { strategy, observation_minutes_per_stage: 15 },
        { headers: { "X-Initiator": initiator, "X-Approver": approverId.trim() } },
      );
      setOk("已啟動上線（雙簽通過）。");
      setDraftVersionId(null);
      setApproverId("");
      loadActive(selected);
    } catch (e) {
      setError(fmt(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex h-full bg-[var(--bg-page)]">
      <Sidebar />
      <div className="flex flex-1 flex-col overflow-hidden">
        <div className="flex items-center gap-3 border-b border-[var(--border)] bg-[var(--bg-surface)] pl-14 pr-4 md:px-8 py-5">
          <SlidersHorizontal className="h-7 w-7 text-[var(--primary)]" />
          <h1 className="text-2xl font-bold text-[var(--text-primary)]">設定治理</h1>
        </div>

        <div className="flex-1 overflow-auto pl-14 pr-4 md:px-8 py-6">
          {error && <div className="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>}
          {ok && (
            <div className="mb-4 flex items-center gap-2 rounded-lg border border-green-200 bg-green-50 px-4 py-3 text-sm text-green-700">
              <Check className="h-4 w-4" /> {ok}
            </div>
          )}

          <div className="grid grid-cols-1 gap-6 lg:grid-cols-[260px_1fr]">
            {/* namespace 清單 */}
            <div className="flex flex-col gap-1 rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] p-2">
              {namespaces.length === 0 ? (
                <span className="px-2 py-2 text-[13px] text-[var(--text-disabled)]">載入中…</span>
              ) : (
                namespaces.map((ns) => (
                  <button
                    key={ns}
                    onClick={() => setSelected(ns)}
                    className={`flex flex-col items-start rounded-md px-3 py-2 text-left text-[13px] ${
                      ns === selected ? "bg-[var(--primary)] text-white" : "text-[var(--text-primary)] hover:bg-[var(--bg-page)]"
                    }`}
                  >
                    {/* 中文說明為主標、原始 namespace 鍵降為小字副標供管理者對照（NS_HINT 缺漏才以鍵為主標）*/}
                    <span className={`text-[13px] font-medium ${NS_HINT[ns] ? "" : "font-mono text-[12px]"}`}>
                      {NS_HINT[ns] ?? ns}
                    </span>
                    {NS_HINT[ns] && (
                      <span className={`font-mono text-[11px] ${ns === selected ? "text-white/70" : "text-[var(--text-disabled)]"}`}>
                        {ns}
                      </span>
                    )}
                  </button>
                ))
              )}
            </div>

            {/* 編輯區 */}
            <div className="flex flex-col gap-4">
              {active && (
                <div className="rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] p-4">
                  <div className="mb-2 flex items-center justify-between">
                    <span className="text-[15px] font-semibold text-[var(--text-primary)]">
                      {selected} {NS_HINT[selected] ? `· ${NS_HINT[selected]}` : ""}
                    </span>
                    <span className="text-[12px] text-[var(--text-secondary)]">
                      {active.active_version_id
                        ? `生效版本 ${active.active_version_id.slice(0, 8)}${active.active_since ? ` · ${active.active_since.slice(0, 10)}` : ""}`
                        : "無生效版本"}
                    </span>
                  </div>

                  <label className="flex flex-col gap-1">
                    <span className="text-[12px] font-medium text-[var(--text-secondary)]">設定值（JSON）</span>
                    <textarea
                      value={draftValue}
                      onChange={(e) => setDraftValue(e.target.value)}
                      rows={12}
                      spellCheck={false}
                      className="rounded-md border border-[var(--border)] bg-[#F8FAFC] px-3 py-2 font-mono text-[12px] outline-none focus:border-[var(--primary)]"
                    />
                  </label>
                  <label className="mt-3 flex flex-col gap-1">
                    <span className="text-[12px] font-medium text-[var(--text-secondary)]">變更理由 <span className="text-red-500">*</span></span>
                    <input
                      value={reason}
                      onChange={(e) => setReason(e.target.value)}
                      className="rounded-md border border-[var(--border)] px-3 py-2 text-[13px] outline-none focus:border-[var(--primary)]"
                    />
                  </label>
                  <button
                    onClick={createDraft}
                    disabled={busy}
                    className="mt-3 rounded-md bg-[var(--primary)] px-4 py-2 text-sm font-semibold text-white hover:bg-[#1D4ED8] disabled:opacity-50"
                  >
                    建立草稿
                  </button>
                </div>
              )}

              {/* 啟動上線（SoD 雙簽）*/}
              {draftVersionId && (
                <div className="rounded-lg border border-[#F59E0B] bg-[#FFFBEB] p-4">
                  <div className="mb-2 text-[14px] font-semibold text-[#92400E]">啟動上線（職責分離雙簽）</div>
                  <p className="mb-3 text-[12px] text-[var(--text-secondary)]">
                    草稿 {draftVersionId.slice(0, 8)} 待上線。發起人為您本人，覆核人須為另一位管理員（不可同人）。
                  </p>
                  <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                    <label className="flex flex-col gap-1">
                      <span className="text-[12px] font-medium text-[var(--text-secondary)]">覆核人帳號（另一位管理員） <span className="text-red-500">*</span></span>
                      <input
                        value={approverId}
                        onChange={(e) => setApproverId(e.target.value)}
                        placeholder="輸入另一位管理員的使用者 ID"
                        className="rounded-md border border-[var(--border)] px-3 py-2 font-mono text-[12px] outline-none focus:border-[var(--primary)]"
                      />
                    </label>
                    <label className="flex flex-col gap-1">
                      <span className="text-[12px] font-medium text-[var(--text-secondary)]">上線策略</span>
                      <select
                        value={strategy}
                        onChange={(e) => setStrategy(e.target.value as "instant" | "canary_5_50_100")}
                        className="rounded-md border border-[var(--border)] px-3 py-2 text-[13px] outline-none focus:border-[var(--primary)]"
                      >
                        <option value="instant">立即上線</option>
                        <option value="canary_5_50_100">灰度（5%→50%→100%）</option>
                      </select>
                    </label>
                  </div>
                  <button
                    onClick={startRollout}
                    disabled={busy}
                    className="mt-3 rounded-md bg-[#B45309] px-4 py-2 text-sm font-semibold text-white hover:opacity-90 disabled:opacity-50"
                  >
                    雙簽啟動上線
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function fmt(e: unknown): string {
  return friendlyError(e);
}
