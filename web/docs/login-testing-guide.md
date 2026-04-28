# `/login` 頁面測試手冊

本文件說明如何在本機驗證 SmartLock Admin 的登入流程。

---

## 前置環境

確認以下兩個服務都跑著：

| 服務 | URL | 啟動方式 |
| :--- | :--- | :--- |
| 後端 API（Docker） | `http://localhost:8001` | `docker ps` 應看到 `smart-lock-api` |
| 前端 dev server | `http://localhost:3000` | `cd web && npm run dev` |

健康檢查：

```bash
curl http://localhost:8001/health
# 應回 {"status":"ok","version":"0.2.0","checks":{"db":"ok"}}
```

測試帳號（種子資料）：

- Email：`admin@example.com`
- 密碼：`changeme123`

---

## 測試步驟

### 1. 未登入自動跳轉

1. 開啟瀏覽器 DevTools → **Application** → **Local Storage** → `http://localhost:3000` → 右鍵 **Clear**
2. 網址列輸入 `http://localhost:3000/dashboard`
3. **預期：** 自動跳轉到 `http://localhost:3000/login`，畫面顯示登入表單

### 2. 登入失敗（顯示錯誤）

1. 在 `/login` 表單輸入：
   - Email：`admin@example.com`
   - 密碼：`wrongpw`
2. 點「登入」
3. **預期：** 表單下方顯示紅色 alert，內容類似：
   ```
   INVALID_CREDENTIALS (401)：Invalid email or password
   ```
4. 仍停留 `/login`，localStorage 仍是空的

### 3. 登入成功（寫入 token）

1. 改輸入正確帳密：
   - Email：`admin@example.com`
   - 密碼：`changeme123`
2. 點「登入」
3. **預期：**
   - 自動跳轉到 `/dashboard`
   - DevTools → Application → Local Storage 看到：
     - `smartlock.access_token`：JWT 字串（`eyJ...`）
     - `smartlock.refresh_token`：JWT 字串
4. 重新整理頁面 → 仍停在 `/dashboard`（token 持久化生效）

### 4. 已登入訪問 `/login` 自動轉回

1. 維持登入狀態
2. 網址列輸入 `http://localhost:3000/login`
3. **預期：** 自動跳回 `/dashboard`（不會看到登入表單）

### 5. 登出

1. 在任意已登入頁面（如 `/dashboard`），看左側 sidebar **左下角**：
   - 「王 / 王小明 / 主管理員」使用者區塊
   - 區塊右邊有一個 **登出 icon**（向右箭頭符號）
2. 點該 icon
3. **預期：**
   - 自動跳轉到 `/login`
   - localStorage 中 `smartlock.access_token` 與 `smartlock.refresh_token` 被清掉

### 6. 登出後保護仍生效

1. 登出後，網址列手動輸入 `http://localhost:3000/dashboard`
2. **預期：** 立即跳回 `/login`（AuthGuard 偵測沒有 token）

### 7.（選做）跨分頁登出同步

1. 開兩個分頁都登入後到 `/dashboard`
2. 在 A 分頁點登出
3. **預期：** B 分頁也自動跳到 `/login`（透過 `storage` event listener）

---

## 後端同步觀察

打開另一個 terminal 觀察後端 log：

```bash
docker logs -f smart-lock-api
```

對應請求：

| 動作 | 預期 log |
| :--- | :--- |
| 登入成功 | `POST /api/v1/auth/login 200` |
| 登入失敗 | `POST /api/v1/auth/login 401` |
| 登出 | `POST /api/v1/auth/logout 200` |
| 自動 refresh（401 後重試） | `POST /api/v1/auth/refresh 200` |

---

## 常見問題排查

### 跳轉沒有發生 / 一直白屏

- 開 DevTools → Console，看是否有紅色錯誤
- 確認 `web/.env.local` 有設定 `NEXT_PUBLIC_API_BASE_URL=http://localhost:8001`
- 確認後端 Docker 容器在跑：`docker ps | grep smart-lock-api`

### 登入按鈕無反應

- DevTools → Network 面板，看 `/api/v1/auth/login` 請求是否發出
- 若是 CORS 錯誤：檢查後端 `api/config.toml` 的 CORS 設定是否包含 `http://localhost:3000`

### 登入後沒跳轉但 token 已寫入

- 重新整理頁面，若能進 `/dashboard` 就是 router.replace 的時序問題
- 檢查 `web/src/app/login/page.tsx:24` 是否正確 await `login()` 後再 `router.replace`

### `/dashboard` 一直跳回 `/login`，但 token 已存在

- DevTools → Application → Local Storage 確認 key 是 `smartlock.access_token`（不是 `access_token`）
- 檢查 `web/src/lib/api.ts:19-23` 的 `STORAGE_KEYS` 與 `auth.getAccessToken()` 一致

---

## 涉及檔案

| 檔案 | 角色 |
| :--- | :--- |
| `web/src/app/login/page.tsx` | 登入表單 UI 與 submit handler |
| `web/src/app/login/layout.tsx` | `/login` 用的 layout（不顯示 Sidebar） |
| `web/src/components/layout/AuthGuard.tsx` | client-side 路由守衛 |
| `web/src/components/layout/Sidebar.tsx` | 登出按鈕所在處 |
| `web/src/app/layout.tsx` | root layout，包入 `<AuthGuard>` |
| `web/src/lib/api.ts` | `login()` / `logout()` / `auth` token helpers |

---

## 後端 endpoints

| Method | Path | 用途 |
| :--- | :--- | :--- |
| POST | `/api/v1/auth/login` | 帳密登入，回傳 access + refresh token |
| POST | `/api/v1/auth/refresh` | 用 refresh token 換新 access token |
| POST | `/api/v1/auth/logout` | 撤銷 refresh token |

完整契約見 `docs/02-design/specs/openapi.yaml`。
