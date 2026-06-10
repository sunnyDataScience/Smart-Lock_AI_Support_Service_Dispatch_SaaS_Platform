"""Realistic demo seed — 產生較大量、貼近真實營運情境的假資料。

設計目標：
- 讓 admin 後台每個 page 都有「足以呈現分組 / 篩選 / 排序」的資料量
- 台灣本地真實感（中文姓名 / 真實品牌型號 / 6 都市區地址 / 09xx 手機）
- 狀態分佈合理（80% 完工 / 15% 進行中 / 5% 取消，warranty 80% 期內 等）
- Deterministic：同一輸入產出同一 SQL，可重複 apply（ON CONFLICT DO NOTHING）

對應 admin 後台需要的呈現：
  /admin/dispatch-queue : work_orders 各 status
  /admin/customers      : users (line_user role) 50+
  /work-orders          : work_orders 80+
  /admin/refunds        : refund_requests 20
  /admin/warranty-claims: warranty_claims 30
  /admin/disputes       : disputes 15 (5 type 平均)
  /admin/inventory      : inventory_items 40
  /accounting           : invoices 60 + reconciliations 25 + settlements 25
  /technicians          : technicians 15 (mix status)

Usage:
    uv run python scripts/seed/realistic_demo_seed.py | \
      docker exec -i lock_AI psql -U lock -d lock_AI_data

    # 或先看：
    uv run python scripts/seed/realistic_demo_seed.py > /tmp/seed.sql
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta, timezone

# ─────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────

TENANT_ID = "00000000-0000-0000-0000-000000000001"
ADMIN_USER_ID = "c782bcfe-89bb-40b3-94b3-8c73d7bd0961"  # 對應 SQL/seeds/_admin_user.sql

NOW = datetime(2026, 6, 8, 12, 0, 0, tzinfo=timezone.utc)


def ts(days: int = 0, hours: int = 0) -> str:
    return (NOW + timedelta(days=days, hours=hours)).isoformat()


def dt_date(days: int = 0) -> str:
    return (NOW + timedelta(days=days)).date().isoformat()


# ─────────────────────────────────────────────────────────────────────
# Taiwan real-feel data pools
# ─────────────────────────────────────────────────────────────────────

FAMILY = "陳林黃張李王吳劉蔡楊許鄭謝郭洪邱曾廖賴徐周葉蘇莊呂江何蕭羅高潘簡朱鍾游彭詹胡施沈余趙盧梁顏柯孫魏翁韓杜方"
GIVEN_M = ["志強", "建華", "俊傑", "家豪", "志偉", "俊宏", "志明", "明哲", "宗翰", "柏翰",
           "承翰", "冠廷", "彥廷", "宇翔", "詠捷", "凱翔", "信宏", "孟翰", "宏毅", "建宏"]
GIVEN_F = ["美玲", "欣怡", "雅萍", "慧君", "美惠", "淑芬", "佩玲", "美玉", "麗華", "雅雯",
           "佳穎", "怡君", "婉婷", "雅婷", "宜君", "詩涵", "曉雯", "怡萱", "雅琪", "靜怡"]

CITIES = [
    ("台北市", ["信義區", "大安區", "松山區", "中山區", "中正區", "萬華區", "文山區", "南港區", "內湖區", "士林區", "北投區", "大同區"]),
    ("新北市", ["板橋區", "新莊區", "中和區", "永和區", "土城區", "三重區", "蘆洲區", "汐止區", "新店區", "淡水區", "樹林區"]),
    ("桃園市", ["桃園區", "中壢區", "平鎮區", "八德區", "龜山區", "蘆竹區", "大溪區", "楊梅區"]),
    ("台中市", ["北區", "西區", "南區", "東區", "中區", "西屯區", "北屯區", "南屯區", "豐原區"]),
    ("台南市", ["中西區", "東區", "南區", "北區", "安平區", "安南區", "永康區"]),
    ("高雄市", ["三民區", "苓雅區", "前金區", "新興區", "鼓山區", "鹽埕區", "左營區", "前鎮區"]),
]

STREETS = ["中正路", "中山路", "民生路", "民權路", "民族路", "建國路", "復興路",
           "和平路", "忠孝路", "仁愛路", "信義路", "光復路", "文化路", "成功路",
           "大同路", "中華路", "南京路", "敦化路", "重慶路", "永康街", "瑞光路"]

# (brand, [models])
DEVICES = [
    ("Yale", ["YDM-4109", "YDM-3119", "YDR-3110", "YDM-7220"]),
    ("Samsung", ["SHP-DP609", "SHP-DR719", "SHP-DH538", "SHP-DR708"]),
    ("Gateman", ["WV-200", "Z-10", "F50-FH", "ARO-2000"]),
    ("美樂", ["ENTR", "Pulse", "Glory", "Touch"]),
    ("Dormakaba", ["SafeRoute", "Saflok-Quantum", "EVOLO-X"]),
    ("Chatlock", ["AI-99", "Pro-X1", "S5", "Mini-3"]),
    ("Philips", ["DDL702", "DDL603", "EasyKey-7300"]),
    ("Xiaomi", ["小米智能門鎖 Pro", "米家智能門鎖 1S", "Push-Pull"]),
]

CATEGORIES = ["電池", "WiFi 連線", "密碼", "指紋辨識", "卡片", "安裝", "故障", "聲音異常"]
URGENCIES = ["normal"] * 6 + ["high"] * 3 + ["critical"] + ["low"] * 2

SYMPTOMS = {
    "電池": ["顯示電量低但更換後仍無法開機", "電池更換頻率異常高", "電池蓋鬆動", "新電池放入無反應"],
    "WiFi 連線": ["APP 無法連線", "離線狀態顯示異常", "重設 WiFi 後仍無法連接", "頻繁斷線"],
    "密碼": ["密碼輸入正確但無法解鎖", "密碼設定後無法儲存", "刪除密碼失敗", "密碼鍵失靈"],
    "指紋辨識": ["指紋登錄成功但辨識失敗", "需多次掃描才能解鎖", "指紋區域反應慢", "辨識區域刮痕"],
    "卡片": ["磁卡感應距離變短", "感應後無反應", "卡片無法新增", "新卡片無法登錄"],
    "安裝": ["新成屋安裝需求", "更換舊鎖", "外觀切割需確認", "門板厚度不符"],
    "故障": ["旋鈕轉動無反應", "馬達聲音正常但門栓未動作", "螢幕無顯示", "鎖芯卡住"],
    "聲音異常": ["按鍵時無提示音", "解鎖音量過大", "持續發出嗶聲", "蜂鳴器壞掉"],
}

WO_STATUS_DIST = (
    [("completed", 30), ("confirmed", 20), ("in_progress", 8), ("assigned", 6),
     ("accepted", 4), ("created", 6), ("cancelled", 4)]
)

INVENTORY_CATEGORIES = ["mortise_lock", "smart_lock", "deadbolt", "padlock", "accessory", "tool", "battery"]
PARTS = [
    ("Yale YDM-4109 主機板", "YALE-YDM4109-PCB"),
    ("Samsung SHP-DP609 馬達", "SAMSUNG-DP609-MOTOR"),
    ("Gateman WV-200 把手", "GATEMAN-WV200-HANDLE"),
    ("美樂 ENTR 鋰電池組", "MIWA-ENTR-BATT"),
    ("Dormakaba SafeRoute 主板", "KABA-SR-MB"),
    ("Chatlock AI-99 指紋模組", "CHATLOCK-AI99-FP"),
    ("Philips DDL702 鎖芯", "PHILIPS-DDL702-CYL"),
    ("Xiaomi 智能鎖 Pro 螢幕", "XIAOMI-PRO-LCD"),
    ("通用電池 4 號 (8 入)", "BATT-AA-8PK"),
    ("通用電池 3 號 (8 入)", "BATT-AAA-8PK"),
    ("專用螺絲組 (50 入)", "SCREW-SET-50"),
    ("拆鎖工具組", "TOOL-LOCK-PRY"),
    ("六角扳手組", "TOOL-HEX-SET"),
    ("鎖芯潤滑劑", "LUB-LOCK-100ML"),
    ("3M 雙面膠", "ADHESIVE-3M-VHB"),
]


# ─────────────────────────────────────────────────────────────────────
# Deterministic helpers
# ─────────────────────────────────────────────────────────────────────

def uid(prefix: str, idx: int, sub: str = "0") -> str:
    """生成 deterministic UUID (用 prefix + idx，方便 trace)。"""
    base = f"{prefix:>4s}".replace(" ", "0")[:4]
    return f"{base}{idx % 10000:04d}-{int(sub) % 10000:04d}-4{idx % 1000:03d}-8{idx % 1000:03d}-{idx % 1000000000000:012d}"


def name(idx: int) -> str:
    fam = FAMILY[idx % len(FAMILY)]
    if idx % 2:
        gv = GIVEN_M[idx % len(GIVEN_M)]
    else:
        gv = GIVEN_F[idx % len(GIVEN_F)]
    return fam + gv


def phone(idx: int) -> str:
    # 純數字 10 碼,對齊 Technician/Customer pydantic 的 `^09\d{8}$` regex。
    # 之前格式 09NN-NNN-NNN 帶 dash 會讓 GET /tenants/{tid}/technicians 反序列化炸 500。
    return f"09{(11 + idx * 7) % 90 + 10:02d}{(123 + idx * 31) % 1000:03d}{(456 + idx * 71) % 1000:03d}"


def address(idx: int) -> str:
    city, dists = CITIES[idx % len(CITIES)]
    d = dists[(idx * 3) % len(dists)]
    st = STREETS[(idx * 7) % len(STREETS)]
    no = (idx * 13 + 11) % 300 + 1
    floor = (idx % 12) + 1
    return f"{city}{d}{st}{no}號{floor}樓"


def line_uid(idx: int) -> str:
    import hashlib
    return "U" + hashlib.md5(f"demo-line-uid-{idx}".encode()).hexdigest()


def device(idx: int) -> tuple[str, str]:
    b, models = DEVICES[idx % len(DEVICES)]
    m = models[(idx // len(DEVICES)) % len(models)]
    return b, m


def category(idx: int) -> str:
    return CATEGORIES[idx % len(CATEGORIES)]


def symptom(cat: str, idx: int) -> str:
    pool = SYMPTOMS[cat]
    return pool[idx % len(pool)]


def urgency(idx: int) -> str:
    return URGENCIES[idx % len(URGENCIES)]


# ─────────────────────────────────────────────────────────────────────
# SQL writers
# ─────────────────────────────────────────────────────────────────────

def q(v):
    if v is None:
        return "NULL"
    if isinstance(v, bool):
        return "TRUE" if v else "FALSE"
    if isinstance(v, (int, float)):
        return str(v)
    s = str(v).replace("'", "''")
    return f"'{s}'"


def emit_header():
    print("-- =============================================================")
    print("-- Realistic demo seed — 大量、貼近真實營運的展示資料")
    print(f"-- Generated at: {NOW.isoformat()}")
    print(f"-- Tenant: {TENANT_ID}")
    print("-- =============================================================")
    print("BEGIN;")
    print()


def emit_footer():
    print()
    print("COMMIT;")
    print("-- end of realistic demo seed")


# ─────────────────────────────────────────────────────────────────────
# Generators
# ─────────────────────────────────────────────────────────────────────

def emit_customers(n: int = 50) -> list[str]:
    """LINE 客戶（users.role='line_user'）。"""
    print("-- ── customers (LINE users) ──")
    ids = []
    for i in range(n):
        uid_ = f"cccc{i:04d}-0001-4cc1-8cc1-{i:012d}"
        ids.append(uid_)
        risk = ["low", "low", "low", "medium", "medium", "high", "critical", None, None, None][i % 10]
        warranty = ["active", "active", "expired", "none", None, None, None][i % 7]
        sql = (
            "INSERT INTO users (id, tenant_id, line_user_id, display_name, phone, address, role, "
            "is_active, last_active_at, risk_level, warranty_status, primary_device_brand, created_at) VALUES ("
            f"{q(uid_)}::uuid, {q(TENANT_ID)}::uuid, {q(line_uid(i))}, {q(name(i))}, "
            f"{q(phone(i))}, {q(address(i))}, 'line_user', TRUE, "
            f"{q(ts(days=-(i % 60), hours=-(i % 12)))}, {q(risk)}, {q(warranty)}, "
            f"{q(DEVICES[i % len(DEVICES)][0])}, {q(ts(days=-(i % 365)))}"
            ") ON CONFLICT (id) DO NOTHING;"
        )
        print(sql)
    print()
    return ids


def emit_technicians(n: int = 12) -> list[str]:
    """技師（users role='technician' + technicians 表）。"""
    print("-- ── technicians ──")
    ids = []
    for i in range(n):
        uuid = f"7777{i:04d}-0001-4777-8777-{i:012d}"
        user_uuid = f"77a7{i:04d}-0001-4aa7-8aa7-{i:012d}"
        status = ["active", "active", "active", "active", "pending_approval", "suspended", "inactive"][i % 7]
        rating = round(3.5 + ((i * 13) % 15) * 0.1, 1)
        completed = (i * 17 + 5) % 200
        caps = '["Yale", "Samsung"]' if i % 2 else '["Gateman", "Dormakaba"]'
        regions = '["台北市", "新北市"]' if i % 3 == 0 else '["桃園市", "新竹縣"]' if i % 3 == 1 else '["台中市"]'

        # users row
        print(
            "INSERT INTO users (id, tenant_id, email, display_name, phone, role, is_active, created_at) VALUES ("
            f"{q(user_uuid)}::uuid, {q(TENANT_ID)}::uuid, {q(f'tech-{i:02d}@example.com')}, "
            f"{q(name(i + 100))}, {q(phone(i + 100))}, 'technician', "
            f"{q(status == 'active')}, {q(ts(days=-(i * 7 + 30)))}"
            ") ON CONFLICT (id) DO NOTHING;"
        )

        print(
            "INSERT INTO technicians (id, user_id, name, phone, email, capabilities, service_regions, "
            "rating, completed_orders, status, created_at) VALUES ("
            f"{q(uuid)}::uuid, {q(user_uuid)}::uuid, {q(name(i + 100))}, {q(phone(i + 100))}, "
            f"{q(f'tech-{i:02d}@example.com')}, {q(caps)}::jsonb, {q(regions)}::jsonb, "
            f"{rating}, {completed}, {q(status)}, {q(ts(days=-(i * 7 + 30)))}"
            ") ON CONFLICT (id) DO NOTHING;"
        )
        ids.append(uuid)
    print()
    return ids


def emit_problem_cards_and_work_orders(
    customer_ids: list[str], technician_ids: list[str], n: int = 80,
) -> tuple[list[str], list[str]]:
    """每張工單對應一張 problem_card，狀態分佈合理。"""
    print("-- ── problem_cards + conversations + work_orders ──")

    # build status pool
    status_pool: list[str] = []
    for st, cnt in WO_STATUS_DIST:
        status_pool.extend([st] * cnt)
    while len(status_pool) < n:
        status_pool.append("completed")
    status_pool = status_pool[:n]

    pc_ids: list[str] = []
    wo_ids: list[str] = []

    for i in range(n):
        cust = customer_ids[i % len(customer_ids)]
        brand, model = device(i)
        cat = category(i)
        sym = symptom(cat, i)
        urg = urgency(i)
        days_ago = (i * 3 + 1) % 60

        # conversation
        conv_id = f"abca{i:04d}-0002-4aec-8aec-{i:012d}"
        print(
            "INSERT INTO conversations (id, user_id, session_id, status, channel, started_at, created_at) VALUES ("
            f"{q(conv_id)}::uuid, {q(cust)}::uuid, {q(f'sess-demo-{i:04d}')}, "
            f"'escalated', 'line', {q(ts(days=-days_ago, hours=-2))}, {q(ts(days=-days_ago, hours=-2))}"
            ") ON CONFLICT (id) DO NOTHING;"
        )

        # problem card
        pc_id = f"abc1{i:04d}-0001-4abc-8abc-{i:012d}"
        pc_ids.append(pc_id)
        addr = address(i + 5)
        symptoms_json = '["' + sym.replace('"', '\\"') + '"]'
        print(
            "INSERT INTO problem_cards (id, conversation_id, location, brand, model, category, symptoms, "
            "urgency, status, created_at, updated_at) VALUES ("
            f"{q(pc_id)}::uuid, {q(conv_id)}::uuid, {q(addr)}, {q(brand)}, {q(model)}, "
            f"{q(cat)}, {q(symptoms_json)}::jsonb, {q(urg)}, 'resolved', "
            f"{q(ts(days=-days_ago, hours=-1))}, {q(ts(days=-days_ago))}"
            ") ON CONFLICT (id) DO NOTHING;"
        )

        # work order
        wo_id = f"abc2{i:04d}-0001-4abe-8abe-{i:012d}"
        wo_ids.append(wo_id)
        status = status_pool[i]
        # only assign tech if past 'created'
        tech_id = technician_ids[i % len(technician_ids)] if status not in ("created", "cancelled") else None
        priority = "urgent" if urg == "critical" else ("high" if urg == "high" else "normal")
        scheduled = ts(days=-days_ago + 1) if status not in ("created",) else None
        completed_at = ts(days=-days_ago + 2) if status in ("completed", "confirmed") else None
        est_price = 1500 + (i * 137 % 4000)
        final_price = est_price + (i * 23 % 600) - 200 if status in ("completed", "confirmed") else None
        rating = (1 + (i * 11) % 5) if status == "confirmed" else None
        feedback = ["服務專業迅速", "技師很有耐心", "解決問題很徹底", "價格合理", "現場很乾淨"][i % 5] if status == "confirmed" else None
        customer_name = name(i % 50)
        customer_phone_str = phone(i % 50)

        print(
            "INSERT INTO work_orders (id, problem_card_id, technician_id, created_by, status, priority, "
            "customer_name, customer_phone, customer_address, scheduled_at, completed_at, "
            "estimated_price, final_price, rating, feedback, created_at, updated_at) VALUES ("
            f"{q(wo_id)}::uuid, {q(pc_id)}::uuid, "
            f"{q(tech_id) + '::uuid' if tech_id else 'NULL'}, {q(ADMIN_USER_ID)}::uuid, "
            f"{q(status)}, {q(priority)}, {q(customer_name)}, {q(customer_phone_str)}, {q(addr)}, "
            f"{q(scheduled)}, {q(completed_at)}, "
            f"{est_price}, {final_price if final_price is not None else 'NULL'}, "
            f"{rating if rating is not None else 'NULL'}, {q(feedback)}, "
            f"{q(ts(days=-days_ago))}, {q(ts(days=-days_ago + 3))}"
            ") ON CONFLICT (id) DO NOTHING;"
        )
    print()
    return pc_ids, wo_ids


def emit_invoices(wo_ids: list[str], n: int = 60) -> list[str]:
    print("-- ── invoices ──")
    ids = []
    statuses = ["paid"] * 35 + ["issued"] * 18 + ["draft"] * 5 + ["cancelled"] * 2
    payments = ["bank_transfer", "credit_card", "line_pay", "cash", "credit_card"]
    for i in range(min(n, len(wo_ids))):
        inv_id = f"abc3{i:04d}-0001-4abf-8abf-{i:012d}"
        ids.append(inv_id)
        wo = wo_ids[i]
        amt = 1500 + (i * 173 % 5000)
        tax = round(amt * 0.05, 2)
        total = amt + tax
        status = statuses[i % len(statuses)]
        days_ago = (i * 4 + 5) % 90
        issued = ts(days=-days_ago) if status in ("issued", "paid") else None
        paid = ts(days=-days_ago + 2) if status == "paid" else None
        pm = payments[i % len(payments)] if status == "paid" else None
        line_items = (
            '[{"name":"基本服務費","price":' + str(amt - 500)
            + ',"qty":1},{"name":"零件成本","price":500,"qty":1}]'
        )
        print(
            "INSERT INTO invoices (id, work_order_id, invoice_number, amount, tax, total, status, "
            "line_items, payment_method, issued_at, paid_at, created_at) VALUES ("
            f"{q(inv_id)}::uuid, {q(wo)}::uuid, {q(f'INV-2026-{(i + 1000):05d}')}, "
            f"{amt}, {tax}, {total}, {q(status)}, {q(line_items)}::jsonb, "
            f"{q(pm)}, {q(issued)}, {q(paid)}, {q(ts(days=-days_ago - 1))}"
            ") ON CONFLICT (id) DO NOTHING;"
        )
    print()
    return ids


def emit_warranty_claims(customer_ids: list[str], wo_ids: list[str], n: int = 30):
    print("-- ── warranty_claims ──")
    statuses = ["filed"] * 8 + ["in_progress"] * 7 + ["approved"] * 10 + ["rejected"] * 5
    for i in range(n):
        wc_id = f"abc4{i:04d}-0001-4acd-8acd-{i:012d}"
        cust = customer_ids[i % len(customer_ids)]
        wo = wo_ids[i % len(wo_ids)] if i % 4 != 0 else None
        brand, model = device(i + 2)
        start = NOW.date() - timedelta(days=(i * 30 + 100) % 700)
        end = start + timedelta(days=365 * 2)  # 2 年保固
        claim = NOW.date() - timedelta(days=(i * 13) % 60)
        within = claim <= end
        status = statuses[i % len(statuses)]
        reason = ["螢幕反白", "馬達異音", "電池快速消耗", "指紋無法辨識", "WiFi 斷線", "卡片感應失靈"][i % 6]
        verification = "技師現場確認" if status in ("approved", "in_progress") else None
        resolution = "免費換新" if status == "approved" else ("拒絕：人為損壞" if status == "rejected" else None)
        discount = 0 if status == "approved" else None

        print(
            "INSERT INTO warranty_claims (id, document_number, work_order_id, customer_id, device_brand, "
            "device_model, warranty_start_date, warranty_end_date, claim_date, is_within_warranty, "
            "status, dispute_reason, verification_source, resolution, discount_offered, created_at) VALUES ("
            f"{q(wc_id)}::uuid, {q(f'WC-20260{(i + 600):04d}')}, "
            f"{q(wo) + '::uuid' if wo else 'NULL'}, {q(cust)}::uuid, "
            f"{q(brand)}, {q(model)}, {q(start.isoformat())}, {q(end.isoformat())}, "
            f"{q(claim.isoformat())}, {q(within)}, {q(status)}, "
            f"{q(reason)}, {q(verification)}, {q(resolution)}, "
            f"{discount if discount is not None else 'NULL'}, {q(ts(days=-(i * 2 + 1) % 45))}"
            ") ON CONFLICT (id) DO NOTHING;"
        )
    print()


def emit_disputes(customer_ids: list[str], wo_ids: list[str], n: int = 18):
    print("-- ── disputes ──")
    types = ["pricing", "quality", "warranty", "cancellation_fee", "settlement"]
    statuses = ["filed"] * 4 + ["in_review"] * 6 + ["resolved"] * 5 + ["rejected"] * 3
    for i in range(n):
        d_id = f"abc5{i:04d}-0001-4ace-8ace-{i:012d}"
        dt = types[i % len(types)]
        st = statuses[i % len(statuses)]
        wo = wo_ids[i % len(wo_ids)]
        cust = customer_ids[i % len(customer_ids)]
        desc = {
            "pricing": "完工金額與報價落差過大，要求說明",
            "quality": "完工後 3 日內仍出現原問題",
            "warranty": "保固期內維修被要求收費，需澄清",
            "cancellation_fee": "前一日已通知取消，仍被收取出工費",
            "settlement": "結算明細與實際工單數不符",
        }[dt]
        res_amount = (i * 200 + 100) if st in ("resolved",) else None
        resolution = "雙方協商給予 20% 折扣補償" if st == "resolved" else None
        print(
            "INSERT INTO disputes (id, work_order_id, filed_by, dispute_type, status, "
            "description, resolution, resolution_amount, filed_at, created_at) VALUES ("
            f"{q(d_id)}::uuid, {q(wo)}::uuid, {q(cust)}::uuid, "
            f"{q(dt)}, {q(st)}, {q(desc)}, "
            f"{q(resolution)}, {res_amount if res_amount is not None else 'NULL'}, "
            f"{q(ts(days=-(i * 2 + 1)))}, {q(ts(days=-(i * 2 + 1)))}"
            ") ON CONFLICT (id) DO NOTHING;"
        )
    print()


def emit_reconciliations_settlements(technician_ids: list[str], n: int = 25):
    print("-- ── reconciliations + settlements ──")
    statuses = ["approved"] * 18 + ["pending"] * 5 + ["disputed"] * 2
    pay_statuses = ["paid"] * 18 + ["pending"] * 6 + ["failed"] * 1
    for i in range(n):
        r_id = f"abc6{i:04d}-0001-4adb-8adb-{i:012d}"
        s_id = f"abc7{i:04d}-0001-4adc-8adc-{i:012d}"
        tech = technician_ids[i % len(technician_ids)]
        ps = NOW.replace(day=1) - timedelta(days=30 * (i % 6))
        pe = (ps + timedelta(days=30)).replace(day=1)
        orders = 5 + (i * 3) % 25
        revenue = orders * (2000 + (i * 17) % 800)
        platform = round(revenue * 0.2, 2)
        payout = revenue - platform
        st = statuses[i % len(statuses)]
        ps_str = ps.isoformat()
        pe_str = pe.isoformat()
        approved_at = ts(days=-(i * 5) % 60) if st == "approved" else None

        print(
            "INSERT INTO reconciliations (id, technician_id, period_start, period_end, total_orders, "
            "total_revenue, platform_fee, technician_payout, status, approved_by, approved_at, created_at) VALUES ("
            f"{q(r_id)}::uuid, {q(tech)}::uuid, {q(ps_str)}, {q(pe_str)}, {orders}, "
            f"{revenue}, {platform}, {payout}, {q(st)}, "
            f"{q(ADMIN_USER_ID) + '::uuid' if approved_at else 'NULL'}, "
            f"{q(approved_at)}, {q(ts(days=-(i * 5 + 5) % 90))}"
            ") ON CONFLICT (id) DO NOTHING;"
        )
        ps2 = pay_statuses[i % len(pay_statuses)]
        paid_at = ts(days=-(i * 5) % 60 + 3) if ps2 == "paid" else None
        print(
            "INSERT INTO settlements (id, reconciliation_id, technician_id, amount, currency, status, "
            "payment_method, paid_at, created_at) VALUES ("
            f"{q(s_id)}::uuid, {q(r_id)}::uuid, {q(tech)}::uuid, {payout}, 'TWD', "
            f"{q(ps2)}, 'bank_transfer', {q(paid_at)}, {q(ts(days=-(i * 5 + 5) % 90))}"
            ") ON CONFLICT (id) DO NOTHING;"
        )
    print()


def emit_inventory(n: int = 40):
    print("-- ── inventory_items ──")
    for i in range(n):
        item_id = f"abc8{i:04d}-0001-4adf-8adf-{i:012d}"
        part_name, part_no = PARTS[i % len(PARTS)]
        if i >= len(PARTS):
            part_name = f"{part_name} (備品 {i})"
            part_no = f"{part_no}-{i:02d}"
        qty = max(0, 50 - (i * 7) % 60)
        reorder = 10
        unit_cost = 100 + (i * 73) % 2400
        cat = INVENTORY_CATEGORIES[i % len(INVENTORY_CATEGORIES)]
        print(
            "INSERT INTO inventory_items (id, name, part_number, category, unit_cost, "
            "quantity_on_hand, reorder_point, supplier, created_at) VALUES ("
            f"{q(item_id)}::uuid, {q(part_name)}, {q(part_no)}, {q(cat)}, {unit_cost}, "
            f"{qty}, {reorder}, {q('原廠代理商' if i % 2 == 0 else '第三方供應商')}, "
            f"{q(ts(days=-(i * 4 + 1) % 200))}"
            ") ON CONFLICT (part_number) DO NOTHING;"
        )
    print()


def emit_refunds(customer_ids: list[str], wo_ids: list[str], invoice_ids: list[str], n: int = 20):
    print("-- ── refund_requests ──")
    decisions = ["approved"] * 10 + ["pending"] * 6 + ["rejected"] * 4
    for i in range(n):
        rf_id = f"abc9{i:04d}-0001-4aeb-8aeb-{i:012d}"
        cust = customer_ids[i % len(customer_ids)]
        wo = wo_ids[i % len(wo_ids)]
        amt = 500 + (i * 271) % 3500
        reason = ["服務未達預期", "技師未到場", "重複收費", "保固期內被收費", "客戶取消"][i % 5]
        decision = decisions[i % len(decisions)]
        print(
            "INSERT INTO refund_requests (id, work_order_id, requested_by, amount, reason, status, created_at) VALUES ("
            f"{q(rf_id)}::uuid, {q(wo)}::uuid, {q(cust)}::uuid, "
            f"{amt}, {q(reason)}, {q(decision)}, {q(ts(days=-(i * 2 + 1) % 30))}"
            ") ON CONFLICT (id) DO NOTHING;"
        )
    print()


# ─────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--customers", type=int, default=50)
    parser.add_argument("--technicians", type=int, default=12)
    parser.add_argument("--work-orders", type=int, default=80)
    parser.add_argument("--invoices", type=int, default=60)
    parser.add_argument("--warranty-claims", type=int, default=30)
    parser.add_argument("--disputes", type=int, default=18)
    parser.add_argument("--reconciliations", type=int, default=25)
    parser.add_argument("--inventory", type=int, default=40)
    parser.add_argument("--refunds", type=int, default=20)
    args = parser.parse_args()

    emit_header()

    cust_ids = emit_customers(args.customers)
    tech_ids = emit_technicians(args.technicians)
    pc_ids, wo_ids = emit_problem_cards_and_work_orders(cust_ids, tech_ids, args.work_orders)
    inv_ids = emit_invoices(wo_ids, args.invoices)
    emit_warranty_claims(cust_ids, wo_ids, args.warranty_claims)
    emit_disputes(cust_ids, wo_ids, args.disputes)
    emit_reconciliations_settlements(tech_ids, args.reconciliations)
    emit_inventory(args.inventory)
    emit_refunds(cust_ids, wo_ids, inv_ids, args.refunds)

    emit_footer()

    print(
        f"\n-- ✓ Seeded ~{args.customers} customers, {args.technicians} technicians, "
        f"{args.work_orders} work_orders, {args.invoices} invoices, "
        f"{args.warranty_claims} warranty_claims, {args.disputes} disputes, "
        f"{args.reconciliations} reconciliations, {args.inventory} inventory items, "
        f"{args.refunds} refunds",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
