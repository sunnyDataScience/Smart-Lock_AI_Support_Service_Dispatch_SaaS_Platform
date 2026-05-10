---
title: Security Checklist — OWASP Top 10 + Pen Test Scope
phase: V-MODEL RIGHT (System Test, security dimension)
gate: TR5 / TR7
status: Initial Content (待 SME 補充細節)
last_updated: 2026-05-07
owners: [Security Lead, Tech Lead]
status: superseded
superseded_by: docs_v2/3-process/security-readiness-checklist.md (appendix)
superseded_at: 2026-05-10
supersede_cr: CR-0007
---

# Security Checklist — OWASP Top 10 + Pen Test Scope

> **狀態**: 骨架文件（SKELETON）— OWASP 對照表 + 工具列表就位，SEC-NNN 細節與 pen test scope 待 Security Lead 補。

---

## §0 Purpose

補齊 V-Model 右翼 **資安測試** 覆蓋率（**40% → 90%**），對應：

- **ISO/IEC 25010**: Security（Confidentiality / Integrity / Non-repudiation / Accountability / Authenticity）
- **OWASP Top 10 (2021)**: 業界主流網頁應用風險清單
- 雙北極星 → `north-star-requirements.md` 的 `COM-001`（PII 保護）/ `COM-002`（稽核）

資安測試與功能測試的關鍵差異 — **不是驗證系統「會做什麼」，而是驗證系統「不會被誘導做什麼」**。

---

## §1 OWASP Top 10 (2021) Coverage Matrix

| OWASP # | 風險 | 對應 SEC-NNN | 影響端點 | Status |
| :--- | :--- | :--- | :--- | :--- |
| A01 | Broken Access Control | SEC-001 RBAC 權限繞過 + IDOR | all `admin/*`、`/work-orders/{id}`、`/refunds/{id}` | ⚠ TBD |
| A02 | Cryptographic Failures | SEC-002 PII 加密（at-rest + in-transit） + Webhook HMAC | DB（users / conversations / addresses）、`/webhook` | ⚠ TBD |
| A03 | Injection | SEC-003 SQL injection / XSS / NoSQL injection | `/search/*`、`/conversations?q=`、所有自由文字輸入 | ⚠ TBD |
| A04 | Insecure Design | SEC-004 Threat modeling per feature | F-011 / F-014 金流、F-019 RBAC、F-020 audit | ⚠ TBD |
| A05 | Security Misconfiguration | SEC-005 默認密碼 + 公開 endpoint 列表審計 | Cloud Run env、Secret Manager、CloudSQL | ⚠ TBD |
| A06 | Vulnerable & Outdated Components | SEC-006 Dependency audit（npm audit / pip audit / trivy） | package-lock.json / poetry.lock / Docker image | ⚠ TBD |
| A07 | Identification & Authentication Failures | SEC-007 JWT 驗證 + session fixation + brute force lockout | `/auth/*`、admin login | ⚠ TBD |
| A08 | Software & Data Integrity Failures | SEC-008 Webhook signature 驗證 + signed token | `/webhook`、Q3=C anonymous Web token、Q9=B scope-change token | ⚠ TBD |
| A09 | Security Logging & Monitoring Failures | SEC-009 audit log 完整性 + 防篡改 | audit_logs 表、所有寫入操作 | ⚠ TBD |
| A10 | Server-Side Request Forgery (SSRF) | SEC-010 GCS / Vertex API call URL validation | webhook receivers、url preview、image fetch | ⚠ TBD |

**規範**：
- 每個 OWASP 類別至少 1 條 SEC-NNN；A01 / A03 / A07（最高風險）至少 3 條
- `Status` 用語同 north-star（✅ Live / 🚧 In Dev / ⚠ TBD / ❌ Deferred）

---

## §2 Pen Test Scope — 2026-Q3 計畫

外部滲透測試規劃（待 Security Lead 確認 vendor）：

| 範圍 | 內容 | 優先級 |
| :--- | :--- | :--- |
| **Web Admin** | OWASP Top 10 全項 + a11y intake | P0 |
| **LINE Bot Webhook** | webhook 簽章驗證、replay attack、payload 注入 | P0 |
| **Tech Mobile App** | API 端 + 行動端 binary 反編譯風險 | P1 |
| **Internal API** | 內網橫向移動、service-to-service auth | P1 |
| **Cloud Infra** | GCP IAM、Secret Manager 權限矩陣 | P0 |

**時程**：2026-Q3（具體日期待 Security Lead 與 vendor 簽約後確認）

**TBD**：
- [ ] Vendor 選定（短名單：TBD）
- [ ] 報告交付格式（CVSS 3.1 計分）
- [ ] 修復 SLA（Critical: 7d / High: 30d / Medium: 90d）

---

## §3 Threat Model

威脅模型分三類：

### 3.1 External Threats
- 公開網路攻擊者（LINE webhook / web admin login）
- 對應防禦：WAF、rate limiting、CSP、HSTS

### 3.2 Internal Threats
- 惡意 / 失誤的內部人員（含技師、客服、admin）
- 對應防禦：least privilege、audit_logs、雙簽（COM-002）

### 3.3 Supply Chain Threats
- 依賴套件污染（npm / PyPI）、CI/CD pipeline 入侵
- 對應防禦：lock file 必提交、trivy 掃描、sigstore 簽章（規劃中）

---

## §4 SEC-NNN Matrix

| SEC-ID | OWASP # | 場景 | 工具 | 對應 COM-NNN | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| SEC-001 | A01 | 一般使用者帳號嘗試呼叫 `/admin/*`；技師 A 嘗試讀取技師 B 的 WO（IDOR） | Burp Suite + custom script | COM-002 | ⚠ TBD |
| SEC-002 | A02 | DB dump 後 PII 欄位（手機 / 地址）是否加密；TLS 強制（HSTS preload） | manual DB inspect + sslyze | COM-001 / COM-003 | ⚠ TBD |
| SEC-003 | A03 | 搜尋 / 自由文字端點 payload 注入（UNION SELECT、`<script>`、$where） | sqlmap + Burp + DOMPurify check | — | ⚠ TBD |
| SEC-004 | A04 | F-011 金流流程 threat modeling（STRIDE）；確認無設計層繞過 | manual review + STRIDE workshop | COM-005 | ⚠ TBD |
| SEC-005 | A05 | Cloud Run env vars 無洩漏；公開 endpoint 列表須白名單；無默認帳密 | gcloud audit + nmap | — | ⚠ TBD |
| SEC-006 | A06 | npm audit / pip audit / trivy 掃描，CRITICAL/HIGH 漏洞 0 容忍 | npm audit + pip-audit + trivy | — | ⚠ TBD |
| SEC-007 | A07 | 密碼錯誤 N 次後 lockout；JWT exp / iss / aud 驗證；session fixation | k6 brute force + custom JWT fuzz | — | ⚠ TBD |
| SEC-008 | A08 | LINE webhook HMAC-SHA256 驗證；Q3=C / Q9=B signed token 防偽造 + 過期 | curl + custom signer | COM-004 | ⚠ TBD |
| SEC-009 | A09 | 模擬寫入操作後檢查 audit_logs 完整性（無漏記、無篡改）；alert 觸發測試 | DB inspect + log diff | COM-002 | ⚠ TBD |
| SEC-010 | A10 | GCS / Vertex API URL validation；阻止內網 metadata endpoint（169.254.169.254）存取 | OWASP ZAP + custom payload | — | ⚠ TBD |

**規範**：
- ID 格式：`SEC-NNN`
- 每筆 SEC 必須註明對應 OWASP 編號；涉合規者必須對應 COM-NNN

---

## §5 Tooling

| 工具 | 用途 | 已建置? |
| :--- | :--- | :--- |
| **gitleaks** | secret scan（pre-commit + CI） | TBD |
| **trivy** | 容器映像 + 依賴漏洞掃描 | TBD |
| **axe-core** | 網頁 a11y（WCAG 2.1 AA） | TBD |
| **Burp Suite** | 手動 pen test（A01 / A03 / A07） | TBD（pen test 階段） |
| **sqlmap** | SQL injection 自動化 | TBD |
| **OWASP ZAP** | DAST 動態掃描（CI 整合） | TBD |

CI 整合（規劃）：
- pre-commit: gitleaks
- on PR: trivy + axe-core + ZAP baseline scan
- nightly: full ZAP active scan

---

## §6 Change Log

| 日期 | 版本 | 變更內容 | 作者 |
| :--- | :--- | :--- | :--- |
| 2026-05-07 | 0.1.0 | 骨架建立 | Claude / Security Lead |
| 2026-05-07 | 0.2.0 | Initial Content：OWASP A01~A10 全 10 項對照 + SEC-001~010 場景填入 | Claude |
| TBD | 0.3.0 | Pen test vendor 簽約 + scope 定稿 | Security Lead / 法務 |
| TBD | 0.4.0 | 第一次 pen test 結果 + 修復追蹤 | Security Lead |
