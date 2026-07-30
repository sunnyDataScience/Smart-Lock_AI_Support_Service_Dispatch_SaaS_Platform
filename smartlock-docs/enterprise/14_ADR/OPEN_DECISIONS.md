---
title: 開放架構決策登記
last_updated: 2026-07-27
status: active
owner: PM / 平台架構師
source: open_decisions.yaml
---

# 開放架構決策登記

> **唯一可寫入來源**：[open_decisions.yaml](./open_decisions.yaml)。本檔由四書生成器輸出為可讀投影；不要直接編輯。`OD-*` 是待決議題，不是 ADR 編號，也不得寫成既定架構。

## 標籤定義

- **OD**：Open Decision，已接受 ADR 的實作細節或跨領域取捨仍需裁決。
- **Open / Decided / Superseded**：尚未裁決／已由新 ADR 或明確裁決定版／被另一決策取代。
- **Current AS-BUILT**：目前程式或部署可觀察的事實；不等於目標架構或 production 證據。
- **技術建議**：技術立場，不是決議；只有 approvers 的裁決才能使 OD 關閉。
- **Decision gate**：未定案前不可越過的 release／擴展門檻。

## 總覽

| OD | 狀態 | 優先級 | 決策 Owner | 關聯情境 |
|---|---|---|---|---|
| OD-001 OHS 服務間憑證模式 | decided | P0 | PM + 平台架構師 | SC-05、SC-12、SC-14 |
| OD-002 knowledge-refinery 的資料進入契約 | decided | P0 | PM + 平台架構師 | SC-01、SC-02、SC-15、SC-16 |
| OD-003 技師即時 WebSocket 的權威歸屬 | decided | P0 | PM + 平台架構師 | SC-05、SC-06、SC-12、SC-14 |
| OD-004 Casdoor 跨租戶 organization 與 claim 模型 | decided | P0 | PM + 平台架構師 | SC-11、SC-12、SC-14、SC-17 |
| OD-005 未完成身分驗證的技師施工之責任、保險與揭露義務 | open | P0 | PM + 平台營運負責人 | SC-12、SC-14 |

## OD-001 — OHS 服務間憑證模式

- **狀態**：`decided`
- **優先級**：P0
- **Owner**：PM + 平台架構師
- **Approvers**：安全負責人 + technician-platform Owner
- **要做的決策**：品牌 API 呼叫技師共享池 OHS 時，定版 OIDC client-credentials 或 internal token，並定義 audience、scope、輪替、撤銷與跨品牌權限邊界。
- **Current AS-BUILT**：OHS 契約和 api 路徑存在；靜態 API 文件已明示長期模式由 OD-001 定版，現行內部鏈多使用 X-Internal-Token。
- **選項**：
  - OIDC client-credentials：每個 workload identity 取短效 audience/scoped token；適合作為跨服務長期邊界。
  - internal token：單一或少量共享 secret；較快接入，但輪替、最小權限與稽核成本較高，只適合作為過渡。
- **裁決結果（2026-07-28，業主（兼任 approvers 兩角色））**：定版受控 opaque service credential（X-Service-Credential，生命週期依 ADR-036）為 OHS 服務間憑證的長期模式。OIDC client-credentials 不否決，改列為重審項：第一個非自建的 外部接入方（他方 ERP、外部派工商）出現前必須重新評估。裁決理由是 ADR-036 已把 hash-only、audience/scope、expiry、rotation overlap、revoke 與 audit 這些安全下限 全部達成，transport 換成 OIDC 不會再提高該下限；而現行三條 caller（agent、refinery、 technician OHS）全為自建服務，OIDC 主要優勢「不必為每個接入方分發密鑰」目前無人受益。
- **承接 ADR**：ADR-040
- **技術建議（尚非決議）**：OIDC client-credentials 為目標；保留 internal token 僅限受時限、可輪替、單一過渡鏈路，且不得成為品牌/技師資料面的長期通用憑證。
- **Decision gate**：在 OHS 成為 production 派工唯一依賴、或第 2 個品牌接入前，必須定版並完成負向契約測試。
- **拍板前所需證據**：IdP 能力與 token claims 範例、service-to-service threat model、token 失效/輪替演練、OHS 403/401 契約與 audit 設計。
- **受影響 ADR**：ADR-004、ADR-016、ADR-022
- **拍板後必回填**：12_SAD §4.5、15_SDS §7.1、16_API_Spec.yaml、13_Security_Architecture.md、23_Deployment_Guide.md
- **受影響情境**：SC-05、SC-12、SC-14

## OD-002 — knowledge-refinery 的資料進入契約

- **狀態**：`decided`
- **優先級**：P0
- **Owner**：PM + 平台架構師
- **Approvers**：Data Owner + Knowledge/Refinery Owner + Security Owner
- **要做的決策**：定版 Refinery 取得診斷對話、問題卡與素材的權威入口：受控 API、批次匯出/唯讀 DB，或 Kafka/outbox event；並定義補數、重播、tenant scope、PII 最小化與 provenance。
- **Current AS-BUILT**：Refinery intake 可用 REFINERY_TENANT_ID + REFINERY_POSTGRES_URI/POSTGRES_URI 直讀品牌資料並 default-deny；Kafka/event backbone 與 API ingestion 均非完整 production contract。
- **選項**：
  - 受控 API：明確 DTO/授權與稽核，讀取延遲較高，需提供 cursor/重試與 bulk 能力。
  - 批次匯出或唯讀 DB：最快可用，必須使用專屬唯讀帳號、資料最小化與嚴格 tenant filter；跨服務耦合較高。
  - Kafka/outbox event：低耦合、可重播，需 schema registry、DLQ、事件順序與 payload 隱私治理；適合規模化但基建未取證。
- **裁決結果（2026-07-28，業主（兼任 approvers 三角色））**：定版受控 API 為 refinery 的唯一主入口。裁決前提是業主確認 refinery 是要賣給品牌的 收費附加服務並已列入 roadmap——這推翻了本條原記載的技術建議（該建議寫在「refinery 為 內部工具」的前提下）。收費產品的資料汲取必須是契約而不是資料庫連線：①每品牌物理分庫下 直讀代表每開一個品牌就要多配一組唯讀憑證與網路路徑（撞 WBS 3.3.1／3.5.1 開站自動化）； ②計費需要逐租戶用量計量，DB 連線沒有計量點；③賣出後 schema 即成契約，品牌端 migration 會靜默打壞付費產品；④DPA 需要逐筆 provenance 與刪除語義。refinery 的寫回路徑已走 受控 API + X-Service-Credential（apply_behavior.py），本裁決是把讀取路徑收尾到同一條 契約上，不是新工程。直讀 DB（REFINERY_POSTGRES_URI，現讀 messages／problem_cards／ knowledge_drafts／tenant 四表）比照 X-Internal-Token 處理：標為 interim、加使用量計數、 歸零才移除。Kafka/outbox 留作日後量能與延遲優化，是 API 的補充不是取代，且不得在 KAFKA_BOOTSTRAP 取得 production 證據前承載這條線。
- **承接 ADR**：ADR-042
- **技術建議（尚非決議）**：M2 以最小權限唯讀／批次入口完成可稽核 intake；M3 Kafka/outbox 成熟後切換為事件主路徑，API 僅供補數與人工重跑，不讓三種入口同時無規則並存。
- **Decision gate**：在把 Refinery 標為 License 可售附加服務、或允許自動排程 intake 前，必須選定一條主入口及其回補規則。
- **拍板前所需證據**：資料分類/PII 最小化評估、每個選項的重播與刪除語義、tenant 隔離測試、bronze provenance 範例、成本/延遲量測。
- **受影響 ADR**：ADR-018、ADR-019、ADR-029、ADR-030
- **拍板後必回填**：12_SAD §4.4、15_SDS §9、17_AsyncAPI.yaml、23_Deployment_Guide.md、25_Monitoring_Spec.md
- **受影響情境**：SC-01、SC-02、SC-15、SC-16

## OD-003 — 技師即時 WebSocket 的權威歸屬

- **狀態**：`decided`
- **優先級**：P0
- **Owner**：PM + 平台架構師
- **Approvers**：Technician Platform Owner + API Owner + SRE
- **要做的決策**：定版技師工作台的即時事件由 brand API、technician-platform，或雙層 gateway 哪一方擁有；同時定義 channel 授權、事件 owner、replay、Redis/Kafka 依賴與切換策略。
- **Current AS-BUILT**：tech portal 目前可連品牌 API 的 WS；程式有 Redis bridge 與 technician event consumer，但 REDIS_URL/KAFKA_BOOTSTRAP 的 production 證據不存在，SDS 已連至 OD-003，不把 interim 當 target。
- **選項**：
  - brand API owner：貼近工單 command 真相，技師 portal 必須跨面連線，跨品牌與身份邊界較複雜。
  - technician-platform owner：貼近技師 identity/projection，需保證投影延遲、replay 與品牌事件契約。
  - gateway/聚合層：可統一通道授權，但新增部署與故障域，不得成為未受監控的第四份投影。
- **裁決結果（2026-07-28，業主（兼任 approvers 三角色））**：定版technician-platform 持有師傅專屬 channel，brand API 只保留品牌營運 channel。 裁決依據是業主確認的產品形態：師傅在單一 app 內看到多個品牌／經銷商的需求（Uber 式 聚合視圖）。由各品牌 API 各自持有 WS 會使師傅 app 必須同時連 N 條線，且沒有任何一方 能組出統一清單；這也與 ADR-041「技師身分只有一份」不一致——身分是一份，通知線就該是 一條。本裁決只涵蓋 channel 歸屬，不涵蓋派工模式本身。業主同日另確認派工採「指派 為主、搶單為輔」（指定師傅逾時未接則釋出到公開池），該混合模式在現行 code 完全不存在 （dispatch_service 只有 candidate 評分排序，師傅端無 accept／reject／搶單），屬產品層 變更，須另開 CR 走 CIA，不得以本 ADR 代替。實際遷移仍受 Redis（跨實例 fan-out）與 Kafka（品牌事件投影）的 production 證據約束，兩者現皆為休眠 opt-in。
- **承接 ADR**：ADR-043
- **技術建議（尚非決議）**：technician-platform 持有技師專屬 channel 與最小工單投影；brand API 持有品牌營運 channel。先以明確 event schema/replay 驗證，再遷移 portal，禁止同一事件長期雙播而無 owner。
- **Decision gate**：在把 API max instances 調高、或宣稱跨 instance 的技師即時派工 SLA 前，必須定版並完成兩實例與斷線復原 SIT。
- **拍板前所需證據**：使用者/租戶/channel 授權矩陣、事件延遲預算、disconnect/replay 演練、Redis/Kafka failure trace、前端切換/rollback 計畫。
- **受影響 ADR**：ADR-006、ADR-016、ADR-017、ADR-022
- **拍板後必回填**：12_SAD §4.5、15_SDS §7.1、16_API_Spec.yaml、17_AsyncAPI.yaml、23_Deployment_Guide.md
- **受影響情境**：SC-05、SC-06、SC-12、SC-14

## OD-004 — Casdoor 跨租戶 organization 與 claim 模型

- **狀態**：`decided`
- **優先級**：P0
- **Owner**：PM + 平台架構師
- **Approvers**：Identity Owner + Security Owner + Technician Platform Owner
- **要做的決策**：在「brand org = 租戶」既有方向下，定版跨品牌技師、platform operator、品牌管理員的 organization membership、role/portal/tenant claims、委派管理與撤銷傳播模型。
- **Current AS-BUILT**：ADR-004 已接受 Casdoor 作 IdP、brand org 為租戶；portal claim guard 與 API surface 已有程式，但完整 Casdoor org/claim 映射及 production HA 證據未定。
- **選項**：
  - 單一平台 org + brand membership：技師與平台人員有平台主體，再以品牌 membership/scopes 授權。
  - 每品牌 org 複製技師帳號：模型直觀但違反跨品牌唯一身分，撤銷與 KYC 一致性風險高。
  - external identity + 平台 entitlement graph：彈性最高，但需自建更多 membership/授權服務與稽核能力。
- **裁決結果（2026-07-28，業主（兼任 approvers 三角色））**：定版「單一平台 principal + brand membership claim」。技師在平台只有一份身分，token 帶 principal、portal、可操作 brand scope 與版本/撤銷語義，並一次帶齊該技師目前已授權的 全部品牌；不採「每品牌各複製一份技師帳號」。品牌間的競爭隔離不由收窄 token scope 達成，而是既有的每品牌物理分庫加上 tech_mirror 最小化投影（品牌庫不鏡射 authorized_brands、憑證與 PII）——品牌後台在資料層就取不到他牌工單。平台跨品牌治理 走 platform admin principal（platform_technicians 的跨品牌清單與 brand authorization 授予/撤回），依 ADR-035 不接受以 X-Tenant-ID 取得跨品牌權限。
- **承接 ADR**：ADR-041
- **技術建議（尚非決議）**：單一平台 principal + brand membership/entitlement claim；token 必須明確帶 principal、portal、可操作 brand scope 與版本/撤銷語義，不以 UI tenant fallback 決定授權。
- **Decision gate**：在 Casdoor 成為所有 portal 的唯一登入、或首個跨品牌技師/平台治理 production rollout 前，必須定版。
- **拍板前所需證據**：claim 範例與最大 token 大小、登入/撤銷/換品牌序列、跨 portal 負向測試、HA/IdP outage 行為、資料保留與刪除責任。
- **受影響 ADR**：ADR-004、ADR-005、ADR-016、ADR-024
- **拍板後必回填**：12_SAD §4.5 and §8、13_Security_Architecture.md、15_SDS §7.1、16_API_Spec.yaml、23_Deployment_Guide.md
- **受影響情境**：SC-11、SC-12、SC-14、SC-17

## OD-005 — 未完成身分驗證的技師施工之責任、保險與揭露義務

- **狀態**：`open`
- **優先級**：P0
- **Owner**：PM + 平台營運負責人
- **Approvers**：業主 + 法務（Irene）
- **要做的決策**：平台在「技師未完成 KYC 身分驗證即到府施工」的情境下，對客戶的責任歸屬、保險覆蓋、賠償上限與揭露義務為何；以及條件式核准是否需設補件期限與逾期處置。
- **Current AS-BUILT**：核准端原本對 KYC 文件零檢查（technician_lifecycle_service.approve_onboarding 全鏈不查 technician_registration_document），實測本機 6 位 active 技師 100% 零文件—— 「未驗身分即上工」早已在發生，只是無人察覺。CR-0195（業主 2026-07-30 裁決）已把它 改為必須顯式「條件式核准」並落 onboarding_approved_conditional 事件，讓決定可稽核； 但責任側規則仍為空白。註冊表單有「授權背景查核」勾選（tech-register/page.tsx:438） 與 insurance/良民證 文件槽位，但查不到任何實際執行背景查核的流程或供應商 （CR-0115 §11 明列 out of scope）。另 CR-0170 師傅懲罰機制（遲到/違約自動停權） 同樣卡在法務未回，狀態為「骨架待料」。
- **選項**：
  - 條件式核准設補件期限（如 14 天），逾期自動停權：責任窗口有上限，但天數與申訴機制需法務給值，且與 CR-0170 懲罰機制同域。
  - 不設期限，僅以清單標記與稽核事件追蹤：現行 CR-0195 實作，成本最低但責任窗口無上限。
  - 條件式核准期間限制派工範圍（如不得進搶單池、僅可指定派工）：降低暴露面，但需在派工資格判定區分兩種 active，成本高一個數量級（見 evidence_required）。
  - 停用條件式核准、回到「核准前必須驗畢」：與業主「師傅不夠時要能先上工」的營運需求衝突。
- **技術建議（尚非決議）**：先由法務界定責任與揭露下限，再回頭決定期限與派工限制。技術面不建議在法務結論前先做 選項三——它需要改 dispatch_service.py:186 的 fail-open 黑名單與散在 4 個站台的 10 份 exhaustive Record，漏改一處即「未驗證技師直接進派工候選集」，成本與風險都不該由 未定的政策驅動。
- **Decision gate**：在對外宣稱技師已完成身分查核之前，或條件式核准累計超過可控件數之前，必須定版。 特別注意 AI 客服的產品知識庫已對客戶明文宣稱「警政單位核發良民證核可」 （agent/lockcore/skills/locksmith-product-knowledge/references/_common/store-info.md:44， 來源為公司官網 bronze 語料）——該聲明對「公司自有鎖匠」可能為真，但對平台 onboard 的師傅目前無任何流程保證。
- **拍板前所需證據**：法務對責任歸屬/保險覆蓋/揭露義務的書面意見；現行服務條款與隱私權政策全文（目前不在 repo， code 只有連結文案）；保險商品是否涵蓋未驗證技師；條件式核准的實際發生件數與停留時長。
- **受影響 ADR**：ADR-041
- **拍板後必回填**：04_SRS.md FR-TEC-02、bdd/SC-12.feature、20_Test_Cases.md TC-TEC-LIFE-01、10_UI_Spec.md、docs/4-exploration/CR-0195、docs/4-exploration/CR-0170
- **受影響情境**：SC-12、SC-14
