"use client";

/**
 * /admin/customers/new — 新增客戶頁面
 *
 * 對應 E7x §4.2 FE UI 缺口 — 客戶 admin 新增表單。
 * 邏輯與表單欄位封裝於 CustomerForm。
 */

import Sidebar from "@shared/components/layout/Sidebar";
import { CustomerForm } from "@/components/admin/CustomerForm";

export default function NewCustomerPage() {
  return (
    <div className="flex h-full bg-[var(--bg-page)]">
      <Sidebar />
      <div className="flex flex-1 flex-col overflow-auto">
        <CustomerForm mode="create" />
      </div>
    </div>
  );
}
