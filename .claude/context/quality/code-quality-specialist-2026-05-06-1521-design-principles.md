# R2 — 設計原則遵循度審查（程式碼品質審查官）

- **日期**: 2026-05-06 15:21
- **任務**: 審查 Linus 哲學 / SOLID / DRY / 不可變性 / 錯誤處理
- **範圍**: agent/harness/, agent/skills/, agent/profiles/, api/ 主 router/service
- **嚴重度**: CRITICAL
- **影響範圍**: code 重構（debounce.py 為頭號問題集中地）；docs（CLAUDE.md 鐵律與實作不一致需註記）

## 結論

### 核心發現
1. **`agent/harness/debounce.py` 是阻擋級問題集中地**：5 層縮排、11 elif 狀態機、mutable global buffer race、silent except 7 處 — 同時違反 CLAUDE.md 三大鐵律（不可變、無特殊情況、無靜默錯誤）
2. **PostgreSQL `_ensure_conn` 雙份重複**：profiles/manager.py:10-30 與 storage/postgres_impl.py:37-51 一字不差，加上 memory/postgres_saver.py:14 共 3 份
3. **`_extract_text` 重複 4 份**：debounce.py:66 / 124、memory_manager.py:19、quality/quality_check.py:404
4. **CLAUDE.md 鐵律違反**：
   - 「不可變性 (CRITICAL)」→ debounce.py 共享 dict 大量 mutate
   - 「絕不靜默吞噬錯誤」→ 至少 7 處 `except: pass` 無 log
   - 「函式 < 50 行、無深層巢狀 (>4 層)」→ debounce.py 多處 5 層、>100 行函式

### 違反清單

#### A. 三層縮排違反 Top 5
| 位置 | 函式 | 層數 |
|------|------|------|
| `harness/debounce.py:160-170` | `agent_and_reply` buffer 處理 | 5 |
| `harness/debounce.py:107-115` | `_format_buffer_for_log` | 5 |
| `skills/tools.py:100-115` | `load_skill` brand gate | 4 |
| `harness/debounce.py:880-907` | `add_to_buffer` | 4+ |
| `skills/__init__.py:118-125` | `load_skills` 載入迴圈 | 4 |

#### B. 特殊情況過多
| 位置 | 分支數 | 性質 |
|------|--------|-----|
| `harness/debounce.py` 全檔 11 elif | 11 | 爛品味（資料結構錯） |
| `harness/debounce.py:75-203` `_normalize_*` | 多處 isinstance 分支 | content block schema 不一致 |
| `api/services/notification_service.py` | 6 | 業務邏輯（可接受） |

#### C. DRY 違反
- PostgreSQL `_ensure_conn`：3 份重複（profiles/storage/memory）
- `_extract_text`：4 份重複
- `try: await conn.close(); except: pass`：3 處重複

#### D. 不可變性違反 Top 3
- `harness/debounce.py:888-907` user_buffers 巢狀 mutation（無鎖、跨 async race）
- `harness/debounce.py:619, 632` _pending_messages 模組級 mutable global
- `skills/__init__.py:122-124` Skill 物件 in-place 屬性賦值

#### E. 錯誤處理問題
**Silent except (CRITICAL)**：debounce.py:737-738/760-761、data_correction.py:34-35、storage/postgres_impl.py:49-50/153-154、profiles/manager.py:22-23、memory/sqlite_saver.py:22-23、api/core/db.py:33-34

#### F. docs 承諾 vs code 違反
| docs 段落 | docs 說 | code 違反 | 判決 |
|-----------|---------|----------|------|
| CLAUDE.md「不可變性 (CRITICAL)」 | 強制不可變 | debounce.py 大量 dict mutation | VIOLATION |
| CLAUDE.md「絕不靜默吞噬錯誤」 | 每層處理 | 7 處 except: pass | VIOLATION |
| CLAUDE.md「函式 < 50 行、>4 層巢狀禁」 | 硬上限 | debounce.py 多處超標 | VIOLATION |
| CLAUDE.md Linus「無特殊情況」 | 消除分支 | debounce.py 11 elif | VIOLATION |

### 嚴重度分級
- **CRITICAL: 2**（silent except 7 處、mutable global race）
- **HIGH: 4**（_ensure_conn DRY、_extract_text 重複、11 elif 狀態機、5 層縮排 5 處）
- **MEDIUM: 3**
- **LOW: 2**

## 行動項目

### 給 Wave 2（本次同步 docs）
- [ ] 在 docs/_audit/code-architecture-review 報告中明確標記「debounce.py 是 vibe-coded 頭號技術債」並列入重構優先清單
- [ ] docs 不需要因為 code 違反鐵律而修改鐵律（CLAUDE.md 鐵律是設計權威，code 違反是 code 的問題）
- [ ] docs 中如有「不可變設計」「無 silent error」承諾段落，保留不動（議長判決：docs 勝）

### 給後續 code 重構（不本次）
- [ ] 把 `agent/harness/debounce.py` 拆分為：
  - `harness/buffer.py`（純 BufferStore + dataclass + immutable replace）
  - `harness/quick_reply.py`（H_QR 獨立）
  - `harness/orchestrator.py`（agent_and_reply 編排核心）
- [ ] 抽 `agent/core/pg_pool.py` 統一管理 _ensure_conn（解 3 份重複）
- [ ] 抽 `agent/core/content_utils.py` 統一 `_extract_text`（解 4 份重複）
- [ ] 全面審查 silent except，每筆要有 log 或往上拋

## 影響評估

- **嚴重度**: CRITICAL
- **影響範圍**: code 端 debounce.py 是阻擋級重構候選；docs 端 CLAUDE.md 鐵律段落維持不變（議長判定）
