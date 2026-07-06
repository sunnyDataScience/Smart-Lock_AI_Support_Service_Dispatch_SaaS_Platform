# `/login` 與 `/tech-login` 頁面測試手冊

本文件說明如何在本機驗證 SmartLock 兩個入口的登入流程：
- **`/login`** — 管理員後台（admin）
- **`/tech-login`** — 技師工作台（technician PWA）

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

### 測試帳號（種子資料）

#### Admin 後台
- Email：`admin@example.com`
- 密碼：`changeme123`
- 來源：`SQL/seeds/_admin_user.sql`

#### 技師端
- Email：`demo-tech@example.com`
- 密碼：`changeme123`
- 來源：`SQL/seeds/technicians.sql`
- 注意：`tech-chen@example.com`、`tech-huang@example.com` 是 placeholder hash，**無法登入**（用於展示列表，不用於 auth）

### 種子載入（如後端首次啟動）

```bash
psql $POSTGRES_URI < SQL/seeds/_admin_user.sql
psql $POSTGRES_URI < SQL/seeds/technicians.sql
```

---

## A. Admin `/login` 測試流程

### 1. 未登入自動跳轉

1. 開啟瀏覽器 DevTools → **Application** → **Local Storage** → `http://localhost:3000` → 右鍵 **Clear**
2. 網址列輸入 `http://localhost:3000/dashboard`
3. **預期：** 自動跳轉到 `http://localhost:3000/login`，畫面顯示登入表單

### 2. 登入失敗（顯示錯誤）

1. 在 `/login` 表單輸入：
   - Email：`admin@example.com`
   - 密碼：`wrongpw`
2. 點「登入」
3. **預期：** 表單下方顯示紅色 alert：
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

## B. 技師端 `/tech-login` 測試流程

### 模擬手機檢視

技師端為 **mobile-first PWA**，桌面瀏覽器會看到 `max-w-480px` 置中佈局。建議：
- Chrome DevTools → F12 → 點左上角 **Toggle device toolbar** → 選 iPhone 14 Pro
- 或手機真機開 `http://<你電腦 IP>:3000/tech-login`

### 1. 未登入自動跳轉（技師路由）

1. 清空 localStorage
2. 網址列輸入以下任一：
   - `http://localhost:3000/pool`
   - `http://localhost:3000/my-orders`
   - `http://localhost:3000/account`
3. **預期：** 自動跳轉到 `http://localhost:3000/tech-login`（不是 `/login`）

> AuthGuard 區分技師路由（`/pool`, `/my-orders`, `/account`, `/tech-login`）→ 導向 `/tech-login`；
> 其餘路由 → 導向 `/login`。

### 2. 登入失敗

1. 在 `/tech-login` 輸入：
   - 帳號：`demo-tech@example.com`
   - 密碼：`wrongpw`
2. 點「登入」
3. **預期：** 紅色 banner 顯示 `INVALID_CREDENTIALS (401)：...`，停留原頁

### 3. 登入成功（跳轉案件池）

1. 改輸入正確帳密：
   - 帳號：`demo-tech@example.com`
   - 密碼：`changeme123`
2. 點「登入」
3. **預期：**
   - 自動跳轉到 `/pool`（**不是 `/dashboard`**）
   - localStorage 寫入 `smartlock.access_token` / `smartlock.refresh_token`
4. 重整頁面 → 仍停在 `/pool`

### 4. Flow 1 Happy Path（完整端對端）

1. `/pool` 看可接工單列表 → 點任一工單卡片「接受工單」
2. **預期：** 跳轉 `/my-orders/<id>`
3. 在詳情頁可看到：
   - 服務地址 / 鎖具資訊 / 服務資訊 / 客戶資訊 / 「完工回報」按鈕 / 「改期」按鈕
4. 點「改期」→ `/my-orders/<id>/reschedule`，填時段與訊息送出
5. 或點「完工回報」→ 填 summary 送出 → 狀態改為 `completed`
6. 切到底部「帳戶」Tab → `/account`
7. 點「登出」→ confirm → 跳 `/tech-login`，localStorage 清空

### 5. 已登入訪問 `/tech-login` 自動轉回

1. 維持登入狀態
2. 網址列輸入 `http://localhost:3000/tech-login`
3. **預期：** 自動跳回 `/pool`（不是 `/dashboard`）

### 6. 跨入口 token 共用

> Admin 與技師目前共用同一 `smartlock.access_token` storage key。

- 若以 admin 帳號登入後訪問 `/pool`，AuthGuard 不會擋（有 token），但後端 `/api/v1/work-orders/pool` 可能依 role 回 403。
- 反之亦然。
- **建議**：admin 與 tech 不要在同一瀏覽器混用；切換前先登出。

### 7. 409 / 衝突情境（可選）

- 兩台手機同時登入同一技師帳號（不建議實際使用，但可測 token 行為）
- 同一工單被別人接走 → `/pool` 點「接受工單」應顯示「此工單已被其他技師接走」

---

## 後端同步觀察

打開另一個 terminal 觀察後端 log：

```bash
docker logs -f smart-lock-api
```

對應請求：

| 動作 | 預期 log |
| :--- | :--- |
| Admin 登入成功 | `POST /api/v1/auth/login 200` |
| Admin 登入失敗 | `POST /api/v1/auth/login 401` |
| 技師登入成功 | `POST /api/v1/technicians/login 200` |
| 技師登入失敗 | `POST /api/v1/technicians/login 401` |
| 登出 | `POST /api/v1/auth/logout 200` |
| 自動 refresh（401 後重試） | `POST /api/v1/auth/refresh 200` |

---

## 常見問題排查

### 跳轉沒有發生 / 一直白屏

- 開 DevTools → Console，看是否有紅色錯誤
- 確認 `web/.env.local` 有設定 `NEXT_PUBLIC_API_BASE_URL=http://localhost:8001`
- 確認後端 Docker 容器在跑：`docker ps | grep smart-lock-api`

### 登入按鈕無反應

- DevTools → Network 面板，看 `/api/v1/auth/login` 或 `/api/v1/technicians/login` 請求是否發出
- 若是 CORS 錯誤：檢查後端 CORS 設定是否包含 `http://localhost:3000`

### 登入後沒跳轉但 token 已寫入

- 重新整理頁面，若能進 `/dashboard` / `/pool` 就是 router.replace 的時序問題
- 檢查 `web/src/app/login/page.tsx` 或 `tech-login/page.tsx` 是否正確 await 後再 `router.replace`

### `/dashboard` 一直跳回 `/login`，但 token 已存在

- DevTools → Application → Local Storage 確認 key 是 `smartlock.access_token`（不是 `access_token`）
- 檢查 `web/src/lib/api.ts:19-23` 的 `STORAGE_KEYS` 與 `auth.getAccessToken()` 一致

### 技師路由跳到 `/login` 而非 `/tech-login`

- 確認 `AuthGuard.tsx` 的 `TECH_ROUTE_PREFIXES` 包含當前路徑前綴
- 重新 build：`cd web && npm run dev` 重啟

### 技師種子帳號 401

- 確認後端有跑 `SQL/seeds/technicians.sql`
- 直接 curl 驗證：
  ```bash
  curl -X POST http://localhost:8001/api/v1/technicians/login \
    -H "Content-Type: application/json" \
    -d '{"email":"demo-tech@example.com","password":"changeme123"}'
  ```

---

## 涉及檔案

| 檔案 | 角色 |
| :--- | :--- |
| `web/src/app/login/page.tsx` | Admin 登入表單 UI 與 submit handler |
| `web/src/app/tech-login/page.tsx` | 技師登入表單（mobile-first） |
| `web/src/app/login/layout.tsx` | `/login` 用 layout（不顯示 Sidebar） |
| `web/src/app/tech-login/layout.tsx` | `/tech-login` 用 layout |
| `web/src/components/layout/AuthGuard.tsx` | client-side 路由守衛（區分 admin / tech） |
| `web/src/components/layout/Sidebar.tsx` | Admin 登出按鈕所在處 |
| `web/src/app/account/page.tsx` | 技師帳戶頁，含登出按鈕 |
| `web/src/app/layout.tsx` | root layout，包入 `<AuthGuard>` |
| `web/src/lib/api.ts` | `login()` / `loginTechnician()` / `logout()` / `auth` token helpers |

---

## 後端 endpoints

| Method | Path | 用途 |
| :--- | :--- | :--- |
| POST | `/api/v1/auth/login` | Admin 帳密登入，回傳 access + refresh token |
| POST | `/api/v1/technicians/login` | 技師帳密登入 |
| POST | `/api/v1/auth/refresh` | 用 refresh token 換新 access token |
| POST | `/api/v1/auth/logout` | 撤銷 refresh token |
| GET | `/api/v1/technicians/me` | 取得目前登入技師個人資料 |
| GET | `/api/v1/work-orders/pool` | 案件池可接工單列表 |
| POST | `/api/v1/work-orders/{id}/accept` | 技師接單 |
| POST | `/api/v1/work-orders/{id}/complete` | 技師完工回報 |

完整契約見 `docs/02-design/specs/openapi.yaml`。
