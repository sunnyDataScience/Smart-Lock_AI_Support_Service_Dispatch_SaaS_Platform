# Plane In Progress 解除條件盤點 — 2026-07-22

> **緣起**：業主問「Plane 還有一堆 In Progress 怎麼回事」。逐張盤點確認：**12 個 In Progress 沒有一個是「還在寫 code」**。本表把每張的解除條件（exit criteria）明文化，讓 In Progress 透明——不是靠硬收 Done 減少數量（那是 CR-0038 完成度虛報老路），而是讓每張都有清楚的「在等什麼、誰負責、何時能收」。

## 一句話結論

In Progress ≠ 停滯。這些卡的 code 幾乎都完成，卡在**基礎設施部署／日曆窗／階段二進行中／主動暫緩**——這四類正是「完成判準改制」（code 完成＋代理 UAT＝完成）**沒**涵蓋的。

## 12 個 In Progress 分類與解除條件

| 卡 | 類別 | code 狀態 | 解除條件（exit criteria） | 負責 |
|---|---|---|---|---|
| **M1 母卡** | rollup | — | 子卡 1.4.1 + 1.6.1 收 Done 即自動收 | 機制 |
| **M2 母卡** | rollup | — | 子卡 2.1.1 + 2.5.1 收 Done 即自動收 | 機制 |
| **M3 母卡** | rollup | — | M3 子卡全 Done（階段二 Release gate） | 機制 |
| **1.4.1 可觀測性** | 基礎設施部署 | ✅ 完成（四站 OTel + OPIK + PII scrub） | **綁真實營運開始**：部署 SigNoz 叢集 + 設 `OTEL_EXPORTER_OTLP_ENDPOINT`（業主 0722 裁決：無流量不架空轉 VM） | OPS（營運後） |
| **1.6.1 基礎 CD** | 主動暫緩 | ✅ 完成（drift-check + CD workflow + WIF 腳本） | `brew install gh` → 跑 `opsday-20260722-3-wif.sh`（業主 0722 決定 GitHub Actions 暫緩） | 業主 |
| **2.1.1 Casdoor** | 基礎設施部署 | ✅ S0-S4 code + prod 部署 | **Casdoor 上雲輪**：prod 無 Casdoor 實體（R6 未上）；含 tokenFormat=JWT-Custom + S3b 自訂網域 + S5 密碼退場 + ACT-01 | Casdoor 上雲輪 |
| **2.5.1 v1 收斂** | 日曆 gate | ✅ 凍結 enforced + caller 歸零 | **deprecation 30 天零命中窗**（0722 OPS 批次日起算）→ 過窗 + CIA 才移除端點 | 時間（8/21 後） |
| **3.1.1 Kafka 骨幹** | 階段二 | ✅ code 在（producer/consumer/投影） | 設 `KAFKA_BOOTSTRAP`（Redpanda broker 佈建）+ 生產驗證 + outbox 退場 | 階段二 OPS |
| **3.2.1 期末對帳** | 階段二 | ✅ 閘門 code + 串月結（0722） | 前置 3.1.1 Kafka 上線 + M18 開 `reconcile_gate_enforce` + BR-SETTLE-05 生產驗收 | 階段二（3.1.1 後） |
| **3.3.1 provisioning** | 階段二進行中 | ✅ 腳本 + SOP + dry-run（0722 升） | 實際上雲部署（R6/GCP 協同）+ 真實 LINE 綁定 + Casdoor/secrets 自動化 | 階段二 OPS |
| **3.5.1 開站演練** | 階段二進行中 | ✅ SOP 文件 + 0712 dry-run（0722 升） | PM+OPS 親走「申請→核准→開站→綁 LINE」全流程（含真實 LINE 通道） | 階段二 PM+OPS |
| **seq38 CR-0176** | 刻意延後 | ✅ S1-S4 + bidx prod 生效（0722） | **S5 DROP 明文欄**：過渡窗 dual-read 穩定後（明文與密文同值，不急） | 未來輪 |

## 分類統計

| 類別 | 張數 | 本質 |
|---|---|---|
| 母卡 rollup | 3 | 機制性，子卡收完自動收 |
| 階段二進行中/未啟用 | 4（3.1.1/3.2.1/3.3.1/3.5.1） | 業主 0712 裁決啟動 M3，規模化正在做，In Progress 健康 |
| 基礎設施部署輪 | 2（1.4.1 SigNoz / 2.1.1 Casdoor 上雲） | 常駐基礎設施+成本決策，綁營運/上雲輪 |
| 日曆 gate | 1（2.5.1） | 30 天窗，時間到才能動 |
| 主動暫緩/刻意延後 | 2（1.6.1 WIF / seq38 S5） | 業主主動決定的暫停 |

## M1 收官路徑

M1 底下 13 張，**11 Done**，只卡 **1.4.1**（綁營運）與 **1.6.1**（WIF 暫緩）。兩張 code 都完成，卡的是一次性基礎設施——**M1 離收官最近，但收官時機綁「營運開始」與「業主想按鈕化」，非今日強收**。

> 治理原則（沿 CR-0038 教訓）：In Progress 誠實反映「未上線/未啟用」，比硬收 Done 的假完成有價值。減少 In Progress 的正道＝真的把東西部署上線（如今天 OPS 批次日清掉 2.4.4.1），非改狀態。
