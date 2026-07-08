"use client";

/**
 * /admin/customers/[id]/edit — 編輯客戶頁面
 *
 * 對應 E7x §4.2 FE UI 缺口 — 客戶 admin 編輯表單。
 * 載入既有客戶資料 → 注入 CustomerForm 預填 → 提交時呼叫 PUT /api/v2/tenants/{tenantId}/customers/{id}。
 */

import { use, useEffect, useState } from "react";
import Sidebar from "@shared/components/layout/Sidebar";
import { CustomerForm, type CustomerFormInitial } from "@/components/admin/CustomerForm";
import { api, resolveTenantId } from "@shared/lib/api";
import { friendlyError } from "@shared/lib/apiError";

interface CustomerDetailLite extends CustomerFormInitial {
  id: string;
  display_name: string;
}

export default function EditCustomerPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const [initial, setInitial] = useState<CustomerFormInitial | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    (async () => {
      try {
        // CR-0002-α：遷移至 tenant-scoped v2 端點讀取客戶資料
        const tenantId = resolveTenantId();
        const res = await api.get<CustomerDetailLite>(
          `/tenants/${encodeURIComponent(tenantId)}/customers/${encodeURIComponent(id)}`,
        );
        if (cancelled) return;
        setInitial({
          display_name: res.display_name,
          phone: res.phone ?? null,
          // BE 是否回 email 待 endpoint 規格；先嘗試取，沒有就為空
          email: (res as unknown as { email?: string | null }).email ?? null,
          address: res.address ?? null,
        });
      } catch (e) {
        if (cancelled) return;
        setError(
          friendlyError(e),
        );
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [id]);

  return (
    <div className="flex h-full bg-[var(--bg-page)]">
      <Sidebar />
      <div className="flex flex-1 flex-col overflow-auto">
        {loading && (
          <div className="flex h-40 items-center justify-center text-[13px] text-[var(--text-secondary)]">
            載入客戶資料中…
          </div>
        )}
        {error && !loading && (
          <div className="mx-auto mt-8 max-w-2xl rounded-md border border-red-200 bg-red-50 px-4 py-3 text-[13px] text-red-700">
            {error}
          </div>
        )}
        {!loading && !error && initial && (
          <CustomerForm mode="edit" customerId={id} initial={initial} />
        )}
      </div>
    </div>
  );
}
