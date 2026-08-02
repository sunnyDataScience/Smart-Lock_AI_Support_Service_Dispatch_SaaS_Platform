"use client";

import { useCallback, useEffect, useState } from "react";
import { Plus, Trash2 } from "lucide-react";
import { api } from "@/lib/api";
import { friendlyError } from "@/lib/apiError";

/**
 * BrandAuthorizationPanel — 技師的品牌授權名單維護。
 *
 * **為什麼需要這個畫面**（CR-0197）：品牌授權是 04_SRS.md FR-TEC-02 的准入閘門
 * （驗收欄明文「未過准入閘門不得進入派工候選集」），程式端的 fail-closed 已經寫好、
 * M18 開關 `dispatch_policy.brand_auth_enforce` 也就位，但**預設關閉**——因為
 * prod 的授權表從 CR-0060 建立至今只有那批 `is_mock` seed（Generic／Kaadas／
 * Philips／Samsung／Yale 各 13 筆），實際在用的 Chatlock／Dormakaba／美樂／
 * Xiaomi／Gateman 一筆都沒有。
 *
 * 而在此之前**四站台都沒有維護這份名單的畫面**，只有 API（PUT/DELETE
 * /api/v1/platform/technicians/{id}/brand-authorizations/{brand}），營運只能打
 * API 或直接下 SQL。沒有畫面 = 名單永遠補不齊 = 閘門永遠不能開。
 *
 * 撤銷用 DELETE（服務端是軟撤：authorized=FALSE），所以下方文案講「撤銷」不是「刪除」。
 */

type BrandAuth = {
  brand: string;
  authorized: boolean;
  cert_expires_at?: string | null;
  updated_at?: string | null;
};

/** 目前 prod 實際出現過的品牌（含尚無授權資料的五個）。可自行輸入其他值。 */
const KNOWN_BRANDS = [
  "Chatlock", "Dormakaba", "Yale", "Kaadas", "Philips",
  "Samsung", "Xiaomi", "Gateman", "美樂", "Generic",
];

function isExpired(d?: string | null): boolean {
  if (!d) return false;
  return new Date(d) < new Date(new Date().toDateString());
}

export default function BrandAuthorizationPanel({ technicianId }: { technicianId: string }) {
  const base = `/api/v1/platform/technicians/${encodeURIComponent(technicianId)}/brand-authorizations`;
  const [rows, setRows] = useState<BrandAuth[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [adding, setAdding] = useState(false);
  const [newBrand, setNewBrand] = useState("");
  const [newExpiry, setNewExpiry] = useState("");

  const load = useCallback(async () => {
    setError(null);
    try {
      const res = await api.get<{ data?: BrandAuth[] } | BrandAuth[]>(base);
      const list = Array.isArray(res) ? res : (res.data ?? []);
      setRows(list);
    } catch (e) {
      setError(friendlyError(e));
    } finally {
      setLoading(false);
    }
  }, [base]);

  useEffect(() => {
    void load();
  }, [load]);

  const grant = async (brand: string, expiry: string) => {
    const b = brand.trim();
    if (!b) return;
    setBusy(b);
    setError(null);
    try {
      await api.put(`${base}/${encodeURIComponent(b)}`, {
        cert_expires_at: expiry.trim() || null,
      });
      setNewBrand("");
      setNewExpiry("");
      setAdding(false);
      await load();
    } catch (e) {
      setError(friendlyError(e));
    } finally {
      setBusy(null);
    }
  };

  const revoke = async (brand: string) => {
    // 撤銷會讓該技師從此品牌的派工候選集消失（閘門啟用時），影響營運，故二次確認。
    if (!window.confirm(`撤銷「${brand}」授權？該技師將不再出現在此品牌的派工候選集。`)) return;
    setBusy(brand);
    setError(null);
    try {
      await api.delete(`${base}/${encodeURIComponent(brand)}`);
      await load();
    } catch (e) {
      setError(friendlyError(e));
    } finally {
      setBusy(null);
    }
  };

  const active = rows.filter((r) => r.authorized);

  return (
    <section className="rounded-xl border border-[var(--border)] bg-[var(--bg-surface)] p-6">
      <div className="mb-1 flex items-center justify-between">
        <h2 className="text-base font-semibold text-[var(--text-primary)]">品牌授權</h2>
        {!adding && (
          <button
            type="button"
            onClick={() => setAdding(true)}
            className="flex items-center gap-1.5 rounded-lg border border-[var(--primary)] px-3 py-1.5 text-sm font-medium text-[var(--primary)] transition hover:bg-[var(--primary-subtle,rgba(59,130,246,0.08))]"
          >
            <Plus className="h-3.5 w-3.5" aria-hidden />
            新增授權
          </button>
        )}
      </div>
      <p className="mb-4 text-xs text-[var(--text-secondary)]">
        決定此技師可被派往哪些品牌的工單（FR-TEC-02 准入閘門）。
        認證到期日留空＝不設期限；已過期的授權不計入候選。
      </p>

      {error && (
        <div className="mb-3 rounded-lg border border-[var(--status-danger)] bg-[var(--badge-danger-bg)] px-3 py-2 text-sm text-[var(--badge-danger-fg)]">
          {error}
        </div>
      )}

      {adding && (
        <div className="mb-4 flex flex-wrap items-end gap-2 rounded-lg border border-[var(--border)] p-3">
          <label className="flex flex-col gap-1">
            <span className="text-xs text-[var(--text-secondary)]">品牌</span>
            <input
              list="brand-options"
              value={newBrand}
              onChange={(e) => setNewBrand(e.target.value)}
              placeholder="如 Chatlock"
              className="w-44 rounded-md border border-[var(--border)] bg-[var(--bg-surface)] px-2 py-1.5 text-sm"
            />
            <datalist id="brand-options">
              {KNOWN_BRANDS.map((b) => (
                <option key={b} value={b} />
              ))}
            </datalist>
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-xs text-[var(--text-secondary)]">認證到期日（可留空）</span>
            <input
              type="date"
              value={newExpiry}
              onChange={(e) => setNewExpiry(e.target.value)}
              className="rounded-md border border-[var(--border)] bg-[var(--bg-surface)] px-2 py-1.5 text-sm"
            />
          </label>
          <button
            type="button"
            disabled={!newBrand.trim() || busy !== null}
            onClick={() => grant(newBrand, newExpiry)}
            className="rounded-md bg-[var(--primary)] px-3 py-1.5 text-sm font-semibold text-white disabled:opacity-50"
          >
            {busy ? "處理中…" : "授權"}
          </button>
          <button
            type="button"
            onClick={() => { setAdding(false); setNewBrand(""); setNewExpiry(""); }}
            className="rounded-md border border-[var(--border)] px-3 py-1.5 text-sm text-[var(--text-secondary)]"
          >
            取消
          </button>
        </div>
      )}

      {loading ? (
        <p className="py-6 text-center text-sm text-[var(--text-secondary)]">載入中…</p>
      ) : active.length === 0 ? (
        <p className="py-6 text-center text-sm text-[var(--text-secondary)]">
          尚未授權任何品牌 —— 派工閘門啟用後，此技師不會出現在任何品牌的候選集。
        </p>
      ) : (
        <div className="flex flex-col divide-y divide-[var(--border)]">
          {active.map((r) => (
            <div key={r.brand} className="flex items-center gap-4 py-3">
              <div className="flex-1">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium text-[var(--text-primary)]">{r.brand}</span>
                  {isExpired(r.cert_expires_at) && (
                    <span className="rounded-full bg-[var(--badge-danger-bg)] px-2 py-[2px] text-[11px] font-medium text-[var(--badge-danger-fg)]">
                      認證已過期
                    </span>
                  )}
                </div>
                <span className="text-xs text-[var(--text-secondary)]">
                  {r.cert_expires_at ? `認證到期 ${r.cert_expires_at}` : "無到期限制"}
                </span>
              </div>
              <button
                type="button"
                disabled={busy === r.brand}
                onClick={() => revoke(r.brand)}
                aria-label={`撤銷 ${r.brand} 授權`}
                className="flex items-center gap-1 rounded-md border border-[var(--border)] px-2.5 py-1.5 text-xs text-[var(--status-danger)] transition hover:bg-[var(--badge-danger-bg)] disabled:opacity-50"
              >
                <Trash2 className="h-3.5 w-3.5" aria-hidden />
                {busy === r.brand ? "處理中…" : "撤銷"}
              </button>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
