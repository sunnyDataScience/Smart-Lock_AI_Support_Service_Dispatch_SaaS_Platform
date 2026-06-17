---
adr_id: ADR-0114
title: 使用者自助忘記密碼 — Email 送達 + 一次性 reset token
status: accepted
date: 2026-06-17
deciders: Sunny（業主）
related: [CR-0025]
supersedes_decision: "2026-06-10 會議 Action #7（免 email、僅 admin 代重設）之『不建自助』部分"
tags: [auth, password-reset, email, security, cr-0025]
---

# ADR-0114 — 使用者自助忘記密碼（Email + 一次性 token）

## Context

原認證只有：`login` / `refresh` / `logout` / `changePassword`（需登入）/ `adminResetPassword`
（需另一已登入 admin 代為重設、回明文臨時密碼、**免 email**）。後者是 2026-06-10 會議
Action #7 為閃避「無寄信基礎建設」而採的方案。

衍生兩個問題（CR-0025 §1）：
1. 兩個登入頁缺自助忘記密碼入口（`/tech-login` 只有不可點提示、`/login` 完全沒有），不符使用者預期。
2. **雞生蛋**：唯一 admin 忘記密碼時，`adminResetPassword` 無人可操作。

> 立場留痕：2026-06-10 會議 Action #7 拍板「不建自助、僅 admin 代重設」；業主 2026-06-17
> 裁決**改為支援自助**（CR-0025 §8）。本 ADR 記錄此覆蓋與最終設計。Action #7 的
> `adminResetPassword` **保留為後備**，非廢除。

## Decision

採 CR-0025 §8 全部裁決：

1. **送達管道 = Email**（Q1=a）。staff 與技師都有 email、都用 email 登入，單一管道涵蓋兩端，
   並順解 admin 雞生蛋（Q3=a，admin 可自助；seed/DB 仍為終極 break-glass）。
2. **寄信抽象化**：新增 `EmailProvider` 介面，預設 **SMTP** 實作（可配 SendGrid/SES SMTP
   endpoint），透過 env/secret 設定 —— **不綁單一 vendor、不把 SDK import 散落**。
3. **流程**：`POST /auth/request-password-reset {email}` → 簽發**高熵 token，只存雜湊**於
   新表 `password_reset_tokens`，寄出含 token 的連結 → `POST /auth/confirm-password-reset
   {token, new_password}` 驗證（未過期/未用）→ 改密碼 + 標 token used + **撤銷該 user 既有
   refresh token**。
4. **Token**：TTL **30 分鐘、單次用**（Q4）。
5. **帳號枚舉防護**：request **一律回 200**「若帳號存在已寄出」（Q6），不洩漏帳號是否存在。
6. **email 未驗證**：接受現狀，首次重設視同驗證（Q5）；完整 email 驗證另開 CR。
7. **範圍**：`/login`（管理員）+ `/tech-login`（技師）兩頁都加可點「忘記密碼」+ 重設頁（Q2）。
8. **rate limit**：per-email + per-IP 節流，防洗 request 灌信。

## Consequences

- ✅ 兩登入頁體驗一致、符合慣例；admin 雞生蛋解除。
- ✅ token 只存雜湊 + 短 TTL + 單次用 + confirm 後撤 refresh → 降外洩/重放風險。
- ✅ EmailProvider 抽象 → 換 vendor 不動 service；架構鎖（agent/lockcore）不受影響（此為 api 範圍）。
- ⚠️ **新外部相依**：prod 需配 SMTP/provider secret，deploy 腳本要接線；未配置時 request-reset
  須 fail-safe（記錄並回 200，不可 500 洩漏）。
- ⚠️ email deliverability 風險（垃圾桶/未送達）→ 選信譽 provider、小範圍先測。
- ⚠️ users email 未驗證 → 寄錯信箱風險；首次重設後標記已驗證為緩解。
- `adminResetPassword` 保留為後備（離線/緊急），不廢除。
