# TC-WEB-MEDIA-01 — 受保護媒體顯示（AuthImage / lightbox / 401-403）

## 結果

| 項目 | 內容 |
|---|---|
| **判定** | **部分實作** |
| 走查日期 | 2026-08-04 |
| 證據型態 | 靜態原始碼走查 |
| 走查基準 | commit `2cfeca92` |
| 走查範圍 | `web/brand-portal/src/components/media/AuthImage.tsx:1-149`、`web/brand-portal/src/components/conversations/ChatTimeline.tsx:5-36/157-165`、`web/brand-portal/src/app/problem-cards/[id]/page.tsx:929-1003`、`web/brand-portal/src/app/work-orders/[id]/page.tsx:517-641`、`web/brand-portal/src/components/work-orders/MediaGallery.tsx:51-166/304-325`、`web/brand-portal/src/lib/api.ts:144-149/382-426`、`api/routers/media_v2.py:100-130` |
| 優先級 / 路徑類型 | P0 / 例外（權限） |

TC 指名的元件 `AuthImage` 在程式碼中存在（`web/brand-portal/src/components/media/AuthImage.tsx:19`），授權 fetch → Blob URL、失敗佔位、unmount revoke 三段皆有對應實作，token 只出現在 `Authorization` request header、不進 URL 或 DOM。判定為「部分實作」的原因是 TC 步驟列的三個畫面中，**對話頁沒有 lightbox**：`ChatTimeline` 內的 `AuthChatImage` 呼叫 `AuthImage` 時未傳 `onClick`（`ChatTimeline.tsx:18-34`），該檔對 `AuthImageLightbox` 零命中；問題卡頁（`problem-cards/[id]/page.tsx:936-942`、`:997-1003`）與工單頁（`work-orders/[id]/page.tsx:612-617`、`:632-638`）兩處則有縮圖 + lightbox。另「401/403 顯示失敗佔位」在原始碼中不區分兩碼，統一由 `res.ok` 為 false 走同一個 `catch`（`AuthImage.tsx:59`、`:64-66`）。實際注入 401/403 後畫面上的呈現屬執行期觀測，本次未取得。

---

## TC 原文

| 欄位 | 內容 |
|---|---|
| 章節 | 12. Web 與顯示整合案例（2026-07-23 codebase 對帳） |
| 前置 | 受保護媒體 API 要求 Bearer + X-Tenant-ID，另備無權/過期 token |
| 步驟 | 在對話、問題卡與工單頁開啟縮圖及 lightbox，再注入 401/403 |
| 預期結果（判定基準） | AuthImage 以授權 fetch→Blob URL 顯示；可放大、關閉並 revoke；401/403 顯示失敗佔位，不裸露 token 或造成整頁崩潰 |
| 路徑類型 | 例外 |
| 驗證面向 | 權限 |
| 優先級 | P0 |
| 驗證哪些需求 | FR-WEB-03、FR-WEB-07 |
| 屬於哪條旅程腳本 | — |

出處：`smartlock-docs/enterprise/20_Test_Cases.md:403`。

---

## 逐條驗收條件對照

| 條件 | 程式碼落點 | 狀態 |
|---|---|---|
| 媒體 API 要求 Bearer + X-Tenant-ID | `api/routers/media_v2.py:106-117`（`Depends(require_tenant)` + cross-tenant 403）；前端送 header `AuthImage.tsx:53-57` | 一致 |
| AuthImage 以授權 fetch → Blob URL 顯示 | `AuthImage.tsx:52-63`、`:104-110` | 一致 |
| 對話頁縮圖 | `ChatTimeline.tsx:17-35`、`:46-53` | 一致 |
| 對話頁 lightbox | `ChatTimeline.tsx` 對 `AuthImageLightbox` 零命中 | 不一致 |
| 問題卡頁縮圖 + lightbox | `problem-cards/[id]/page.tsx:936-942`、`:997-1003` | 一致 |
| 工單頁縮圖 + lightbox | `work-orders/[id]/page.tsx:612-617`、`:632-638` | 一致 |
| 可關閉 | `AuthImage.tsx:130-139`（背景點擊 + 關閉鈕） | 一致 |
| revoke Blob URL | `AuthImage.tsx:69-76`；`MediaGallery.tsx:89-96` | 一致（另有一條 async 競態路徑，見步驟 4） |
| 401/403 顯示失敗佔位 | `AuthImage.tsx:59`、`:64-66`、`:79-90` | 一致（兩碼不分流） |
| 不裸露 token | `AuthImage.tsx:48/54`；`api.ts:147`（access token 僅存記憶體） | 一致 |
| 不造成整頁崩潰 | `AuthImage.tsx:64-66` catch-all + `web/brand-portal/src/app/error.tsx` | 一致（畫面實況屬執行期觀測） |

---

## Event Storming

本案例為前端呈現行為，無 domain event。改列元件與資料來源對照：

| 使用者動作 | 元件 | 資料來源 | 程式碼落點 | 程式碼實際行為 |
|---|---|---|---|---|
| 開對話詳情 | `ChatTimeline` → `AuthChatImage` → `AuthImage` | `Message.media_url` | `ChatTimeline.tsx:46-53` | 縮圖顯示；無點擊放大 |
| 開問題卡詳情 | `AuthImage` + `AuthImageLightbox` | `card.media_urls[]` | `problem-cards/[id]/page.tsx:931-946` | 縮圖 `onClick` → `setPreviewMediaUrl` → lightbox |
| 開工單詳情 | `LineMediaGallery` → `AuthImage` + `AuthImageLightbox` | `GET /conversations/{id}/media` 之 `m.media_url` | `work-orders/[id]/page.tsx:602-638` | 縮圖 `onClick` → `setPreviewUrl` → lightbox |
| 點縮圖放大 | `AuthImageLightbox` | 同一 `url` 重新掛載 `AuthImage` | `AuthImage.tsx:140-147` | 第二次授權 fetch，產生第二份 blob URL |
| 關閉 lightbox | `AuthImageLightbox` | — | `AuthImage.tsx:130-139` | 背景 `onClick` 或右上鈕 `onClose` |
| token 無效 / 無權 | `AuthImage` | HTTP 401 / 403 | `AuthImage.tsx:59`、`:79-89` | 丟 `Error("HTTP 401")` → `failed=true` → 失敗佔位 |

---

## 逐層走查

### 步驟 1 — 元件層：授權 fetch → Blob URL

`web/brand-portal/src/components/media/AuthImage.tsx:38-67`

```tsx
  useEffect(() => {
    setFailed(false);
    if (/^https?:\/\//.test(url)) {
      setSrc(url);
      return;
    }
    let cancelled = false;
    const ac = new AbortController();
    // || 而非 ??：docker build 會把未設的 env 烘成空字串，?? 接不住（lib/api.ts 同款）
    const baseUrl = apiBaseUrl();
    const token = auth.getAccessToken();

    (async () => {
      try {
        const res = await fetch(`${baseUrl}${url}`, {
          headers: {
            Authorization: token ? `Bearer ${token}` : "",
            "X-Tenant-ID": auth.getTenantId(),
          },
          signal: ac.signal,
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const blob = await res.blob();
        const objUrl = URL.createObjectURL(blob);
        objectUrlRef.current = objUrl;
        if (!cancelled) setSrc(objUrl);
      } catch {
        if (!cancelled) setFailed(true);
      }
    })();
```

渲染出的 `<img src>` 是 blob URL（`:104-110`）：

```tsx
    <img
      src={src}
      alt={alt}
      decoding="async"
      className={className ?? "max-h-[240px] rounded-md"}
      onClick={onClick}
    />
```

絕對 URL（`https?://`）走 `:40-43` 直接指派，不帶 header。

### 步驟 2 — 後端端點的認證與租戶隔離

`api/routers/media_v2.py:106-121`

```python
async def get_media_v2(
    tenantId: str = Path(..., description="租戶 UUID（ADR-0030）"),
    mediaId: str = Path(..., description="媒體 UUID"),
    user: CurrentUser = Depends(require_tenant),
) -> Response:
    # cross-tenant guard（ADR-0030）
    if user.tenant_id and user.tenant_id != tenantId:
        raise ApiError(
            "CROSS_TENANT_READ",
            "Path tenantId does not match authenticated tenant",
            403,
        )
```

回應標頭為 `Cache-Control: private, max-age=3600`（`:128`）。

### 步驟 3 — 三個畫面的實際掛法

對話頁（`web/brand-portal/src/components/conversations/ChatTimeline.tsx:17-35`）：

```tsx
function AuthChatImage({ url, alt }: { url: string; alt: string }) {
  return (
    <AuthImage
      url={url}
      alt={alt}
      className="max-h-[240px] rounded-md"
      errorNode={
        <div className="flex items-center gap-1 rounded-md bg-white/15 px-3 py-2 text-[12px] text-white/80">
          <ImageOff className="h-4 w-4" />
          照片載入失敗
        </div>
      }
```

無 `onClick`，該檔對 `AuthImageLightbox` 零命中：

```
git grep -n "AuthImage" -- web/brand-portal/src/components/conversations/ChatTimeline.tsx
web/brand-portal/src/components/conversations/ChatTimeline.tsx:5:import { AuthImage } from "@/components/media/AuthImage";
web/brand-portal/src/components/conversations/ChatTimeline.tsx:14: * CR-0178 輪次 C：fetch→blob 邏輯抽至共用 <AuthImage>（media/AuthImage.tsx），
web/brand-portal/src/components/conversations/ChatTimeline.tsx:19:    <AuthImage
```

`ChatTimeline` 唯一的消費端是 `web/brand-portal/src/app/conversations/[id]/page.tsx:314`；該頁對 `lightbox` / `preview` 零命中。

問題卡頁（`web/brand-portal/src/app/problem-cards/[id]/page.tsx:935-943`）：

```tsx
                    {card.media_urls.map((url) => (
                      <AuthImage
                        key={url}
                        url={url}
                        alt="附件照片"
                        className="h-32 w-32 cursor-pointer rounded-lg border border-[var(--border)] object-cover"
                        onClick={() => setPreviewMediaUrl(url)}
                      />
                    ))}
```

對應 lightbox 於 `:997-1003`。工單頁（`web/brand-portal/src/app/work-orders/[id]/page.tsx:611-617`）為同型，lightbox 於 `:632-638`。

TC 步驟寫「在對話、問題卡與工單頁開啟縮圖及 **lightbox**」（出處：`smartlock-docs/enterprise/20_Test_Cases.md:403`）／程式碼在對話頁只掛縮圖、未掛 lightbox（`ChatTimeline.tsx:18-34`）。此處僅並陳，不裁定。

### 步驟 4 — 放大、關閉與 revoke

`web/brand-portal/src/components/media/AuthImage.tsx:128-148`

```tsx
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 p-4"
      onClick={onClose}
    >
      <button
        onClick={onClose}
        className="absolute right-4 top-4 rounded-full bg-white/10 px-3 py-1 text-[14px] text-white hover:bg-white/20"
        aria-label="關閉預覽"
      >
        ✕
      </button>
      <div onClick={(e) => e.stopPropagation()}>
        <AuthImage
          url={url}
          alt={alt}
          className="max-h-[90vh] max-w-[90vw] rounded-lg object-contain"
        />
      </div>
    </div>
```

檔內註解（`:115-117`）自述 lightbox「內部重掛 AuthImage 重 fetch 一次」、「blob URL 不可開新分頁（unmount/revoke 即失效，且新分頁補不了 auth header）」。

revoke 在 effect cleanup（`:69-76`）：

```tsx
    return () => {
      cancelled = true;
      ac.abort();
      if (objectUrlRef.current) {
        URL.revokeObjectURL(objectUrlRef.current);
        objectUrlRef.current = null;
      }
    };
```

觀測到的一條競態路徑：`URL.createObjectURL` 在 `:61` 執行、指派 `objectUrlRef.current` 在 `:62`，兩者都在 `if (!cancelled)` 判斷（`:63`）之前；若 cleanup 已先於這段 async 完成執行，`objectUrlRef.current` 在 cleanup 讀取當下仍是 `null`，其後 `:62` 才寫入，該次 blob URL 不會被 `:72` revoke。此為原始碼路徑陳述，實際是否觸發需執行期觀測。

`AuthImageLightbox` 對 `Escape`、`role="dialog"`、`aria-modal` 三者零命中（該檔全檔 149 行）。

### 步驟 5 — 401 / 403 的處理

`AuthImage.tsx:59` 只判斷 `res.ok`：

```tsx
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
```

`catch` 不讀狀態碼（`:64-66`），一律 `setFailed(true)`；失敗佔位 `:79-90`：

```tsx
  if (failed) {
    return (
      <>
        {errorNode ?? (
          <div className="flex items-center gap-1 rounded-md border border-[var(--border)] bg-[var(--bg-page)] px-3 py-2 text-[12px] text-[var(--text-disabled)]">
            <ImageOff className="h-4 w-4" />
            照片載入失敗
          </div>
        )}
      </>
    );
  }
```

`AuthImage` 用的是原生 `fetch`（`:52`），不是 `lib/api.ts` 的 `rawRequest`，因此不經過該檔的 401 → refresh → retry 鏈（`web/brand-portal/src/lib/api.ts:418-426`）：

```ts
  if (res.status === 401 && !options.skipAuth) {
    const ok = await refreshAccessToken();
    if (ok) {
      const newToken = auth.getAccessToken();
      if (newToken) (init.headers as Record<string, string>)["Authorization"] = `Bearer ${newToken}`;
      res = await apiFetch(buildUrl(path, options.query), init);
    }
    if (res.status === 401) handleSessionExpired(); // 刷新失敗/仍 401 → session 失效，導登入頁
  }
```

即 access token 過期時，同頁其他 `api.get` 會自動續期並重試，`AuthImage` 則直接落到失敗佔位。

### 步驟 6 — token 是否外露

access token 只存在模組內記憶體變數（`web/brand-portal/src/lib/api.ts:147`）：

```ts
  getAccessToken: () => accessTokenMemory,
```

`AuthImage` 只把它放進 request header（`:54`），未進 query string、未進 `src`；渲染出的 `src` 為 `blob:` 或原始絕對 URL。tenant id 由 claims cookie 取得，讀不到時退回常數（`api.ts:144`、`:149`）：

```ts
export const FALLBACK_TENANT_ID = "00000000-0000-0000-0000-000000000001";
```

該處 `:140-142` 附有 TODO 註記，說明「正式環境理應在無有效 tenant 時擋下並導回登入，而非靜默退回 1 號租戶」。

### 步驟 7 — 第二份同型實作的狀態

`web/brand-portal/src/components/work-orders/MediaGallery.tsx` 內另有一份未收斂到 `AuthImage` 的 `MediaThumb`（`:51-97` fetch→blob、`:141-146` 失敗佔位、`:89-96` revoke），其 lightbox（`:304-325`）在遮罩內重新渲染同一個 `MediaThumb`，而 `MediaThumb` 的容器尺寸固定為 `h-32`（`:106`）。

該元件在 `web/` 下無任何 import 端：

```
git grep -n "MediaGallery" -- web/brand-portal/src
web/brand-portal/src/app/work-orders/[id]/page.tsx:517:function LineMediaGallery({ conversationId }: { conversationId?: string }) {
web/brand-portal/src/app/work-orders/[id]/page.tsx:2017:          <LineMediaGallery conversationId={...} />
web/brand-portal/src/components/media/AuthImage.tsx:13: * 日後 GCS 簽名 URL）直接使用。原三處同款複本（MediaGallery.MediaThumb、
web/brand-portal/src/components/media/AuthImage.tsx:115: * AuthImageLightbox — 最小放大檢視（沿 MediaGallery lightbox 先例：
web/brand-portal/src/components/work-orders/MediaGallery.tsx:179:export default function MediaGallery({
```

工單頁實際使用的是同檔內的 `LineMediaGallery`（`work-orders/[id]/page.tsx:517`），走 `AuthImage` + `AuthImageLightbox`。

---

## 既有測試證據

前端側：

- `web/brand-portal/tests/unit/` 八個 vitest 檔（`commandRegistry` / `format` / `instrumentation` / `mutation` / `piiScrub` / `realtime` / `serverApiProxy` / `statusGroup`）中無 `AuthImage` 相關案例；`git grep -rn "AuthImage" -- web/brand-portal/tests` 零命中。
- `web/brand-portal/tests/e2e/` 內 `media` 字樣僅出現在 fixture 的 `media_urls: []`（`admin/cr-0022-hitl.spec.ts:28`、`admin/problem-cards.spec.ts:37`），無媒體顯示或 401/403 注入案例。
- 四站台 `node_modules` 均未安裝（`web/{brand-portal,tech-portal,landing,platform-console}/node_modules` 不存在），本次未實跑前端測試。

後端側（媒體端點的認證與租戶隔離）既有測試本次實跑通過：

```
cd api && POSTGRES_URI=<本機測試庫> python -m pytest \
  tests/test_media_v2.py tests/test_media_upload.py \
  tests/test_problem_card_media_urls_relative.py \
  tests/test_cr_0109_legal_hold.py tests/test_cr_api08_media_crypto.py \
  -q -p winloop_plugin
31 passed in 3.09s
```

`api/tests/test_media_v2.py:5-12` 的檔頭列出其涵蓋範圍：四個路徑的「無 token → 401」與四個 cross-tenant 403（`CROSS_TENANT_WRITE` / `CROSS_TENANT_READ`）。該檔為 API 層斷言，不涉及前端 `AuthImage` 的畫面行為。

---

## 事實結論

1. `AuthImage`（`AuthImage.tsx:19`）與 `AuthImageLightbox`（`:119`）在程式碼中存在，非零命中。
2. 授權 fetch → Blob URL 的實作在 `AuthImage.tsx:52-63`；`Authorization: Bearer` 與 `X-Tenant-ID` 兩個 header 皆送出（`:54-55`）。
3. lightbox 存在於問題卡頁與工單頁；對話頁 `ChatTimeline` 只掛縮圖，該檔對 `AuthImageLightbox` 零命中。
4. 關閉路徑有兩條（背景點擊 `:131`、關閉鈕 `:133-139`）；`Escape` 鍵處理、`role="dialog"`、`aria-modal` 在該檔零命中。
5. revoke 於 effect cleanup（`:72-75`）；另有一條 async 競態路徑上 blob URL 不進 revoke（`:61-63` 與 cleanup 的相對順序）。
6. 401 與 403 在前端不分流，統一走 `res.ok === false` → `catch` → 失敗佔位（`:59`、`:64-66`、`:79-90`）。
7. `AuthImage` 走原生 `fetch`，不經 `lib/api.ts` 的 401 → refresh → retry（`api.ts:418-426`）。
8. access token 僅在記憶體（`api.ts:147`）且只進 header；渲染的 `src` 為 `blob:` scheme。
9. 元件內 `catch` 為 catch-all（`:64`），單張圖失敗不往上拋。
10. `components/work-orders/MediaGallery.tsx` 為未被 import 的同型實作；其 lightbox 內重用固定 `h-32` 的 `MediaThumb`（`:106`、`:318`）。
11. 實際注入 401/403 後的畫面呈現、blob 記憶體釋放狀況屬執行期觀測，本次未取得。
