---
id: OPS-MONITORS-RUNBOOK
title: Background Monitors Runbook（8-monitor lifespan）
status: active
created_at: 2026-06-05
purpose: 給 ops / on-call 用的背景 worker 完整清單 + 故障排除 + 健康監測。
---

# Background Monitors Runbook

> Production 部署時 API service 啟動會自動掛 8 個背景 monitor / cron。
> 本 doc 給 ops / on-call 故障排除用。

## §1 8-Monitor 啟動序

```
inventory_monitor → sla_monitor → line_push_worker → recon_exc_detector
→ dispute_escalation_cron → canary_advance_cron
→ statement_auto_approval → gdpr_hard_delete
```

各 monitor 都是 in-process asyncio task，重啟即重新開始計時。

## §2 各 Monitor 詳細

| Monitor | 預設 interval | 用途 | Env override | 對應 FR/CR |
|:---|:---:|:---|:---|:---|
| `inventory_monitor` | 60s | 低庫存背景偵測 | — | v1.28.0 |
| `sla_monitor` | 60s | quote/dispatch/response/arrival 4 SLA 告警 | `SLA_MONITOR_INTERVAL_SECONDS` | v1.33.0 |
| `line_push_outbox_worker` | 10s | LINE Flex push outbox poll → push | `LINE_PUSH_WORKER_INTERVAL` | CR-0017 Stage 2 |
| `reconciliation_exception_detector` | 86400s (24h) | 對帳異常 daily 偵測（3 detector） | `RECON_EXCEPTION_DETECTOR_INTERVAL` | CR-0018 Stage 3 |
| `dispute_escalation_cron` | 86400s (24h) | 60d dispute 自動 escalation | `DISPUTE_ESCALATION_CRON_INTERVAL` | WBS §8 P1 |
| `config_canary_advance_cron` | 300s (5min) | M18 canary 5%→50%→100% 自動推進 | `CONFIG_CANARY_ADVANCE_INTERVAL` | WBS §8 P1 |
| `statement_auto_approval` | 3600s (1hr) | 3 statement 表 dispute window 過期 auto-approve | `STATEMENT_AUTO_APPROVAL_INTERVAL` | FR-0045/0046/0047 |
| `gdpr_hard_delete` | 86400s (24h) | T+30 GDPR forget 自動硬刪 (BR-PII-001) | `GDPR_HARD_DELETE_INTERVAL` | FR-0053 |

## §3 Health 即時查詢

```bash
curl -H "Authorization: Bearer $JWT" \
  https://api.example.com/api/v1/admin/lifespan-monitors/health
```

回應 example：

```json
{
  "monitors": {
    "inventory": {"state": "running", "interval_seconds": 60, ...},
    "sla": {"state": "running", "interval_seconds": 60, ...},
    "gdpr_hard_delete": {"state": "crashed", "task_done": true, ...}
  },
  "summary": {
    "total": 8,
    "by_state": {"running": 7, "crashed": 1},
    "all_running": false
  }
}
```

state 4 種：
- `running` — task active + stopping signal not set → 正常
- `stopping` — shutdown 進行中（lifespan stop）
- `crashed` — task done 但 stopping signal 未 set → **異常終止，需 restart API**
- `not_started` — task=None（應在 startup 完成後不該出現此狀態）
- `import_error` — module import 失敗（部署檔案損壞）

## §4 故障排除

### 4.1 single monitor crashed

| 症狀 | 可能原因 | 處置 |
|:---|:---|:---|
| `line_push_outbox_worker` crashed | LINE API quota 用罄 / 網路 | 查 LINE Console quota；restart API |
| `recon_exception_detector` crashed | 大 batch SQL 鎖住 | 查 active query；下次重啟後縮 batch |
| `gdpr_hard_delete` crashed | DELETE users FK constraint 衝突 | 查 error log 找具體 user_id；手動清 FK 再 restart |
| `statement_auto_approval` crashed | 三表之一 schema drift | 查 migration registry；補 missing migration |
| `canary_advance_cron` crashed | _dethrone_active 鎖等 | 查 config_version table；可能 race；restart |
| `dispute_escalation_cron` crashed | sla_deadline 欄位 NULL | 補 NULL → 正常時間；restart |

### 4.2 all_running=false 但個別 not import_error

```bash
# 跑健康查詢
curl ... /admin/lifespan-monitors/health

# 若 crashed → kubectl rollout restart 或 docker restart api container
# 重啟後 lifespan 重新啟動所有 monitor
```

### 4.3 一個 monitor 重複 crash

代表 root cause 未解；不要無限 restart，先：
1. 查 logger 對應 monitor name 的 ERROR/EXCEPTION
2. 看 §4.1 對應症狀處置
3. 若是 schema/data issue → 暫設 env 加大 interval 或 disable（修改 main.py lifespan 留待下次部署）

## §5 暫停 monitor 流程（如業務需要）

正常運維**不應暫停 monitor**；極端情況（e.g. DB 維護）：

1. 改 env 把 interval 設極大值（e.g. `GDPR_HARD_DELETE_INTERVAL=999999999`）
2. 重啟 API container
3. monitor 仍會跑 startup_delay 後等 sleep，實質暫停
4. DB 維護完後 reset env + restart

## §6 多 worker / 多 instance 部署考量

| 風險 | 影響 | 緩解 |
|:---|:---|:---|
| `line_push_outbox_worker` 多 instance 同時 poll 同 row | 重複 push | 已用 `FOR UPDATE SKIP LOCKED` |
| `gdpr_hard_delete` 多 instance 同時 SELECT | 同 row 跑兩次 hard_delete | service 內已有 status='soft_deleted' CAS；下次跑時 status 已 hard_deleted 自動跳過 |
| `statement_auto_approval` 多 instance | 同 statement UPDATE 兩次 | WHERE status='pending_review' 條件冪等；第二次 affected=0 |
| `canary_advance_cron` 多 instance | 同 rollout advance 兩次 | UPDATE WHERE current_stage 條件；CAS 第二次無效 |
| `*_detector` / `*_escalation` | 重複偵測 | service 內 detect_exception 有 idempotent check |

**結論**：本 session 所有新 monitor 都已設計成 multi-instance safe；舊 `inventory_monitor` / `sla_monitor` 使用 in-memory `_alerted` set，多 instance 重複告警。**建議**：production 部署 API container = 1 instance；scale 由 load balancer 前置。

## §7 lifespan startup 失敗

若 startup 任一 monitor `.start()` 拋 exception → API 整個 startup fail 不能服務。

排除：
1. 看啟動 log 哪個 module import fail
2. 通常為 migration 未跑 / env 缺
3. 確認 `pending-apply` migration 都套用（`SQL/migrations/MIGRATION_REGISTRY.md`）

## §8 相關文件

- `api/routers/lifespan_health.py` — 本 endpoint 實作
- `api/realtime/*` — 各 monitor 實作
- `SQL/migrations/MIGRATION_REGISTRY.md` — 對應 schema 變更
- `CHANGELOG.md [Unreleased] Decisions` — 各 monitor 加入歷史
