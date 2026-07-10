# CR-0146 — OIDC 授權碼流 web 接線(WBS 2.1.1-R2)

- **日期**:2026-07-10
- **觸發面向**:User flow(登入)、External integration(Casdoor 授權碼流)
- **依據**:ADR-024(薄回調,無 BFF)、CR-0141 R1(api 雙驗+cookie 來源)、13_Security ACT-01

## §1 交付(brand-portal 參考實作)

1. `/auth/callback` route handler(ADR-024 唯一 server-side 認證點):code→token(server-side client_secret)、寫 httpOnly cookie `smartlock_access_token`(SameSite=Lax;api R1 已支援 cookie 來源)、token 經 fragment 交 `/auth/sso-complete`
2. `/auth/sso-complete`:fragment→localStorage(**過渡雙寫**——既有 30+ 頁同步 getCurrentSession 依賴)→依角色導向
3. 登入頁 SSO 按鈕(`NEXT_PUBLIC_CASDOOR_ENDPOINT` 配置時顯示;redirect_uri client 端組——SSR 空值 bug 由 E2E 抓到並修)
4. AuthGuard 白名單 +/auth/sso-complete

## §2 live E2E 實證(Playwright,dev :3005 + 真 Casdoor :8005)

SSO 按鈕→Casdoor authorize(redirect_uri 正確)→ops 帳號(bcrypt 遷移密碼)登入→薄回調→**httpOnly cookie 已設(JS 不可讀 ✓)**+localStorage 雙寫→RS256 token 角色 operations_manager/租戶 0001 映射全對→自動導向 dashboard。

## §8/遺留(R3,業主排程)

1. **ACT-01 cutover**(localStorage 退場):getCurrentSession 同步→非同步改造波及 30+ 頁+5 fetch 攔截點+WS/SSE ticket+跨分頁登出 BroadcastChannel——UAT 前不宜自主硬切;13_Security ACT-01 Phase 標註矛盾(§7/§8.3=P2 vs §12=P1)一併裁決
2. 其餘三站接線=複製本參考實作(redirect URIs 已在 bootstrap 註冊);api 端 OIDC 啟用=部署配 CASDOOR_* env(opt-in)
3. prod cookie 需共用網域(localhost 憑 host 同名通行,雲端要 parent domain 或 BFF 化)

### 進度

- ✅ R2 done(2026-07-10,branch `feat/casdoor-oidc-web-r2`):live E2E 全通;tsc 0;build 綠(callback=ƒ/sso-complete=○)
