# Casdoor 第三方登入(Google / LINE)開通 Runbook

- **日期**:2026-07-16(20260715 會議 16.5.2:鎖匠端支援 Google、LINE 等第三方登入)
- **現況**:bootstrap 已支援(env-gated,未設憑證=零行為變化);**缺的只有兩組憑證**
- **定位**:第三方僅作**登入方式**(`canSignUp=False`)——技師開帳仍走 KYC 註冊審核,
  不允許純第三方自動開帳;Email/密碼登入照常並存

---

## 一、要申請的兩組憑證(可先送件,等待期最長的一步)

### 1. Google OAuth Client

1. [Google Cloud Console](https://console.cloud.google.com/apis/credentials) → 選/建專案
   → 「建立憑證」→「OAuth 用戶端 ID」→ 類型「網頁應用程式」
2. **已授權的重新導向 URI** 填 **Casdoor 的 callback**(不是我們站台的):
   - 本機:`http://localhost:8005/callback`
   - 雲端:`https://<casdoor-正式網域>/callback`
3. 若首次使用需先設定「OAuth 同意畫面」(External、App 名稱、支援信箱)
4. 產出:**Client ID + Client Secret**

### 2. LINE Login Channel

1. [LINE Developers Console](https://developers.line.biz/console/) → Provider
   →「Create a new channel」→ 類型選 **LINE Login**(⚠ 不是 Messaging API;
   與客服 bot 的 channel 是兩回事)
2. Callback URL 同上填 Casdoor callback:
   - 本機:`http://localhost:8005/callback`
   - 雲端:`https://<casdoor-正式網域>/callback`
3. 上線前 channel 要從 Developing 切 **Published**(否則只有測試名單能登)
4. 產出:**Channel ID(=Client ID)+ Channel Secret**

## 二、憑證到手後,一條指令開通

```bash
POSTGRES_URI="postgresql://lock:0000@localhost:5433/lock_AI_data" \
CASDOOR_GOOGLE_CLIENT_ID="<Google Client ID>" \
CASDOOR_GOOGLE_CLIENT_SECRET="<Google Client Secret>" \
CASDOOR_LINE_CLIENT_ID="<LINE Channel ID>" \
CASDOOR_LINE_CLIENT_SECRET="<LINE Channel Secret>" \
  uv run python scripts/idp/casdoor_bootstrap.py
```

冪等:重跑只更新憑證,不會重複建。只申請到其中一家也行(另一家自動跳過)。
機密規則照舊:憑證放 `.env` / Secret Manager,**不入 git、不入 toml**。

## 三、驗證(E2E)

1. 開 Casdoor 登入頁(`http://localhost:8005`,或走師傅站 SSO 鈕轉入)
   → 登入表單下方應出現 **Google / LINE 圖示按鈕**
2. 點 Google → Google 帳號授權 → 導回 Casdoor → 完成登入
3. 點 LINE → LINE 授權 → 同上
4. 綁定語意:第三方 email 與既有 Casdoor 使用者相同 → 視為同一人登入;
   查無帳號 → 因 `canSignUp=False` 會被擋(引導走 `/tech-register` KYC 註冊)

## 四、備註

- **師傅站 SSO 鈕顯示前提**:tech web build 要帶 `NEXT_PUBLIC_CASDOOR_ENDPOINT`
  (目前本機 build 未帶,鈕隱藏——屬站台 build 參數,與本 runbook 的 provider 開通互相獨立)
- **prod 憑證是另一組**:redirect URI 網域不同,Google/LINE 都要各申請或在同
  console 補正式 redirect;切勿把 dev 憑證帶上 prod
- 「LINE Login(本 runbook)」與「LINE Messaging API(客服 bot / 未來師傅推播)」
  是不同 channel 類型,互不影響
