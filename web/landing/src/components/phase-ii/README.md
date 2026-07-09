# Phase II 9 FR — Web Sprint Pre-build Assets

> Sprint 1-5 BUILD 前先 import 本目錄，不要自己 reinvent type/label/fetch wrapper。

## 結構

```
phase-ii/
  ├── types.ts        — 9 FR response shape + 共用 status enum + decimal-string convention
  ├── labels.ts       — 繁中 label + badge color + formatDecimal/formatDateTime/daysUntilDeadline helper
  ├── api-client.ts   — tenant-scoped fetch wrapper + 9 FR namespace (PhaseIIApi.xxx)
  ├── index.ts        — barrel export
  └── README.md       — 本檔
```

## 對應 backend

| Web export | Backend service | Endpoint prefix |
|---|---|---|
| `PhaseIIApi.approvalInbox` | `api/services/approval_inbox_service.py` | `/tenants/{tid}/approval-inbox` (FR-0049) |
| `PhaseIIApi.technicianLifecycle` | `api/services/technician_lifecycle_service.py` | `/tenants/{tid}/technicians/{id}/...` (FR-0044) |
| `PhaseIIApi.techStatement` | `api/services/technician_statement_service.py` | `/tenants/{tid}/me/statements` (FR-0045) |
| `PhaseIIApi.dispatcherCommission` | `api/services/dispatcher_commission_service.py` | `/tenants/{tid}/me/commission-statements` (FR-0046) |
| `PhaseIIApi.brandB2B` | `api/services/brand_b2b_statement_service.py` | `/tenants/{tid}/brand-b2b-statements` (FR-0047) |
| `PhaseIIApi.gdprForget` | `api/services/gdpr_forget_service.py` | `/tenants/{tid}/gdpr/forget-requests` (FR-0053) |
| `PhaseIIApi.aiGovernance` | `api/services/ai_governance_trace_service.py` | `/tenants/{tid}/ai/governance/...` (FR-0050) |
| `PhaseIIApi.sopFeedback` | `api/services/sop_feedback_service.py` | `/tenants/{tid}/sop-feedback` (FR-0051) |
| `PhaseIIApi.rmaQuality` | `api/services/rma_quality_service.py` | `/tenants/{tid}/rma/quality-findings` (FR-0048) |
| `PhaseIIApi.opsHealth` | `api/main.py` lifespan health | `/ops/lifespan-monitors` |

## 使用範例

### 範例 1：FR-0045 Tech statement page

```tsx
import {
  PhaseIIApi,
  type TechStatement,
  STATEMENT_STATUS_LABEL,
  STATEMENT_STATUS_COLOR,
  formatDecimal,
  formatDateTime,
  daysUntilDeadline,
} from "@/components/phase-ii";

function MyStatementsPage() {
  const opts = useApiOptions();           // baseUrl + tenantId + getAuthToken
  const [statements, setStatements] = useState<TechStatement[]>([]);

  useEffect(() => {
    PhaseIIApi.techStatement.myStatements(opts).then(setStatements);
  }, [opts]);

  return (
    <Table>
      {statements.map((s) => (
        <Row key={s.id}>
          <Badge color={STATEMENT_STATUS_COLOR[s.status]}>
            {STATEMENT_STATUS_LABEL[s.status]}
          </Badge>
          <Cell>{formatDecimal(s.net_amount)}</Cell>
          <Cell>{formatDateTime(s.dispute_window_ends_at)}</Cell>
          <Cell>
            剩 {daysUntilDeadline(s.dispute_window_ends_at) ?? "—"} 天
          </Cell>
        </Row>
      ))}
    </Table>
  );
}
```

### 範例 2：FR-0049 Admin Approval Inbox

```tsx
import {
  PhaseIIApi,
  type ApprovalInboxItem,
  APPROVAL_INBOX_TYPE_LABEL,
  SEVERITY_LABEL,
  SEVERITY_COLOR,
} from "@/components/phase-ii";

function ApprovalInboxPage() {
  const opts = useApiOptions();
  const [data, setData] = useState<Awaited<
    ReturnType<typeof PhaseIIApi.approvalInbox.list>
  > | null>(null);

  useEffect(() => {
    PhaseIIApi.approvalInbox.list(opts).then(setData);
  }, [opts]);

  if (!data) return <Spinner />;

  return (
    <>
      <h1>待處理 {data.total} 件</h1>
      <Tabs>
        {(Object.keys(data.by_type) as Array<keyof typeof data.by_type>).map((t) => (
          <Tab key={t}>{APPROVAL_INBOX_TYPE_LABEL[t]} ({data.by_type[t]})</Tab>
        ))}
      </Tabs>
      {data.items.map((it: ApprovalInboxItem) => (
        <Card key={it.id}>
          <Badge color={SEVERITY_COLOR[it.severity]}>
            {SEVERITY_LABEL[it.severity]}
          </Badge>
          <p>{it.summary}</p>
          <small>逾期 {it.days_overdue} 天</small>
        </Card>
      ))}
    </>
  );
}
```

### 範例 3：FR-0044 Technician suspend action

```tsx
import { PhaseIIApi, ApiError } from "@/components/phase-ii";

async function handleSuspend(technicianId: string) {
  try {
    const event = await PhaseIIApi.technicianLifecycle.suspend(
      opts,
      technicianId,
      { reason: "證照過期需停權", notes: "客戶投訴 #12345" },
    );
    toast.success(`已停權 (event ${event.id.slice(0, 8)})`);
  } catch (e) {
    if (e instanceof ApiError && e.status === 422) {
      toast.error(`狀態機不允許: ${(e.detail as any)?.detail}`);
    } else {
      toast.error("操作失敗");
    }
  }
}
```

## 共用約定

- **decimal**: backend 用 string 回傳 (e.g. `"50000.00"`)。前端用 `formatDecimal` 顯示，計算用 `Number()` 注意精度。
- **datetime**: backend 用 ISO 8601 string (含 timezone)。前端用 `formatDateTime` 顯示為本地短格式。
- **nullable**: backend 用 `null` 表示「未填」(不是 `""` 或 `0`)。前端統一 `value ?? "—"` 顯示。
- **狀態機 enum**: backend 用 lowercase string。前端用 `XXX_STATUS_LABEL[s.status]` 翻譯成繁中。
- **error**: 422 表業務邏輯 (狀態機/權限)；500 表系統錯。`ApiError.detail` 含 backend `{detail: "..."}` 結構。
- **auth**: `ClientOptions.getAuthToken` 由 caller 自己接 next-auth / Clerk / Auth0；wrapper 只負責注入 header。

## Sprint 1-5 對應 page

對齊 `docs/_ops/phase-ii-web-integration-plan.md` §4：

| Sprint | Page | 主要 export 用到 |
|---|---|---|
| **Sprint 1** | `app/admin/approval-inbox/page.tsx` (FR-0049) | `approvalInbox` + `APPROVAL_INBOX_TYPE_LABEL` + `SEVERITY_*` |
| **Sprint 2** | `app/admin/technicians/page.tsx` + `.../[id]/lifecycle/page.tsx` (FR-0044) | `technicianLifecycle` + `TECHNICIAN_STATUS_*` + `TECHNICIAN_LIFECYCLE_EVENT_LABEL` |
| **Sprint 3** | `app/account/statements/page.tsx` (FR-0045) + `app/account/commission-statements/page.tsx` (FR-0046) | `techStatement` + `dispatcherCommission` + `STATEMENT_STATUS_*` + `daysUntilDeadline` |
| **Sprint 4** | `app/admin/brand-b2b/page.tsx` (FR-0047) + `app/admin/gdpr-forget-queue/page.tsx` (FR-0053) | `brandB2B` + `gdprForget` + `B2B_DIRECTION_*` + `GDPR_*` |
| **Sprint 5** | `app/admin/ai-governance/page.tsx` (FR-0050) + `app/admin/sop-feedback/page.tsx` (FR-0051) + `app/admin/rma-quality/page.tsx` (FR-0048) | `aiGovernance` + `sopFeedback` + `rmaQuality` + 對應 label/color |

## 不在本目錄的責任

| Out-of-scope | 在哪裡解決 |
|---|---|
| React component skeleton (Badge, Countdown 等) | Sprint 各 page 自己用 shadcn 組 — 本目錄不綁 UI library |
| Auth / token 取得 | `useApiOptions()` hook 由 caller 自己寫接 next-auth / Clerk |
| Data fetching state (SWR/TanStack) | Sprint 自己包裝 — 本目錄純 fetch function |
| Routing | Next.js App Router — 本目錄不碰 |
| Form validation | Zod schema — Sprint 自己定 (本目錄 type 是 response shape，不是 form shape) |

## 變更注意

本目錄是 backend service 的 **type contract** 反映；backend service 改 response shape 就要同步改本目錄 type。建議：

1. Backend 改 service → 改 `types.ts` 對應 interface
2. 加新 endpoint → 加 `api-client.ts` namespace function
3. 加新 enum 值 → 加 `labels.ts` 對應 label/color (避免 page 跑 runtime crash)

對應 CR 與 traceability：見 `docs/_audit/phase-ii-9fr-complete-2026-06-05.md`。
