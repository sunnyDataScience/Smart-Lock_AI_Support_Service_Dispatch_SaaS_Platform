---
name: product-knowledge
description: 電子鎖產品知識查詢。客戶詢問電子鎖原理、品牌型號、電池規範、Wi-Fi設定、鎖匣類型、側板規格、開門方向等產品相關知識時使用
user-invocable: true
---

# 電子鎖產品知識庫

## ⚠️ 故障問題請先用 troubleshoot

如果客戶的問題包含故障症狀或結構問題（沒電、打不開、卡住、警報、行動電源喚醒、門扇反弓、鉸鏈、門歪、門下沉等），**不要使用本技能**，請先呼叫 `load_skill("troubleshoot")` 進行症狀分流。本技能僅用於查詢產品規格、手冊連結、功能說明等非故障問題。

## 必須收集的資訊

若客戶詢問特定產品問題，先確認：
- **品牌**：「請問您的電子鎖是什麼品牌？」
- **型號**：「型號是什麼？不確定可以描述外觀或開門方式」

---

## 一、支援品牌與型號

| 品牌 | 型號 | 特色 |
|------|------|------|
| **Chainlock/Chatlock** | AI99、A90、AI88 | 3D人臉辨識、掌靜脈、APP遠端、攝影鏡頭(AI99) |
| **Dormakaba** | AS901、DP850、ML660 | 擺動式鎖舌設計、歐規品質 |
| **Philips** | 7300、Alpha、702E、9200、9300 | 飛利浦品牌 |
| **Kaadas 凱迪仕** | 藍寶堅尼3D、門鈴款 | 中高階市場 |
| **Milre 美樂** | 6500F、6500S、7150 | 韓系品牌 |
| **AiLock** | 七合一旗艦款 | 多合一功能 |

### 型號操作手冊（Google Drive 連結）

| 型號 | 手冊連結 |
|------|---------|
| GL220 | https://drive.google.com/file/d/1ZD-fwviSEWguw1V0ZZ27-CKgZeoamKBr/view |
| FA9000 | https://drive.google.com/file/d/1L7JZB7pbSgIe71755n07DbwdF7swYw5o/view |
| DP850 | https://drive.google.com/file/d/1_v4NybcMy4C72hsL-slYW02-jdrYUc2_/view |
| AS701 | https://drive.google.com/file/d/1khDfWOjNoYEqKq6s-WEaaEFtUpAXCMWO/view |
| AS901 | https://drive.google.com/file/d/1DiJSJhPSpJhg7lUuizV0ClMYpEgO1skC/view |
| ML550 | https://drive.google.com/file/d/155gAgxCWZ139sijQKY3CJ8Y_fkacMjrB/view |
| ML660 | https://drive.google.com/file/d/1d2yqi8WHxQw9kYNsTkQBKHhWjcXJgkOa/view |
| ML770 | https://drive.google.com/file/d/1oh2CBKJJcWkzYN0gX8zGfU5y_qA4FgJZ/view |
| MP750 | https://drive.google.com/file/d/1YEQNNNR8OoRk6O_y4x12Ye9gtjaoVQ5r/view |
| RL320 | https://drive.google.com/file/d/1VovQdEbsz23V97dxtkz6Q0yccUjzm87o/view |
| RL360 | https://drive.google.com/file/d/18oZhIgJbKLi9DGFqy16Fcn6tohEcPPQH/view |
| RL360V | https://drive.google.com/file/d/1CJxpazymupuqjSzygGIkjIIWZY8iqalY/view |
| RL599 | https://drive.google.com/file/d/1ICv9biXDX7jAJPfbnpuhwp8Y8-GaaTCn/view |
| FSL800 | https://drive.google.com/file/d/1QCnUgdX3gmLULgknkRrFjQPmFdSBNYum/view |
| Rose | https://drive.google.com/file/d/1UGyxDzGY_O76Xwh2j2EHBESBLASSjc5B/view |
| WiFi 設定 | https://drive.google.com/file/d/15_WKocOTqfhB1Xt4ppmk_QhTROdWkEfh/view |
| Dormakaba APP 遠端操作 | https://drive.google.com/file/d/1Ii4vdaz8_kGdUUtc0p_sep5LI8i09RML/view |
| Dormakaba APP 操作手冊 | https://drive.google.com/file/d/1lSdrdkjE9Jeh-sqXhylQvAvGxDO3S4eV/view |

> 客戶詢問特定型號的操作手冊時，直接提供對應的 Google Drive 連結。

---

## 二、開門方式分類

| 類型 | 說明 | 判斷方式 |
|------|------|---------|
| **推拉式** | 解鎖後直接推拉門 | 「不需要按把手，推或拉就可以開」 |
| **把手式** | 解鎖後需下壓把手 | 「要握住把手往下壓才能開門」 |

---

## 三、鎖匣類型

| 類型 | 特徵 |
|------|------|
| **全自動鎖匣** | 有鎖舌/鎖榫感應器，關門自動伸出鎖舌上鎖 |
| **半自動鎖匣** | 無感應器，需手動上提把手，3-5 秒後自動上鎖（把手空轉 + 馬達聲） |

---

## 四、電池與供電規範

### 鹼性電池
- ✅ **Panasonic 鹼性電池**（金紅包裝）或太元素電池
- ❌ 禁止金鼎等品牌（漏液）、碳鋅電池（電壓不穩）
- 8 顆電池續航約 8 個月至 1 年

### 鋰電池充電
- 充電頭：**5V1A 或 5V2A**（❌ 禁止快充）
- 充電線：Type-C 轉 Type-A

### 低電量提示方式
- 語音提醒、燈號閃爍、手機 APP 通知

### 無電緊急方案（Chainlock AI99/A90）
- 底部中央圓形蓋子 → 向下按壓並向右旋轉
- 左側：Type-C 充電孔（接行動電源緊急供電）
- 右側：備用鑰匙孔

---

## 五、Wi-Fi 與聯網

- 僅支援 **2.4G 頻段**（❌ 不支援 5G）
- ❌ 不建議 Wi-Fi 6/7/8 路由器（協定相容性差）
- **必要設定：** 路由器 2.4G 和 5G 頻段必須分開設定（合併會異常耗電）
- 進階方案：購買僅支援 2.4G 的入門級路由器供電子鎖專用

---

## 六、鎖體構造

三大核心部件：
1. **前部機（室外機）**：安裝於門外
2. **鎖夾/鎖體**：嵌入門體內部（核心機械）
3. **後部機（室內機）**：安裝於門內

配套組件：**受口片**（門框上的銀色金屬片，為鎖舌提供卡入位置）

### 鎖體內部
- **鎖舌（斜舌）**：門關時自動彈出
- **鎖栓**：上鎖時伸出的主要防盜部件
- **按鎖鎖栓**：部分型號配備

---

## 七、側板規格

- 定義：鎖匣外部的整片鐵片
- 台灣常見：**歐規、美規、義大利規、日規、韓規**（無台灣本地標準）
- Chainlock 做法：確認現有側板寬度與長度 → 提供相符側板替換 → 避免切割
- ⚠️ 砂輪機切割副作用：毛邊、敲打痕跡、高熱可能導致門板油漆起泡

---

## 八、開門方向判斷

**判斷基準：** 人站在門外，看鉸鏈位置

| 鉸鏈位置 | 開門方向 |
|----------|---------|
| 鉸鏈在右側 | 右開門 |
| 鉸鏈在左側 | 左開門 |

**開門方式：** 向外拉開 或 向內推開

---

## 九、解鎖方式

| 方式 | 說明 |
|------|------|
| 指紋 | 0.3 秒辨識，生物辨識技術 |
| 密碼 | 自設 6-12 位 |
| 卡片 | NFC 感應，無需鑰匙孔 |
| 實體鑰匙 | 備用，系統故障時使用 |
| 藍牙 | 部分型號標配/加購，需 APP |
| 遠端 | 異地開關門 或 發送限時密碼 |
| 人臉辨識 | 3D 辨識，AI99 |
| 掌靜脈 | 15-30 公分感應，AI99 |

### 權限區分
- **管理者**：最高權限，可設定所有功能
- **一般使用者**：僅具開門權限

### 使用者管理
Chainlock 電子鎖在管理者驗證成功後，即可進入用戶管理介面，在此介面可新增用戶並選擇新增方式。

---

## 十、常見問題與排除

### Dormakaba 鎖舌卡住排除
當Dormakaba 電子鎖使用者在門外欲以推門方式開門，但門無法開啟時，應先將電子鎖門拉緊，完成解鎖後，立即用力推動把手，鎖舌便會擺動，即可順利開門。

$ARGUMENTS