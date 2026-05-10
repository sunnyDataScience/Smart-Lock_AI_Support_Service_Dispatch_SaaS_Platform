---
id: SF-DSP-02
title: Matching Algorithm
tier: 2
status: accepted
parent_bf: BF-0000-dispatch-overview
trace_to_flow: F-003
related:
  - "../../modules/dispatch-engine.md"
  - "../../modules/dispatch-engine-weights.md"
legacy_id: E5x--workflow-dispatch §2
---

# SF-DSP-02 — Matching Algorithm

> Dispatch BF 核心：媒合演算法。

## §2 媒合演算法實作規格 — 對應 F-003（核心）

### 2.1 問題

01-define/E3x--module-breakdown.md 定義了權重（40% 距離 + 30% 技能 + 20% 評分 + 10% 負載），但 02-design 缺乏實作細節。

### 2.2 評分公式

> 完整權重與 tie-breaker 規則：[[02-design/specs/dispatch-weights]]

```
total_score = W_dist × distance_score
            + W_skill × skill_score
            + W_rating × rating_score
            + W_load × load_score
            + bonus_same_tech
            + bonus_on_call
```

| 權重 | 代號 | 值 | 說明 |
|------|------|-----|------|
| 距離 | W_dist | 0.35 | 越近越好 |
| 技能 | W_skill | 0.30 | 品牌+型號完全匹配 |
| 評分 | W_rating | 0.20 | 歷史客戶評分 |
| 負載 | W_load | 0.15 | 當天已接單數越少越好 |
| 同一技師加分 | bonus_same_tech | +0.10 | 回頭客偏好同一技師 |
| 值班加分 | bonus_on_call | +0.05 | 當前時段為 on_call 的技師優先 |

### 2.3 各分項計算

```python
def calc_distance_score(distance_km: float) -> float:
    """距離分數：0-1，越近越高。"""
    if distance_km <= 5:
        return 1.0
    elif distance_km <= 15:
        return 0.8
    elif distance_km <= 30:
        return 0.6
    elif distance_km <= 50:
        return 0.3
    else:
        return 0.1  # >50km 仍可派但分數極低


def calc_skill_score(tech_skills: list[str], required_brand: str, required_model: str | None) -> float:
    """技能分數：品牌+型號完全匹配=1.0，僅品牌=0.7，無匹配=0。"""
    if required_model and f"{required_brand}:{required_model}" in tech_skills:
        return 1.0   # 品牌+型號完全匹配
    if required_brand in tech_skills:
        return 0.7   # 僅品牌匹配
    if "GENERAL" in tech_skills:
        return 0.3   # 通用技師
    return 0.0        # 無匹配


def calc_rating_score(avg_rating: float, total_jobs: int) -> float:
    """評分分數：考慮平均分 + 樣本數信心度。"""
    if total_jobs == 0:
        return 0.5  # 新技師給中間值
    confidence = min(total_jobs / 20, 1.0)  # 20 單以上視為可靠
    normalized = (avg_rating - 1) / 4        # 1-5 分映射到 0-1
    return normalized * confidence + 0.5 * (1 - confidence)  # 貝氏平滑


def calc_load_score(active_orders_today: int, max_concurrent: int) -> float:
    """負載分數：今天已接單越少越好。"""
    if max_concurrent == 0:
        return 0.0
    utilization = active_orders_today / max_concurrent
    return max(0, 1.0 - utilization)
```

### 2.4 完整媒合流程

```python
async def match_technician(
    tenant_id: str,
    work_order: WorkOrder,
    target_datetime: datetime,
) -> list[dict]:
    """回傳排序後的候選技師清單（最多 5 位）。"""

    # 1. 篩選：該租戶、有技能、有排班、可接單
    candidates = await db.fetch(
        """SELECT t.*, 
              AVG(r.rating) AS avg_rating, 
              COUNT(r.id) AS total_jobs,
              COUNT(wo.id) FILTER (WHERE wo.status IN ('assigned','accepted','en_route','in_progress')
                AND wo.scheduled_at::date = $3) AS active_today
           FROM technicians t
           LEFT JOIN customer_ratings r ON r.technician_id = t.id
           LEFT JOIN work_orders wo ON wo.technician_id = t.id
           WHERE t.tenant_id = $1 AND t.is_active = TRUE
           GROUP BY t.id""",
        tenant_id, work_order.device_brand, target_datetime.date(),
    )

    # 2. 過濾：排班可用性
    available = []
    for tech in candidates:
        if await is_technician_available(tech["id"], target_datetime, tenant_id):
            available.append(tech)

    # 3. 評分
    scored = []
    for tech in available:
        distance_km = await calc_distance(tech["service_area"], work_order.address)
        score = (
            0.35 * calc_distance_score(distance_km)
            + 0.30 * calc_skill_score(tech["skills"], work_order.device_brand, work_order.device_model)
            + 0.20 * calc_rating_score(tech["avg_rating"] or 3.0, tech["total_jobs"])
            + 0.15 * calc_load_score(tech["active_today"], 2)
        )
        # 加分項
        if await is_same_technician(work_order.line_user_id, tech["id"]):
            score += 0.10
        scored.append({"technician": tech, "score": round(score, 4), "distance_km": distance_km})

    # 4. 排序，回傳 Top 5
    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:5]
```

### 2.5 擴展搜索半徑

依 supplement §23.2 OP-09：

| 輪次 | 半徑 | 加價 | 等待時間 |
|------|------|------|---------|
| 第 1 輪 | 30 km | 無 | 5 分鐘 |
| 第 2 輪 | 50 km | +NT$200 車馬費 | 5 分鐘 |
| 第 3 輪 | 80 km | +NT$500 車馬費 | 5 分鐘 |
| 無人接單 | — | — | 轉管理者手動派工 |

### 2.6 緊急派工（Red_Code）

觸發條件：客戶被鎖門外、幼童反鎖、瓦斯爐開著。

| 項目 | 規則 |
|------|------|
| 偵測 | AI 分類 confidence >= 0.9 且 intent = RED_CODE |
| 媒合 | 跳過排班限制，直接推送最近的 on_call 技師 |
| 加價 | 緊急加價 NT$500 |
| SLA | 30 秒內推送技師、15 分鐘內接單 |
| 通知 | 同步推送 tenant_admin |

---

