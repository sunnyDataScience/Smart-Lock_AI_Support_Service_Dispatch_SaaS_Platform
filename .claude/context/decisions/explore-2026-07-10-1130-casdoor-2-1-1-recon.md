# Explore 報告(2.1.1 Casdoor 開工查證)

- **日期**: 2026-07-10 11:30
- **任務**: 2.1.1 開工前 ADR/安全/認證面/租戶資料面查證(5 讀者 workflow)
- **範圍**: ADR-004/002/005/024、13_Security ACT-01、api 認證面、四站 token 面、License 資料面

## 結論

- ADR-004 自帶分段條款(L49):org+角色映射先行,License-gated provisioning 隨 ADR-002——R1/R2 切分的正典依據
- api 認證單一咽喉=deps.get_current_user(103 router 檔繫於此);token 全走 Bearer header,無 cookie
- web 面 ACT-01 量體:localStorage token、5 個 fetch 攔截點、30+ 頁前端解 JWT、WS/SSE query param、跨分頁 storage event——R2 專輪
- **Casdoor sub≠users.id**:身分映射必須走 user properties(smartlock_user_id/tenant_id/smartlock_role),bootstrap 寫入
- **平台庫 tenant.id≠品牌庫 tenant_id**(兩套 UUID 體系):token claims 用品牌庫 saas.tenant 的 id;平台庫只是註冊表(slug/plan)
- License 零資料面(tenant.plan 欄預留未用);13_Security 內 ACT-01 的 Phase 標註矛盾(§7/§8.3=P2,§12=P1 表)
- 埠位表:8000 agent/8001 dispatch-api/8002 tech-api/8003 platform-api → refinery 8004、casdoor 8005

## 行動項目

- [x] R1 落地(CR-0141):部署+bootstrap+api 雙驗+cookie 地基;live E2E 實證
- [ ] R2:四站授權碼流+ACT-01 cutover(薄回調 handler per ADR-024;WS ticket;BroadcastChannel 登出)
- [ ] test@lock-ai.com 雙 row 收斂一人一帳(admin row 被 Casdoor email 唯一性跳過)
- [ ] 13_Security ACT-01 Phase 標註矛盾隨 R2 銷案時統一
- [ ] prod:Casdoor HA/備份、admin 密碼換發、版本 pin(OPS)

## 影響評估

- **嚴重度**: HIGH(全站身分體系演進的地基)
- **影響範圍**: api 認證面(R1 完成,opt-in)、四站 web(R2)、2.1.2 自助開帳(依賴 R1 角色物件)
