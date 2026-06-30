"use client";

import { useEffect, useState } from "react";
import { Tag } from "lucide-react";
import Sidebar from "@/components/layout/Sidebar";
import { api, tenantPath } from "@/lib/api";
import { friendlyError } from "@/lib/apiError";
import { useTranslations } from "@/components/i18n/LocaleProvider";

interface Service {
  service_code: string;
  category: string;
  service_name: string;
  service_type: string;
  unit: string;
  internal_base_cost?: string | null;
  suggested_customer_price: string | null;
  decision_status: string;
  is_mock: boolean;
}
interface Material {
  material_code: string;
  category: string;
  material_name: string;
  unit: string;
  internal_cost?: string | null;
  suggested_price: string | null;
  decision_status: string;
}
interface Surcharge {
  rule_code: string;
  rule_type: string;
  rule_name: string;
  amount: string | null;
  value_text: string | null;
  decision_status: string;
}
interface Catalog {
  services: Service[];
  materials: Material[];
  surcharges: Surcharge[];
  cost_visible: boolean;
  note: string;
}

function price(v?: string | null): string {
  if (v == null) return "—";
  return `NT$ ${Math.round(parseFloat(v)).toLocaleString()}`;
}

export default function QuoteCatalogPage() {
  const t = useTranslations("admin.quoteCatalog");
  const [cat, setCat] = useState<Catalog | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await api.get<Catalog>(tenantPath("/quote-catalog"));
        if (!cancelled) setCat(res);
      } catch (e) {
        if (!cancelled) setError(friendlyError(e));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="flex h-full bg-[var(--bg-page)]">
      <Sidebar />
      <div className="flex flex-1 flex-col overflow-hidden">
        <div className="flex items-center gap-3 border-b border-[var(--border)] bg-[var(--bg-surface)] pl-14 pr-4 md:px-8 py-5">
          <Tag className="h-7 w-7 text-[var(--primary)]" />
          <h1 className="text-2xl font-bold text-[var(--text-primary)]">{t("title")}</h1>
          <span className="rounded bg-[#FEF3C7] px-2 py-[2px] text-[11px] text-[#92400E]">{t("mockBadge")}</span>
        </div>

        <div className="flex-1 overflow-auto pl-14 pr-4 md:px-8 py-6">
          {error && <div className="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>}
          {!cat ? (
            <p className="text-sm text-[var(--text-secondary)]">{t("loading")}</p>
          ) : (
            <div className="flex flex-col gap-8">
              {/* 服務 */}
              <Section title={t("services", { n: cat.services.length })}>
                <table className="w-full text-sm">
                  <thead className="bg-[#F8FAFC] text-xs text-[var(--text-secondary)]">
                    <tr>
                      <th className="px-3 py-2 text-left">{t("code")}</th>
                      <th className="px-3 py-2 text-left">{t("name")}</th>
                      <th className="px-3 py-2 text-left">{t("type")}</th>
                      {cat.cost_visible && <th className="px-3 py-2 text-right">{t("cost")}</th>}
                      <th className="px-3 py-2 text-right">{t("custPrice")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {cat.services.map((s) => (
                      <tr key={s.service_code} className="border-t border-[var(--border)]">
                        <td className="px-3 py-2 font-mono text-[12px] text-[var(--text-secondary)]">{s.service_code}</td>
                        <td className="px-3 py-2 text-[var(--text-primary)]">{s.service_name}</td>
                        <td className="px-3 py-2 text-[var(--text-secondary)]">{s.service_type}</td>
                        {cat.cost_visible && <td className="px-3 py-2 text-right font-mono text-[var(--text-disabled)]">{price(s.internal_base_cost)}</td>}
                        <td className="px-3 py-2 text-right font-mono font-medium text-[var(--text-primary)]">{price(s.suggested_customer_price)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </Section>

              {/* 材料 */}
              <Section title={t("materials", { n: cat.materials.length })}>
                <table className="w-full text-sm">
                  <thead className="bg-[#F8FAFC] text-xs text-[var(--text-secondary)]">
                    <tr>
                      <th className="px-3 py-2 text-left">{t("code")}</th>
                      <th className="px-3 py-2 text-left">{t("name")}</th>
                      {cat.cost_visible && <th className="px-3 py-2 text-right">{t("cost")}</th>}
                      <th className="px-3 py-2 text-right">{t("custPrice")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {cat.materials.map((m) => (
                      <tr key={m.material_code} className="border-t border-[var(--border)]">
                        <td className="px-3 py-2 font-mono text-[12px] text-[var(--text-secondary)]">{m.material_code}</td>
                        <td className="px-3 py-2 text-[var(--text-primary)]">{m.material_name}</td>
                        {cat.cost_visible && <td className="px-3 py-2 text-right font-mono text-[var(--text-disabled)]">{price(m.internal_cost)}</td>}
                        <td className="px-3 py-2 text-right font-mono font-medium text-[var(--text-primary)]">{price(m.suggested_price)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </Section>

              {/* 加價/取消費規則 */}
              <Section title={t("surcharges", { n: cat.surcharges.length })}>
                <table className="w-full text-sm">
                  <thead className="bg-[#F8FAFC] text-xs text-[var(--text-secondary)]">
                    <tr>
                      <th className="px-3 py-2 text-left">{t("ruleType")}</th>
                      <th className="px-3 py-2 text-left">{t("name")}</th>
                      <th className="px-3 py-2 text-left">{t("value")}</th>
                      <th className="px-3 py-2 text-left">{t("status")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {cat.surcharges.map((r) => (
                      <tr key={r.rule_code} className="border-t border-[var(--border)]">
                        <td className="px-3 py-2 text-[var(--text-secondary)]">{r.rule_type}</td>
                        <td className="px-3 py-2 text-[var(--text-primary)]">{r.rule_name}</td>
                        <td className="px-3 py-2 font-mono text-[var(--text-primary)]">{r.amount != null ? price(r.amount) : r.value_text}</td>
                        <td className="px-3 py-2">
                          <span className={`rounded px-2 py-[2px] text-[11px] ${r.decision_status === "已知規格" ? "bg-[#DCFCE7] text-[#15803D]" : "bg-[#FEF3C7] text-[#92400E]"}`}>
                            {r.decision_status}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </Section>

              <p className="text-[12px] text-[var(--text-disabled)]">{cat.note}</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="flex flex-col gap-2">
      <h2 className="text-base font-semibold text-[var(--text-primary)]">{title}</h2>
      <div className="overflow-hidden rounded-lg border border-[var(--border)] bg-[var(--bg-surface)]">{children}</div>
    </section>
  );
}
