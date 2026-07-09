# CR-0133: 對話三方全量存檔驗證＋失敗告警（WBS 1.2.4 / BR-Conv-004 / FR-AGT-09）

- **日期**: 2026-07-09
- **狀態**: done
- **觸發面向**: 資料完整性驗證（知識精煉閉環第一類輸入）、agent 通道韌性
- **上游正典**: BR-Conv-004（三方全量存檔＋失敗告警不得靜默遺失）、FR-AGT-09（接管期間零缺漏）、04_SRS §2.1 Message

## §1 現況查證（多數鏈路已存在，本輪補「不得遺失」與驗證）

- ✅ 方案 A 旁路持久化：agent gateway `_persist_turn_safe` → `/internal/conversations/ingest`
  （客戶＋AI 每輪入庫，internal token 認證）。
- ✅ 接管期間：gateway 接管分支逐則持久化客戶訊息（AI 暫停仍入庫）；真人小編
  `send_message` 同表寫入（metadata.sender_role=agent_human＋sender_id 稽核）。
- ❌ **寫入失敗＝warning log 後直接遺失**（違反 BR-Conv-004「須告警不得靜默遺失」）→ 本輪修。

## §2 落地內容

1. **失敗告警升級＋spool 補送**（agent `line_gateway.py`）：ingest 失敗 →
   `[ARCHIVE_ALERT]` **ERROR 級**（雲端 alerting 依 severity 掛規則）＋批次落本機
   spool（jsonl，`PERSIST_SPOOL_PATH`，上限 500 防爆量、超限丟最舊並告警）；
   每次持久化前先補送 spool（成功移除、失敗保留）——實例存活期間零缺漏，
   fire-and-forget 語意不變（絕不影響客人回覆）。
2. **驗證測試**：
   - api（test_cr_0133）：一輪 AI 對話→接管→接管期客戶訊息→真人回覆＝四筆全入庫、
     `sender_role` 依序正確、接管期客戶零缺漏；sender_role 可過濾（精煉前提）。
   - agent（test_line_gateway 增 2）：失敗→spool→恢復補送清空；spool 上限丟最舊。

## §8 備註

- `sender_role` 值域映射：code 存 `line_user`/`ai`/`agent_human`/`system` ≡ SRS 語彙
  `customer`/`ai_agent`/`human_agent`——歷史資料在庫，改值需 messages metadata 遷移，
  收益低；以本 CR 記載映射為準（18_DB 已列 code 值域）。
- spool 位於容器檔案系統：Cloud Run 重啟即失——僅覆蓋「API 暫時不可達」情境；
  跨重啟 durability 屬 1.3.1+（外部 queue）範疇，記遺留。

## §9 驗收

api component **902 passed**（新 2 項）；agent **162 passed**（新 2 項）。
