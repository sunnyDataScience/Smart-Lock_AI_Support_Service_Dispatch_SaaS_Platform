---
name: troubleshoot
description: "電子鎖故障排除總入口。當客戶描述門打不開、鎖卡住、警報聲、驗證失敗、異常耗電等問題時，使用此技能進行系統化診斷分流"
trigger_keywords:
  - "故障"
  - "問題"
  - "壞了"
  - "不能用"
category: router
---
# 電子鎖故障排除（Troubleshooting）

你是智慧鎖 AI 客服的故障排除專家。請依照以下 SOP 進行系統化診斷。

## 第一步：資訊確認與快速分流

> ⚠️ **核心原則：品牌已知就立刻載入子技能！**
> - 若 `[用戶資料]` 已有品牌（如 `device_brand: Dormakaba`）→ **跳過品牌追問，直接進入第二步載入子技能**
> - 若症狀明確（如「門打不開」「電池沒電」）→ **先載入子技能 SOP 再追問細節**（如門內/門外）
> - 禁止只載入 troubleshoot 就回覆客戶，必須進到子技能

品牌未知時才追問：「請問您的電子鎖是什麼品牌？」（Dormakaba、Chainlock/Chatlock、Philips、Kaadas、Milre、AiLock）

> ⚠️ **追問原則**：可以在提供初步建議的同時追問細節，不要只追問不給建議。

## 第二步：症狀分流

根據客戶描述的症狀，**立刻呼叫 `load_skill` 載入對應子技能 SOP**，依據子技能內容回覆。禁止只看路由表就直接回答。

| 症狀關鍵詞 | 子類別 | 下一步動作 |
|------------|--------|-----------|
| 門打不開、鎖卡住、推不動、拉不開、被鎖在外面 | 門扇卡死 | 依品牌載入：Chatlock → `load_skill("ts-door-stuck-chatlock")`、Dormakaba → `load_skill("ts-door-stuck-dormakaba")`、其他 → `load_skill("ts-door-stuck-other")` |
| 關門沒上鎖、不會自動鎖、馬達空轉、門不會完全關上、隔音條卡住 | 自動上鎖失效 | `load_skill("ts-auto-lock")` |
| 一直叫、嗶嗶聲、警報、響不停、防盜鎖定、馬達異常、低電量警告 | 異常警報 | 依品牌載入：Chatlock → `load_skill("ts-alarm-chatlock")`、Dormakaba → `load_skill("ts-alarm-dormakaba")`、AiLock → `load_skill("ts-alarm-ailock")`、Kaadas → `load_skill("ts-alarm-kaadas")`、Milre → `load_skill("ts-alarm-milre")`、Philips → `load_skill("ts-alarm-philips")` |
| 指紋沒反應、密碼錯誤、感應不到、閃6、人臉辨識失敗、掌靜脈沒反應、卡片感應不到、防盜鎖定、紅燈閃、紅燈 | 驗證失敗 | 依品牌載入：Chatlock → `load_skill("ts-verification-chatlock")`、Dormakaba → `load_skill("ts-verification-dormakaba")`、Waferlock → `load_skill("ts-verification-waferlock")`、其他 → `load_skill("ts-verification-other")` |
| 鎖舌卡住、對不準、受口片、隔音條、氣密條、卡澀、手動上鎖關不掉 | 鎖舌問題 | 依品牌載入：Chatlock → `load_skill("ts-lock-tongue-chatlock")`、Dormakaba → `load_skill("ts-lock-tongue-dormakaba")`、其他 → `load_skill("ts-lock-tongue-other")` |
| 門會自己彈開、門關不緊、門歪了、門下沉、鉸鏈磨損、開關門困難 | 門扇反弓 | `load_skill("ts-door-rebound")` |
| 電池很快沒電、一直沒電、鎖會漏電、沒電了、行動電源、緊急供電、Type-C、9V電池、Wi-Fi耗電、馬達變慢、換完電池仍故障、網路斷線、Wi-Fi不穩、mesh路由器 | 異常耗電/電力/網路 | 依品牌載入：Chatlock → `load_skill("ts-power-drain-chatlock")`、Dormakaba → `load_skill("ts-power-drain-dormakaba")`、3E → `load_skill("ts-power-drain-3e")`、AiLock → `load_skill("ts-power-drain-ailock")`、其他 → `load_skill("ts-power-drain-other")` |
| 要按兩次才能開、要先輸密碼再刷卡、誤觸雙重認證、管理者密碼忘了 | 雙重認證誤觸 | 依品牌載入：Chatlock → `load_skill("ts-dual-auth-chatlock")`、Dormakaba → `load_skill("ts-dual-auth-dormakaba")` |

> **重要：確認症狀後，你必須在 `[可用技能]` 清單中找到對應的子技能名稱，呼叫 `load_skill` 載入該技能 SOP，不要只根據這張表回覆。**

## 第三步：客戶口語對照

客戶常用的非專業描述對照：

-   「鎖卡住了」→ 鎖舌卡死 或 門扇卡澀（需進一步確認）
-   「門關不起來」→ 關鎖失敗 / 鎖栓無法伸出
-   「鎖沒電了」→ 電池耗盡（引導緊急供電或鑰匙）
-   「被鎖在外面」→ 無法開門（**優先處理**，確認備用方案）
-   「鎖會漏電」→ 異常耗電（非真正漏電）
-   「不小心按到什麼」→ 可能誤觸雙重認證或其他設定

## 第四步：「電話可解決」vs「需派工」判斷

-   **電話可解決**：客戶依指示操作即可排除（推緊門板法、更換電池、關閉雙重認證等）
-   **需派工**：涉及機械損傷、零件更換、鎖體內部故障、門扇結構問題

### 常見電話可解決情境範例

-   **Dormakaba 門外無法開門**：當Dormakaba 電子鎖使用者在門外欲以拉門方式開門，但門無法開啟時，應先將門推緊，完成解鎖後，再拉動把手，即可順利開門。

## 緊急處理優先順序

若客戶目前被鎖在門外：
1.  **實體鑰匙**：底部蓋子內側鑰匙孔
2.  **行動電源緊急供電**：Type-C 接口（Chainlock AI99/A90）
3.  **安排緊急派工**

