#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Smart Lock 平台 — drawio 架構圖生成器
=========================================
依 drawio/README.md 全域視覺規範 + 各子資料夾 prompt.md,
生成 16 張 Smart Lock AI 客服與派工 SaaS 平台架構圖(正典來源 smartlock-docs/enterprise/)。

輸出:
  1. drawio/smartlock-platform-architecture.drawio   ← 單檔多分頁,一次匯入全部 16 張
  2. 各子資料夾同名單張檔 (依 README 命名慣例,如 03-1_container.drawio)

執行:  python3 _build_drawio.py
"""

import html
import math
import os

BASE = os.path.dirname(os.path.abspath(__file__))

# ---------------------------------------------------------------------------
# 全域配色 (README「配色」表) — (fill, stroke)
# ---------------------------------------------------------------------------
FILL = {
    "red":    ("#F8CECC", "#B85450"),   # 即時客服熱路徑
    "blue":   ("#DAE8FC", "#6C8EBF"),   # 品牌後台營運
    "green":  ("#D5E8D4", "#82B366"),   # 平台共用服務
    "teal":   ("#B0E3E6", "#0E8088"),   # 獨立子系統 technician-platform / knowledge-refinery
    "orange": ("#FFE6CC", "#D79B00"),   # 知識 / AI 能力資產
    "yellow": ("#FFF2CC", "#D6B656"),   # 設計態 / DSL / Vertical Pack
    "gray":   ("#F5F5F5", "#666666"),   # 外部實體 / actor
    "purple": ("#E1D5E7", "#9673A6"),   # Data Store
    "white":  ("#FFFFFF", "#666666"),   # 中性容器 / 圖例
}

# ---------------------------------------------------------------------------
# 形狀 style
# ---------------------------------------------------------------------------
def rrect(color):                       # 元件 / 程序 = 圓角矩形
    f, s = FILL[color]
    return f"rounded=1;whiteSpace=wrap;html=1;fillColor={f};strokeColor={s};"

def rect(color):                        # 外部實體 / 系統 = 直角矩形
    f, s = FILL[color]
    return f"whiteSpace=wrap;html=1;fillColor={f};strokeColor={s};"

def cyl(color="purple"):                # 資料儲存 = 圓柱
    f, s = FILL[color]
    return (f"shape=cylinder3;whiteSpace=wrap;html=1;boundedLbl=1;"
            f"backgroundOutline=1;size=12;fillColor={f};strokeColor={s};")

def actor(color="gray"):                # 人 / 角色 = actor
    f, s = FILL[color]
    return (f"shape=umlActor;verticalLabelPosition=bottom;verticalAlign=top;"
            f"html=1;outlineConnect=0;fillColor={f};strokeColor={s};")

def container(color, dashed=False):     # 分層 / 部署區 / 子系統 = 群組框 (標題置頂)
    f, s = FILL[color]
    d = "dashed=1;" if dashed else ""
    return (f"rounded=1;whiteSpace=wrap;html=1;fillColor={f};strokeColor={s};"
            f"verticalAlign=top;fontStyle=1;fontSize=13;container=1;collapsible=0;{d}")

def swim(color, start=40, horizontal=0):  # swimlane (層)
    f, s = FILL[color]
    return (f"swimlane;html=1;whiteSpace=wrap;horizontal={horizontal};startSize={start};"
            f"fillColor={f};strokeColor={s};fontStyle=1;fontSize=13;container=1;collapsible=0;")

def band(color):                        # 標語 / 註記橫幅
    f, s = FILL[color]
    return f"rounded=0;whiteSpace=wrap;html=1;fillColor={f};strokeColor={s};fontStyle=1;"

def arrow_down(color="yellow"):         # 縱向粗箭頭 (脊椎)
    f, s = FILL[color]
    return (f"shape=singleArrow;direction=south;whiteSpace=wrap;html=1;"
            f"fillColor={f};strokeColor={s};fontStyle=1;arrowWidth=0.5;arrowSize=0.25;")

def note(color="yellow"):               # 小卡 / 註記
    f, s = FILL[color]
    return (f"rounded=1;whiteSpace=wrap;html=1;fillColor={f};strokeColor={s};"
            f"align=left;verticalAlign=top;fontSize=11;dashed=1;")

def txt(align="left"):                   # 純文字
    return f"text;html=1;strokeColor=none;fillColor=none;align={align};verticalAlign=middle;"

def state_style(color):                  # UML 狀態
    f, s = FILL[color]
    return f"rounded=1;arcSize=40;whiteSpace=wrap;html=1;fillColor={f};strokeColor={s};"


def ref_zone(header_fill="#F8FAFC", stroke="#CBD5E1"):
    """06 高階參考架構的 L1 責任區：白底、淡色表頭、低裝飾。"""
    return (
        "swimlane;html=1;whiteSpace=wrap;horizontal=1;startSize=36;"
        f"fillColor=#FFFFFF;swimlaneFillColor={header_fill};strokeColor={stroke};"
        "fontColor=#0F172A;fontStyle=1;fontSize=12;container=1;collapsible=0;"
    )


def ref_component(stroke="#64748B", fill="#FFFFFF", dashed=False):
    d = "dashed=1;dashPattern=5 4;" if dashed else ""
    return (
        "rounded=1;arcSize=8;whiteSpace=wrap;html=1;"
        f"fillColor={fill};strokeColor={stroke};fontColor=#0F172A;"
        f"fontSize=10;spacing=5;{d}"
    )


def ref_store(stroke="#EA580C"):
    return (
        "rounded=1;arcSize=8;whiteSpace=wrap;html=1;"
        f"fillColor=#FFF7ED;strokeColor={stroke};fontColor=#7C2D12;"
        "fontSize=9;spacing=4;"
    )


def ref_card(stroke, fill):
    return (
        "rounded=1;arcSize=6;whiteSpace=wrap;html=1;align=left;verticalAlign=top;"
        f"fillColor={fill};strokeColor={stroke};fontColor=#0F172A;"
        "fontSize=9;spacingTop=7;spacingLeft=8;spacingRight=6;"
    )

# ---------------------------------------------------------------------------
# 線型 style (README「線型」)
# ---------------------------------------------------------------------------
# 直線路由(非 orthogonal):讓多條線從節點各自角度散開,不會被正交繞線疊到同一軌道。
# 節點座標已對「直線穿越」最佳化(見 _analyze_layout.py),故直線 pierce 亦低。
E_MAIN  = "html=1;strokeWidth=2.5;endArrow=classic;endFill=1;strokeColor=#333333;fontSize=10;"          # 即時主資料鏈
E_SOLID = "html=1;endArrow=classic;endFill=1;strokeColor=#555555;fontSize=10;"                          # 設計態發布 (一般實線)
E_DASH  = "html=1;endArrow=classic;dashed=1;strokeColor=#6C8EBF;fontSize=10;"                           # 學習態回流 (虛線)
E_DOT   = "html=1;endArrow=open;dashed=1;dashPattern=1 4;strokeColor=#999999;fontSize=10;"              # 橫切支撐 (點線)
E_STATE = "edgeStyle=orthogonalEdgeStyle;rounded=1;html=1;endArrow=classic;endFill=1;strokeColor=#555555;fontSize=10;"                    # 狀態轉移(狀態圖保留正交)
E_STRAIGHT = "html=1;endArrow=classic;endFill=1;strokeColor=#333333;fontSize=10;"                                                          # 直線 (sequence)

# 06 高階參考架構專用資料路徑。
# 工業視覺語意轉譯：Video→即時互動、Metadata→領域事件、Control→治理、Storage→重播/證據。
E_REF_INTERACTION = (
    "edgeStyle=orthogonalEdgeStyle;rounded=1;orthogonalLoop=1;jettySize=auto;"
    "html=1;strokeWidth=2.5;endArrow=classic;endFill=1;"
    "strokeColor=#2563EB;fontColor=#1E3A8A;fontSize=9;"
)
E_REF_EVENT = (
    "edgeStyle=orthogonalEdgeStyle;rounded=1;orthogonalLoop=1;jettySize=auto;"
    "html=1;strokeWidth=2;endArrow=classic;endFill=1;dashed=1;dashPattern=6 4;"
    "strokeColor=#16A34A;fontColor=#166534;fontSize=9;"
)
E_REF_CONTROL = (
    "edgeStyle=orthogonalEdgeStyle;rounded=1;orthogonalLoop=1;jettySize=auto;"
    "html=1;strokeWidth=2;endArrow=open;endFill=0;dashed=1;dashPattern=3 4;"
    "strokeColor=#9333EA;fontColor=#6B21A8;fontSize=9;"
)
E_REF_STORAGE = (
    "edgeStyle=orthogonalEdgeStyle;rounded=1;orthogonalLoop=1;jettySize=auto;"
    "html=1;strokeWidth=2;endArrow=classic;endFill=1;dashed=1;dashPattern=8 4;"
    "strokeColor=#EA580C;fontColor=#9A3412;fontSize=9;"
)


# ---------------------------------------------------------------------------
# 低階建構
# ---------------------------------------------------------------------------
def esc(s):
    return html.escape(str(s), quote=True)

def node(cid, value, x, y, w, h, style, parent="1"):
    return (f'<mxCell id="{cid}" value="{esc(value)}" style="{style}" vertex="1" '
            f'parent="{parent}"><mxGeometry x="{x}" y="{y}" width="{w}" height="{h}" '
            f'as="geometry"/></mxCell>')

def edge(cid, src, tgt, value, style, parent="1", pts=None, exit=None, entry=None):
    st = style
    if exit:
        st += f"exitX={exit[0]};exitY={exit[1]};exitDx=0;exitDy=0;"
    if entry:
        st += f"entryX={entry[0]};entryY={entry[1]};entryDx=0;entryDy=0;"
    if pts:
        arr = "".join(f'<mxPoint x="{px}" y="{py}"/>' for px, py in pts)
        geo = f'<mxGeometry relative="1" as="geometry"><Array as="points">{arr}</Array></mxGeometry>'
    else:
        geo = '<mxGeometry relative="1" as="geometry"/>'
    return (f'<mxCell id="{cid}" value="{esc(value)}" style="{st}" edge="1" '
            f'parent="{parent}" source="{src}" target="{tgt}">{geo}</mxCell>')

def free_edge(cid, x1, y1, x2, y2, value, style, parent="1", dash=False):
    st = style + ("dashed=1;" if dash else "")
    return (f'<mxCell id="{cid}" value="{esc(value)}" style="{st}" edge="1" parent="{parent}">'
            f'<mxGeometry relative="1" as="geometry">'
            f'<mxPoint x="{x1}" y="{y1}" as="sourcePoint"/>'
            f'<mxPoint x="{x2}" y="{y2}" as="targetPoint"/></mxGeometry></mxCell>')

def title(cid, text, x=40, y=8, w=760):
    return node(cid, text, x, y, w, 30,
                "text;html=1;strokeColor=none;fillColor=none;align=left;"
                "verticalAlign=middle;fontStyle=1;fontSize=17;")

def subtitle(cid, text, x=40, y=36, w=900):
    return node(cid, text, x, y, w, 22,
                "text;html=1;strokeColor=none;fillColor=none;align=left;"
                "verticalAlign=middle;fontSize=11;fontColor=#666666;")

def legend(prefix, x, y, items, w=250, ttl="圖例 Legend"):
    """items: list of (kind, val, text).
    kind='fill' → val=色票 key,畫色塊;
    kind='line' → val=色票 key,畫實心細線(向後相容);
    kind='edge' → val=完整 edge style 字串,畫真實線型 swatch(粗實/實/虛/點)。
    """
    cells = []
    row_h = 22
    h = 30 + row_h * len(items) + 6
    gid = f"{prefix}_lg"
    cells.append(node(gid, ttl, x, y, w, h,
                      "rounded=1;whiteSpace=wrap;html=1;fillColor=#FFFFFF;strokeColor=#666666;"
                      "verticalAlign=top;fontStyle=1;fontSize=11;container=1;collapsible=0;"))
    yy = 28
    for i, (kind, val, text) in enumerate(items):
        if kind == "edge":
            # 用絕對座標畫真實線型 swatch(避免容器內 edge 座標歧義)
            sw = val.replace("edgeStyle=orthogonalEdgeStyle;", "")  # swatch 走直線
            cells.append(
                f'<mxCell id="{gid}_s{i}" value="" style="{sw}" edge="1" parent="1">'
                f'<mxGeometry relative="1" as="geometry">'
                f'<mxPoint x="{x + 8}" y="{y + yy + 11}" as="sourcePoint"/>'
                f'<mxPoint x="{x + 38}" y="{y + yy + 11}" as="targetPoint"/></mxGeometry></mxCell>')
        else:
            f, s = FILL[val]
            if kind == "fill":
                cells.append(node(f"{gid}_s{i}", "", 10, yy + 3, 26, 14,
                                  f"rounded=1;html=1;fillColor={f};strokeColor={s};", parent=gid))
            else:  # 'line'
                cells.append(node(f"{gid}_s{i}", "", 10, yy + 8, 26, 4,
                                  f"html=1;fillColor={s};strokeColor={s};", parent=gid))
        cells.append(node(f"{gid}_t{i}", text, 42, yy, w - 50, row_h,
                          "text;html=1;align=left;verticalAlign=middle;fontSize=10;", parent=gid))
        yy += row_h
    return cells


def d_00_1():
    P = "m1"
    LW = 1060          # layer 寬
    LX = 40
    c = [title(f"{P}_ttl", "00-1 商業模式與營運鏈心智模型  ·  enterprise 00 / 02", w=1000),
         subtitle(f"{P}_sub", "License 開通商業模式 × 單品牌營運全鏈 × 產業無關平台核心 —— 三層一脊")]

    def layer(cid, ttl, color, y, h):
        return node(cid, ttl, LX, y, LW, h, container(color))

    # 上層 — 商業模式(yellow)
    c.append(layer(f"{P}_biz", "商業模式 —— License 開通", "yellow", 70, 145))
    biz = [
        "per-brand bundle\n每品牌一套物理隔離單體 + 綁定品牌 LINE 官方帳號",
        "附加模組 License 加購\nknowledge-refinery、Agent Configuration Studio",
        "集中共用平台\n（我方集中營運，跨品牌）",
    ]
    for i, t in enumerate(biz):
        c.append(node(f"{P}_biz{i}", t, 20 + i * 348, 50, 330, 78, rrect("yellow"), parent=f"{P}_biz"))

    # 中層 — 營運全鏈路(red)
    c.append(layer(f"{P}_run", "營運全鏈路（單品牌）", "red", 230, 190))
    run = [
        "客服\n（AI 對話 → 問題卡）",
        "報價\n（客戶 LIFF 確認）",
        "派工\n（1-click 開工單）",
        "維修\n（現場複核 / 存證）",
        "結算\n（計費 / 對帳 / 佣金）",
    ]
    for i, t in enumerate(run):
        c.append(node(f"{P}_run{i}", t, 20 + i * 205, 48, 190, 72, rrect("red"), parent=f"{P}_run"))
    for i in range(len(run) - 1):
        c.append(edge(f"{P}_re{i}", f"{P}_run{i}", f"{P}_run{i+1}", "", E_MAIN, parent=f"{P}_run"))
    c.append(node(f"{P}_note", "報價先行：客人確認後才派工；急件 4 類可事後補審（retrospective）",
                  20, 132, 1010, 44, note("red"), parent=f"{P}_run"))

    # 下層 — 平台核心(green)
    c.append(layer(f"{P}_plat", "平台核心 —— 產業無關", "green", 440, 140))
    plat = [
        "工單狀態機引擎\n（flow DSL 解釋執行）",
        "金流軌\n（append-only 帳本）",
        "四方 RBAC\n（deny-by-default）",
        "事件骨幹 🔜\n（Kafka，階段二）",
    ]
    for i, t in enumerate(plat):
        c.append(node(f"{P}_plat{i}", t, 20 + i * 258, 48, 245, 72, rrect("green"), parent=f"{P}_plat"))

    # 右側縱向脊椎(orange)
    c.append(node(f"{P}_spine", "知識精煉閉環 + 積木飛輪\n（階段二 🔜）",
                  1120, 70, 110, 510, arrow_down("orange")))

    # 底部標語(gray)
    c.append(node(f"{P}_banner",
                  "通用工單維運核心 + 產業配置層（Vertical Pack）—— 藍領營運的商業邏輯編譯器",
                  40, 595, 1190, 44, band("gray")))

    c += legend(P, 40, 655, [
        ("fill", "yellow", "商業模式 · License 開通"),
        ("fill", "red", "營運全鏈路（單品牌）"),
        ("fill", "green", "平台核心（產業無關）"),
        ("fill", "orange", "脊椎 · 知識精煉閉環 + 積木飛輪"),
        ("fill", "gray", "平台定位標語"),
        ("edge", E_MAIN, "粗實線 = 營運主鏈 客服→報價→派工→維修→結算"),
    ], w=360)
    return ("d00_1", "00-1 商業模式與營運鏈心智模型", c)


def d_00_2():
    P = "m2"
    c = [title(f"{P}_ttl", "00-2 System Context (C4 Level 1)  ·  enterprise 12_SAD", w=1000)]

    center = f"{P}_sys"
    c.append(node(center, "Smart Lock AI 客服與派工 SaaS 平台\n（6 子系統 + 集中共用平台）",
                  520, 350, 340, 120, rrect("blue") + "fontStyle=1;fontSize=14;"))

    # 外部角色(actor · gray)
    actors = {
        "cust": ("終端客戶\n（LINE 用戶）",           150, 110),
        "oper": ("品牌營運人員\n（租戶 Admin / 小編）", 150, 360),
        "tech": ("簽約技師\n（跨品牌共享）",           150, 600),
        "padm": ("平台管理員\n（Super Admin）",        660, 120),
        "pros": ("潛在加盟品牌",                      1230, 120),
    }
    for k, (v, x, y) in actors.items():
        c.append(node(f"{P}_{k}", v, x, y, 60, 90, actor("gray")))

    # 外部系統(rect · gray)
    exts = {
        "line": ("LINE Platform\n（webhook / LIFF / Flex）",                       1110, 340, 220, 70),
        "llm":  ("LLM 供應商\n（Gemini / Vertex / Claude / GPT，經 LiteLLM 字串路由）", 1060, 470, 275, 100),
        "mat":  ("產品素材源\n（YouTube / 官網 / 手冊）",                            1110, 210, 220, 70),
        "gcp":  ("GCP\n（Cloud Run / Secret Manager / Cloud SQL）",                 540, 610, 300, 70),
    }
    for k, (v, x, y, w, h) in exts.items():
        c.append(node(f"{P}_{k}", v, x, y, w, h, rect("gray")))

    E = E_SOLID
    c.append(edge(f"{P}_e1", f"{P}_cust", center, "LINE 報修 / LIFF 確認報價 / 評分", E))
    c.append(edge(f"{P}_e2", f"{P}_oper", center, "監看對話 / 派工 / 對帳（OIDC 登入）", E))
    c.append(edge(f"{P}_e3", f"{P}_tech", center, "接單 / 到府存證 / 發起現場報價修正", E))
    c.append(edge(f"{P}_e4", f"{P}_padm", center, "跨租戶治理 / License 開通", E))
    c.append(edge(f"{P}_e5", f"{P}_pros", center, "品牌申請 → License 開通", E + "dashed=1;"))
    c.append(edge(f"{P}_e6", center, f"{P}_line", "webhook 入站 / Reply·Push / Flex",
                  E + "startArrow=classic;startFill=1;"))
    c.append(edge(f"{P}_e7", center, f"{P}_llm", "模型呼叫（供應商無關，LiteLLM 路由）", E))
    c.append(edge(f"{P}_e8", f"{P}_mat", center, "知識素材汲取（bronze）", E))
    c.append(edge(f"{P}_e9", center, f"{P}_gcp", "部署 / 密鑰 / 資料庫", E))

    c += legend(P, 150, 730, [
        ("fill", "blue", "本平台（Smart Lock AI SaaS）"),
        ("fill", "gray", "外部角色 / 外部系統"),
        ("edge", E_SOLID, "實線箭頭 = 互動 / 資料流（示方向）"),
    ], w=300)
    return ("d00_2", "00-2 System Context (C4 L1)", c)


def d_01_1():
    P = "p1"
    c = [title(f"{P}_ttl",
               "01-1 部署三分層（per-brand bundle / 集中共用 / License 附加）  ·  enterprise 12_SAD §2", w=1100),
         subtitle(f"{P}_sub",
                  "部署形態：大單體 + 內部容器；per-brand bundle 物理隔離、可完整獨立部署（不含師傅端）", w=1100)]

    CY, CH = 80, 450

    # ① per-brand bundle (blue)
    b1 = f"{P}_bundle"
    c.append(node(b1, "① per-brand bundle（每品牌一套 · 物理隔離 · 可獨立部署）", 40, CY, 440, CH, container("blue")))
    c.append(node(f"{P}_web",   "web 品牌營運後台  :3000\nAPP_MODE=dispatch",                     20, 45,  400, 52, rrect("blue"), parent=b1))
    c.append(node(f"{P}_api",   "api 派工控制平面  :8001\n（API_SURFACE 塑形）",                    20, 112, 400, 55, rrect("blue"), parent=b1))
    c.append(node(f"{P}_agent", "agent（LockCore LINE Bot）\nSkill 行為驅動 + RAG-via-MCP client", 20, 182, 400, 55, rrect("blue"), parent=b1))
    c.append(node(f"{P}_mcp",   "MCP-RAG server\n（search_product_manual / similar_cases）",       20, 252, 400, 50, rrect("blue"), parent=b1))
    c.append(node(f"{P}_dbb",   "品牌庫\nPostgreSQL + pgvector\n（業務 + 唯一事實語料）",           20, 320, 200, 105, cyl("purple"), parent=b1))
    c.append(node(f"{P}_redis", "Redis\n（WS pub/sub + cache）",                                  235, 320, 185, 105, cyl("purple"), parent=b1))

    # ② 集中共用平台 (green)
    b2 = f"{P}_shared"
    c.append(node(b2, "② 集中共用平台（跨品牌 · 我方集中營運）", 500, CY, 560, CH, container("green")))
    c.append(node(f"{P}_cas", "Casdoor\n（IdP / 租戶 / License）",  20, 45, 255, 55, rrect("green"), parent=b2))
    c.append(node(f"{P}_sig", "SigNoz + OPIK\n（可觀測 / LLM Ops）", 290, 45, 250, 55, rrect("green"), parent=b2))

    tp = f"{P}_techp"
    c.append(node(tp, "technician-platform（技師共享池）", 20, 118, 520, 145, container("teal")))
    c.append(node(f"{P}_tapi", "tech-api  :8002\n（OHS API）",     15, 42, 165, 58, rrect("teal"), parent=tp))
    c.append(node(f"{P}_tweb", "師傅 web  :3001\nAPP_MODE=tech",   190, 42, 155, 58, rrect("teal"), parent=tp))
    c.append(node(f"{P}_tdb",  "技師庫\nlock_tech",                360, 35, 145, 95, cyl("purple"), parent=tp))

    c.append(node(f"{P}_kafka", "Kafka 事件骨幹  🔜（階段二）", 20, 280, 520, 42, rrect("green"), parent=b2))
    c.append(node(f"{P}_pcon",  "平台 console  :3003",         20, 338, 165, 55, rrect("green"), parent=b2))
    c.append(node(f"{P}_papi",  "platform-api  :8003",         195, 338, 165, 55, rrect("green"), parent=b2))
    c.append(node(f"{P}_pdb",   "平台庫",                       375, 330, 145, 95, cyl("purple"), parent=b2))

    # ③ License 附加模組 (teal)
    b3 = f"{P}_addon"
    c.append(node(b3, "③ License 附加模組", 1080, CY, 280, CH, container("teal")))
    c.append(node(f"{P}_ref",  "knowledge-refinery\n（知識精煉 · License 附加）",     20, 45,  240, 55, rrect("teal"), parent=b3))
    c.append(node(f"{P}_refp", "精煉管線\n（raw → bronze → silver → 事實 / 行為）",    20, 115, 240, 70, rrect("teal"), parent=b3))
    c.append(node(f"{P}_refh", "HITL 審核 UI\n（draft → 人審 → commit）",            20, 200, 240, 60, rrect("teal"), parent=b3))
    c.append(node(f"{P}_refw", "refinery web\n（Next.js · Casdoor OIDC）",           20, 275, 240, 55, rrect("teal"), parent=b3))

    # 跨層連線(4 條)
    c.append(edge(f"{P}_x1", f"{P}_api", f"{P}_cas",  "OIDC claim 🔜", E_DOT))
    c.append(edge(f"{P}_x2", f"{P}_api", f"{P}_sig",  "遙測 OTel", E_DOT))
    c.append(edge(f"{P}_x3", f"{P}_api", f"{P}_tapi", "OHS API：派工 / requote command", E_SOLID))
    c.append(edge(f"{P}_x4", f"{P}_ref", f"{P}_dbb",  "核可後灌語料（學習態回流）", E_DASH))

    # ADR 依據：per-brand 獨立部署 = ADR-P005（SAD §2.1 / BRD §2.2 / Product Strategy §2.3）
    c.append(node(f"{P}_note", "品牌不依賴任何共享元件即可自成一套上線（ADR-P005）",
                  40, CY + CH + 12, 440, 44, note("blue")))

    c += legend(P, 520, CY + CH + 12, [
        ("fill", "blue", "per-brand bundle（單品牌單體）"),
        ("fill", "green", "集中共用平台"),
        ("fill", "teal", "獨立子系統 / License 附加"),
        ("fill", "purple", "資料儲存（DB / Redis）"),
        ("edge", E_SOLID, "實線 = OHS 派工 API（命令）"),
        ("edge", E_DASH, "虛線 = 學習態回流（灌語料）"),
        ("edge", E_DOT, "點線 = 橫切支撐（OIDC / 遙測）"),
    ], w=340)
    return ("d01_1", "01-1 部署三分層", c)


def d_01_2():
    P = "p2"
    c = [title(f"{P}_ttl", "附錄A 01-2 平台核心 vs 領域配置（Vertical Pack）  ·  🔜 階段二", w=1000),
         subtitle(f"{P}_sub", "業主裁決 2026-07-07：本層全數列產品階段二，先深耕鎖匠垂直")]

    # 左 — 平台核心(green)
    core = f"{P}_core"
    c.append(node(core, "平台核心（永不隨產業改）", 60, 90, 540, 390, container("green")))
    core_items = [
        "工單引擎\n（DSL executor + SLA timer）",
        "共用元件庫\n（DynamicForm / DynamicTable / WorkOrderBoard …）",
        "金流軌\n（append-only 帳本）",
        "身分 RBAC\n（Casdoor · deny-by-default）",
        "事件骨幹\n（Kafka / Redis）",
    ]
    for i, t in enumerate(core_items):
        c.append(node(f"{P}_c{i}", t, 20, 45 + i * 68, 500, 56, rrect("green"), parent=core))

    # 右 — Vertical Pack(yellow)
    pack = f"{P}_pack"
    c.append(node(pack, "Vertical Pack（一包 = 一產業）", 800, 90, 540, 390, container("yellow")))
    pack_items = [
        "field_metadata\n（診斷 / 工單欄位定義）",
        "flow DSL\n（工單 / 金流狀態機）",
        "catalog\n（價目 / 料件）",
        "knowledge\n（skills + RAG 語料）",
        "ui_composition\n（後台畫面組裝）",
        "blocks 積木\n（領域積木庫）",
    ]
    for i, t in enumerate(pack_items):
        cx = 20 + (i % 2) * 260
        cy = 45 + (i // 2) * 108
        c.append(node(f"{P}_p{i}", t, cx, cy, 250, 96, rrect("yellow"), parent=pack))

    # 中間裝載箭頭
    c.append(edge(f"{P}_load", core, pack, "pack@version 裝載 + 租戶覆寫",
                  E_SOLID, exit=(1, 0.5), entry=(0, 0.5)))

    # 下方 note(yellow)
    c.append(node(f"{P}_note",
                  "FDE 新產業只做 4 配置面：① 診斷系統　② 知識精煉　③ 工單金流 flow　④ 後台 UI 組裝\n"
                  "三鐵律：DSL-first（先引擎後 UI） / 頭 2-3 產業積木手工建 / 金流·派工·同意書必過人審",
                  60, 510, 1280, 90, note("yellow")))

    c += legend(P, 60, 620, [
        ("fill", "green", "平台核心（產業無關，永不隨產業改）"),
        ("fill", "yellow", "Vertical Pack（領域配置 · 一包一產業）"),
        ("edge", E_SOLID, "實線 = pack 裝載 + 租戶覆寫"),
    ], w=360)
    return ("d01_2", "附錄A · 01-2 平台核心 vs Vertical Pack", c)


# ===========================================================================
# 附錄B 02-1  知識與模型能力分層 (agent ADR-003/004/P008)
# ===========================================================================
def d_02_1():
    P = "k1"
    c = [title(f"{P}_ttl", "附錄B 02-1 知識與模型能力分層  ·  agent ADR-003/004/P008", w=1000),
         node(f"{P}_hint",
              "四層能力資產供 LockCore agent 消費：Skill 行為 · RAG 事實 · per-user 記憶 · Model Orchestration；"
              "知識精煉閉環回流（見 04-4）",
              40, 36, 1180, 20, txt() + "fontSize=11;fontColor=#666666;")]

    # ── 第 1 層:Skill 行為層(orange) ──
    skill = f"{P}_skill"
    c.append(node(skill, "Skill 行為層（git-tracked，可攜 · Agent Skills 標準）", 40, 76, 880, 118,
                  container("orange")))
    c.append(node(f"{P}_sk0", "locksmith-cs-sop\nSOP / 紅線決策樹 / 7 條轉真人硬規則",
                  18, 36, 410, 64, rrect("orange"), parent=skill))
    c.append(node(f"{P}_sk1", "locksmith-product-knowledge\n精選事實 + 檢索程序 + domain-safety",
                  450, 36, 410, 64, rrect("orange"), parent=skill))

    # ── 第 2 層:RAG 事實層(orange) ──
    rag = f"{P}_rag"
    c.append(node(rag, "RAG 事實層（品牌庫 pgvector · 唯一事實語料）", 40, 210, 880, 150,
                  container("orange")))
    c.append(node(f"{P}_rg0", "manual_chunks\n手冊 chunk · VECTOR(768)",
                  18, 36, 250, 56, rrect("orange"), parent=rag))
    c.append(node(f"{P}_rg1", "case_entries\n案例庫", 285, 36, 250, 56, rrect("orange"), parent=rag))
    c.append(node(f"{P}_rg2", "逐型號事實 chunk\n長尾檢索", 552, 36, 308, 56, rrect("orange"), parent=rag))
    c.append(node(f"{P}_rgn",
                  "🔜 語義層 Phase（RAG-via-MCP）：agent 經 MCP server 查，"
                  "DB 耦合封在 server 內；查詢強制 WHERE tenant_id",
                  18, 100, 842, 38, note("yellow"), parent=rag))

    # ── 第 3 層:per-user 記憶(purple 容器) ──
    mem = f"{P}_mem"
    c.append(node(mem, "per-user 記憶（agent.* schema · pg_trgm/GIN）", 40, 372, 880, 118,
                  container("purple")))
    c.append(node(f"{P}_mm0", "BUILD：注入 &lt;memory&gt; 客戶事實",
                  18, 34, 410, 48, rrect("purple"), parent=mem))
    c.append(node(f"{P}_mm1", "SAVE：抽第三人稱事實寫回（try/except 不敗 turn）",
                  450, 34, 410, 48, rrect("purple"), parent=mem))
    c.append(node(f"{P}_mmn", "讀寫必帶 tenant + user_id，缺則 raise（default deny）",
                  18, 86, 842, 26, note("purple"), parent=mem))

    # ── 第 4 層:Model Orchestration Layer(green) ──
    mdl = f"{P}_model"
    c.append(node(mdl, "Model Orchestration Layer（供應商無關）", 40, 502, 880, 110,
                  container("green")))
    c.append(node(f"{P}_md0", "LiteLLM 單一 Provider\nmodel 字串路由",
                  18, 34, 410, 52, rrect("green"), parent=mdl))
    c.append(node(f"{P}_md1", "gemini/ · vertex_ai/ · claude-* · gpt-4o\n失敗回哨兵值 → 友善話術",
                  450, 34, 410, 52, rrect("green"), parent=mdl))

    # ── agent 核心(red 熱路徑) ──
    ag = f"{P}_agent"
    c.append(node(ag, "AI 客服 agent（LockCore）\n\nContextBuilder → AgentRunner\n漸進式揭露組 system prompt",
                  960, 250, 300, 190, rrect("red") + "fontStyle=1;fontSize=13;"))

    # ── knowledge-refinery(teal 獨立子系統) ──
    kr = f"{P}_kr"
    c.append(node(kr, "knowledge-refinery 知識精煉\nbronze-only 治理 · HITL gate",
                  960, 476, 300, 90, rrect("teal")))
    c.append(node(f"{P}_krtxt", "→ 見 04-4 精煉閉環（bronze→silver→事實 / 行為）",
                  960, 570, 300, 22, txt() + "fontSize=10;fontColor=#0E8088;"))

    # ── 連線 ──
    c.append(edge(f"{P}_e1", skill, ag, "行為驅動", E_SOLID))
    c.append(edge(f"{P}_e2", rag, ag, "檢索能力（MCP）", E_SOLID))
    c.append(edge(f"{P}_e3", mem, ag, "BUILD 注入 / SAVE 回寫", E_DOT + "startArrow=open;"))
    c.append(edge(f"{P}_e4", mdl, ag, "模型調用 · 哨兵 fallback", E_DOT))
    c.append(edge(f"{P}_e5", kr, rag, "事實精煉回流", E_DASH))
    c.append(edge(f"{P}_e6", kr, skill, "行為精煉回流", E_DASH))

    c += legend(P, 40, 636, [
        ("fill", "orange", "Skill 行為層 / RAG 事實層（能力資產）"),
        ("fill", "purple", "per-user 記憶（agent.* data store）"),
        ("fill", "green", "Model Orchestration（平台共用服務）"),
        ("fill", "red", "AI 客服 agent（即時客服熱路徑）"),
        ("fill", "teal", "knowledge-refinery（獨立子系統）"),
        ("edge", E_SOLID, "實線 = 行為驅動 / 檢索能力（agent 消費）"),
        ("edge", E_DOT, "點線 = 記憶 / 模型 橫切支撐"),
        ("edge", E_DASH, "虛線 = 知識精煉回流（→ 04-4）"),
    ], w=360)
    return ("d02_1", "附錄B 02-1 知識與模型能力分層 · agent ADR-003/004/P008", c)


# ===========================================================================
# 附錄C 02-2  AI 邊界紅線治理 (BRD §6.1 / ADR-025)
# ===========================================================================
def d_02_2():
    P = "k2"
    c = [title(f"{P}_ttl", "附錄C 02-2 AI 邊界紅線治理  ·  BRD §6.1 / ADR-025", w=1000),
         node(f"{P}_hint",
              "AI 職責 = 對話判斷 + 知識回覆；判定與交易永遠在人與確定性系統（BR-AI / BR-QUOTE / BR-WO）",
              40, 36, 1180, 20, txt() + "fontSize=11;fontColor=#666666;")]

    # ── 中央:AI 客服核心(red) ──
    ai = f"{P}_ai"
    c.append(node(ai, "AI 客服\n（LockCore agent）", 560, 300, 320, 150,
                  rrect("red") + "fontStyle=1;fontSize=15;"))

    # ── 四周紅線規則卡(note red) ──
    c.append(node(f"{P}_c1",
                  "① 工具白名單僅 6 項（單點控管）\n"
                  "read_file / list_dir / find_files /\ngrep / web_search / transfer_to_human\n"
                  "新增工具 = 架構變更（走 CIA）\n〔BR-AI-01 / FR-A06〕",
                  90, 96, 420, 120, note("red")))
    c.append(node(f"{P}_c2",
                  "② transfer_to_human = AI 進後台唯一入口\n"
                  "對客承諾「將為您安排」必實際呼叫工具；\n"
                  "未呼叫 → gateway 偵測承諾話術 → 兜底補建 escalation\n〔BR-AI-02 / FR-A04〕",
                  930, 96, 420, 120, note("red")))
    c.append(node(f"{P}_c4",
                  "④ 200 題禁區 Eval pipeline\n每次 deploy 自動跑\npass &lt; 95% → 阻擋部署\n〔BR-AI-04 / FR-A10〕",
                  90, 290, 380, 140, note("red")))
    c.append(node(f"{P}_c5",
                  "⑤ rule_triggered_by 由確定性規則引擎寫入\n（不得 LLM 自報 → 防 KPI gaming）\n"
                  "Prompt injection 攔截 ≥ 95%\n誤攔 &lt; 1% · 輸出限定智慧鎖話題\n〔BR-AI-03 / BR-AI-06〕",
                  970, 290, 380, 140, note("red")))

    # ── ③ AI 永不(red 容器 + 四子卡) ──
    c3 = f"{P}_c3"
    c.append(node(c3, "③ AI 永不（交易 / 判定紅線）", 350, 490, 740, 180, container("red")))
    c.append(node(f"{P}_c3a", "直接建工單 / 派工 / 碰金流\n（一律 1-click 人工確認）〔BR-WO-01〕",
                  16, 44, 350, 60, rrect("red"), parent=c3))
    c.append(node(f"{P}_c3b", "final quote / 折扣 / 免費保固\n（只給範圍價 range）〔BR-QUOTE-01〕",
                  378, 44, 350, 60, rrect("red"), parent=c3))
    c.append(node(f"{P}_c3c", "複誦個案報價金額\n（server 模板限定，無自由文金額）〔BR-QUOTE-02〕",
                  16, 110, 350, 60, rrect("red"), parent=c3))
    c.append(node(f"{P}_c3d", "影像辨識（合約明文禁止）\n圖片僅附件保存〔BR-AI-05〕",
                  378, 110, 350, 60, rrect("red"), parent=c3))

    # ── 中央 → 各紅線卡(E_SOLID:enforced-by) ──
    c.append(edge(f"{P}_e1", ai, f"{P}_c1", "BR-AI-01/06", E_SOLID))
    c.append(edge(f"{P}_e2", ai, f"{P}_c2", "BR-AI-02", E_SOLID))
    c.append(edge(f"{P}_e4", ai, f"{P}_c4", "BR-AI-04", E_SOLID))
    c.append(edge(f"{P}_e5", ai, f"{P}_c5", "BR-AI-03/06", E_SOLID))
    c.append(edge(f"{P}_e3", ai, c3, "BR-WO-01 / BR-QUOTE / BR-AI-05", E_SOLID))

    # ── 底部標語 band(gray) ──
    c.append(node(f"{P}_band",
                  "AI 職責僅限對話判斷與知識回覆——判定與交易永遠在人與確定性系統（BR-AI-01）",
                  90, 690, 1260, 44, band("gray")))

    c += legend(P, 90, 750, [
        ("fill", "red", "AI 核心 + 紅線規則卡（禁區）"),
        ("fill", "gray", "職責邊界標語"),
        ("edge", E_SOLID, "實線 = 紅線規則約束（enforced-by · deterministic）"),
    ], w=440)
    return ("d02_2", "附錄C 02-2 AI 邊界紅線治理 · BRD §6.1/ADR-025", c)


# ===========================================================================
# 03-2  agent (LockCore) 元件 (15_SDS §5)
# ===========================================================================
def d_03_2():
    P = "x2"
    c = [title(f"{P}_ttl", "03-2 agent（LockCore）元件  ·  15_SDS §5", w=1000),
         node(f"{P}_hint",
              "一 webhook = 一 turn；LINE 入站唯一路徑 /callback；旁路持久化 fail-soft，絕不阻斷客人回覆",
              40, 36, 1250, 20, txt() + "fontSize=11;fontColor=#666666;")]

    # ── 入站前置鏈(E_MAIN 直線主鏈) ──
    c.append(node(f"{P}_line", "LINE Platform\n（訊息來源）", 40, 90, 150, 64, rect("gray")))
    c.append(node(f"{P}_verify", "webhook 驗簽\nX-Line-Signature\n失敗 400", 210, 90, 150, 64, rrect("green")))
    c.append(node(f"{P}_dedup", "EventDeduplicator(24h)\n+ InboundDebouncer(1.5s)", 380, 90, 200, 64, rrect("red")))
    c.append(node(f"{P}_handover",
                  "handover-state 檢查（查 api）\n接管中 AI 暫停 · 訊息仍全量入庫\nBR-CONV-03 · fail-soft 5s",
                  610, 86, 240, 72, rrect("red")))

    # ── Turn 狀態機(red 容器) ──
    turn = f"{P}_turn"
    c.append(node(turn, "Turn 狀態機（loop.py · 8 態 · 記憶寫回 try/except 不敗 turn）",
                  200, 250, 900, 140, container("red")))
    steps = ["RESTORE", "COMPACT", "COMMAND", "BUILD", "RUN", "SAVE", "RESPOND"]
    for i, s in enumerate(steps):
        c.append(node(f"{P}_t{i}", s, 30 + i * 124, 48, 112, 56, rrect("red"), parent=turn))
    for i in range(len(steps) - 1):
        c.append(edge(f"{P}_te{i}", f"{P}_t{i}", f"{P}_t{i+1}", "", E_STATE, parent=turn))

    # ── 回覆 LINE ──
    c.append(node(f"{P}_reply",
                  "回覆 LINE（reply_message）\nsentinel / 空回覆 → 友善話術\n單則 &gt; 4900 字截斷",
                  1130, 270, 200, 90, rrect("red")))

    # ── 主鏈 E_MAIN ──
    c.append(edge(f"{P}_m1", f"{P}_line", f"{P}_verify", "", E_MAIN))
    c.append(edge(f"{P}_m2", f"{P}_verify", f"{P}_dedup", "", E_MAIN))
    c.append(edge(f"{P}_m3", f"{P}_dedup", f"{P}_handover", "", E_MAIN))
    c.append(edge(f"{P}_m4", f"{P}_handover", turn, "跑 Turn", E_MAIN))
    c.append(edge(f"{P}_m5", f"{P}_t6", f"{P}_reply", "", E_MAIN))

    # ── 支撐元件(E_DOT 接入 Turn) ──
    c.append(node(f"{P}_skills", "SkillsLoader\n2 builtin skills", 200, 430, 155, 58, rrect("orange")))
    c.append(node(f"{P}_rag", "RAG-via-MCP\n🔜 pgvector 事實層", 375, 430, 165, 58, rrect("orange")))
    c.append(node(f"{P}_mem", "per-user 記憶\nBUILD / SAVE", 560, 430, 155, 58, rrect("purple")))
    c.append(node(f"{P}_llm", "LiteLLM Provider\n多供應商 failover", 735, 430, 165, 58, rrect("green")))
    c.append(node(f"{P}_tools",
                  "工具白名單 6 項\nread_file / list_dir / find_files /\ngrep / web_search / transfer_to_human",
                  920, 430, 210, 80, note("yellow")))
    c.append(edge(f"{P}_s1", f"{P}_skills", f"{P}_t3", "", E_DOT))
    c.append(edge(f"{P}_s2", f"{P}_rag", f"{P}_t4", "", E_DOT))
    c.append(edge(f"{P}_s3", f"{P}_mem", f"{P}_t3", "", E_DOT))
    c.append(edge(f"{P}_s4", f"{P}_llm", f"{P}_t4", "", E_DOT))
    c.append(edge(f"{P}_s5", f"{P}_tools", f"{P}_t4", "", E_DOT))

    # ── escalation 路徑(E_SOLID) ──
    c.append(node(f"{P}_tth", "transfer_to_human\n（進後台唯一入口 + 兜底補建）", 1130, 430, 200, 58, rrect("red")))
    c.append(node(f"{P}_esc", "EscalationStore\nfacts_snapshot JSON", 1150, 520, 160, 76, cyl("purple")))
    c.append(node(f"{P}_ingest",
                  "api /internal/escalations/ingest\n→ 建 AI 草擬問題卡（source=ai_line）",
                  1090, 630, 250, 66, rrect("blue")))
    c.append(edge(f"{P}_x1", f"{P}_t4", f"{P}_tth", "紅線觸發", E_SOLID))
    c.append(edge(f"{P}_x2", f"{P}_tth", f"{P}_esc", "", E_SOLID))
    c.append(edge(f"{P}_x3", f"{P}_esc", f"{P}_ingest", "", E_SOLID))

    # ── 外送佇列 ──
    c.append(node(f"{P}_outbox",
                  "LINE outbox worker\nquote_proposal 輪詢推 Flex\n（fire-and-forget 20s）",
                  830, 630, 230, 66, rrect("green")))
    c.append(edge(f"{P}_o1", turn, f"{P}_outbox", "postback fan-out / 外送", E_DOT))

    c += legend(P, 40, 540, [
        ("fill", "gray", "LINE / 外部"),
        ("fill", "red", "Turn 熱路徑 / 前置 / 工具"),
        ("fill", "orange", "skills / RAG 能力資產"),
        ("fill", "purple", "per-user 記憶 / EscalationStore（data store）"),
        ("fill", "green", "LiteLLM / 驗簽 / outbox（平台共用）"),
        ("fill", "blue", "api /internal ingest（後台營運）"),
        ("fill", "yellow", "工具白名單（設計態 note）"),
        ("edge", E_MAIN, "粗實線 = 入站主鏈"),
        ("edge", E_STATE, "折線 = Turn 狀態轉移"),
        ("edge", E_DOT, "點線 = 橫切支撐元件"),
        ("edge", E_SOLID, "實線 = escalation 轉真人路徑"),
    ], w=360)
    return ("d03_2", "03-2 agent（LockCore）元件 · 15_SDS §5", c)


# ===========================================================================
# 03-3  api (派工控制平面) 元件 (15_SDS §6)
# ===========================================================================
def d_03_3():
    P = "x3"
    c = [title(f"{P}_ttl", "03-3 api（派工控制平面）元件  ·  15_SDS §6", w=1000),
         node(f"{P}_hint",
              "同一 codebase 靠 API_SURFACE 塑形部署面（路由過濾非安全邊界）；隔離押在每端點 RBAC · deny-by-default",
              40, 36, 1250, 20, txt() + "fontSize=11;fontColor=#666666;")]

    # ── 頂部守衛鏈(E_MAIN 串 3 rrect green) ──
    c.append(node(f"{P}_g1", "get_current_user\n驗 Bearer + jti 撤銷 + 每請求安全狀態重查",
                  60, 84, 290, 68, rrect("green")))
    c.append(node(f"{P}_g2", "require_tenant\nX-Tenant-ID 比對 claim", 390, 84, 250, 68, rrect("green")))
    c.append(node(f"{P}_g3",
                  "role_required(*roles)\ndeny-by-default enforce · SoD 三方標頭\n"
                  "X-Initiator / Approver / Executor 任二相同 403",
                  680, 84, 360, 68, rrect("green")))
    c.append(edge(f"{P}_ge1", f"{P}_g1", f"{P}_g2", "", E_MAIN))
    c.append(edge(f"{P}_ge2", f"{P}_g2", f"{P}_g3", "", E_MAIN))
    c.append(node(f"{P}_gn",
                  "服務間：require_internal_token（fail-closed 503/401）\n"
                  "平台面：require_platform_admin（不收 X-Tenant-ID）",
                  1080, 84, 270, 68, note("yellow")))

    # ── 中部:域 router 群(container blue) ──
    dom = f"{P}_dom"
    c.append(node(dom, "域 Router 群（routers/ · tenant-scoped /tenants/{tid}/…）", 60, 210, 690, 272,
                  container("blue")))
    doms = [
        ("d0", "問題卡 problem_card\nAI 草擬 → 小編補齊 → confirm", 18, 44),
        ("d1", "工單 work_order\n狀態機 + 事件溯源 work_order_events", 353, 44),
        ("d2", "派工 dispatch\nOHS 呼叫 technician-platform", 18, 118),
        ("d3", "對話接管 conversation\nhandover · 全量存檔", 353, 118),
        ("d4", "結算計費 settlement\ncommission.accrued outbox", 18, 192),
        ("d5", "平台面 platform（:8003）\nrequire_platform_admin", 353, 192),
    ]
    for sid, val, dx, dy in doms:
        c.append(node(f"{P}_{sid}", val, dx, dy, 315, 62, rrect("blue"), parent=dom))

    # ── 獨立 bounded context:報價引擎 Quote BC(container yellow) ──
    q = f"{P}_q"
    c.append(node(q, "報價引擎 Quote BC（獨立 bounded context · api/pricing/）", 770, 210, 560, 272,
                  container("yellow")))
    c.append(node(f"{P}_q0", "quote 主狀態機\ndraft→internal_approved→customer_sent→confirmed",
                  18, 44, 250, 64, rrect("blue"), parent=q))
    c.append(node(f"{P}_q1", "分層核可\n減價/同額直送 · 加價 501-2000 小編 · &gt;2000 主管",
                  288, 44, 254, 64, rrect("blue"), parent=q))
    c.append(node(f"{P}_q2", "pricing_rule_snapshot\nsha256 · append-only\n已送出報價不重算",
                  18, 120, 250, 82, cyl("purple"), parent=q))
    c.append(node(f"{P}_q3", "LIFF customer-confirm\nIdempotency-Key · confirm token TTL 48h",
                  288, 120, 254, 72, rrect("blue"), parent=q))
    c.append(node(f"{P}_qn", "AI 禁直呼定價引擎——經報價聚合 in-process 取價（BR-QUOTE / FR-C02）",
                  18, 208, 524, 48, note("red"), parent=q))

    # ── 守衛鏈 → 域 router(E_MAIN) ──
    c.append(edge(f"{P}_gd", f"{P}_g3", dom, "逐端點掛 role_required", E_MAIN))

    # ── 底部基礎設施(E_DOT) ──
    c.append(node(f"{P}_ob", "outbox\nDB 寫入 ⟂ side-effect 分離 · 重試至成功", 60, 512, 210, 64, rrect("green")))
    c.append(node(f"{P}_ws", "WS hub（10 頻道）\n🔜 遷 Redis pub/sub（ADR-P007）", 290, 512, 230, 64, rrect("green")))
    c.append(node(f"{P}_cr", "11 cron workers\nSLA / GDPR 硬刪 / 自動結案 / outbox\n🔜 分散式鎖",
                  540, 512, 230, 64, rrect("green")))
    c.append(node(f"{P}_db", "品牌庫 lock_AI_data\n一品牌一庫（物理隔離）", 790, 512, 200, 80, cyl("purple")))
    c.append(edge(f"{P}_i1", dom, f"{P}_ob", "outbox 保證", E_DOT))
    c.append(edge(f"{P}_i2", dom, f"{P}_ws", "WS 推播", E_DOT))
    c.append(edge(f"{P}_i3", f"{P}_cr", dom, "SCHED → SVC", E_DOT))
    c.append(edge(f"{P}_i4", dom, f"{P}_db", "", E_DOT))
    c.append(edge(f"{P}_i5", q, f"{P}_db", "", E_DOT))

    # ── 右側 note:requote command 入口 ──
    c.append(node(f"{P}_rq",
                  "/internal/requote-requests\n技師平台 requote command 入口\n"
                  "（ADR-027 · 零定價權 · 只收 diff）\nS2S 認證 + request_id 冪等",
                  1030, 600, 300, 100, note("red")))
    c.append(edge(f"{P}_rqe", f"{P}_rq", q, "requote command", E_SOLID))

    c += legend(P, 60, 600, [
        ("fill", "green", "守衛鏈 + 平台共用基礎設施（outbox/WS/cron）"),
        ("fill", "blue", "域 router（品牌後台營運）"),
        ("fill", "yellow", "獨立 bounded context（Quote BC）/ 註記"),
        ("fill", "purple", "data store（snapshot / 品牌庫）"),
        ("fill", "red", "紅線註記（AI 禁直呼定價）"),
        ("edge", E_MAIN, "粗實線 = 守衛鏈 / 請求主鏈"),
        ("edge", E_DOT, "點線 = 背景 / 基礎設施橫切"),
        ("edge", E_SOLID, "實線 = requote command 入口（ADR-027）"),
    ], w=400)
    return ("d03_3", "03-3 api（派工控制平面）元件 · 15_SDS §6", c)


def d_03_1():
    P = "x1"
    c = [title(f"{P}_ttl", "03-1 Container（C4 L2）主錨 · 12_SAD", w=1100),
         subtitle(f"{P}_sub",
                  "per-brand bundle 可獨立部署（不含師傅端）｜集中共用平台（跨品牌）｜knowledge-refinery 為 License 附加模組",
                  w=1200)]

    # ── 外部 actor（gray）+ LINE 外部系統 ──
    c.append(node(f"{P}_cust", "終端客戶\n（LINE 用戶）", 40, 150, 64, 76, actor()))
    c.append(node(f"{P}_oper", "品牌營運\n人員", 40, 380, 64, 76, actor()))
    c.append(node(f"{P}_padmin", "平台\n管理員", 1545, 180, 64, 76, actor()))
    c.append(node(f"{P}_tech", "簽約師傅\n／鎖匠", 1545, 520, 64, 76, actor()))
    c.append(node(f"{P}_line", "LINE\nMessaging API", 168, 156, 124, 62, rect("gray")))

    # ── per-brand bundle（blue container）──
    bd = f"{P}_bundle"
    c.append(node(bd, "per-brand bundle（物理隔離 · 可完整獨立部署 · 不含師傅端）",
                  340, 95, 640, 580, container("blue")))
    c.append(node(f"{P}_agent", "agent（LockCore）\nLINE Bot · /callback webhook",
                  25, 44, 275, 76, rrect("blue"), parent=bd))
    c.append(node(f"{P}_web", "web（Next.js 多站）\nAPP_MODE=dispatch · :3000",
                  340, 44, 275, 76, rrect("blue"), parent=bd))
    c.append(node(f"{P}_ui", "Web UI", 561, 40, 54, 16,
                  "rounded=1;html=1;fillColor=#DAE8FC;strokeColor=#6C8EBF;fontSize=9;fontStyle=1;", parent=bd))
    c.append(node(f"{P}_api", "api（FastAPI 控制平面）\nAPI_SURFACE 塑形 · :8001",
                  340, 155, 275, 76, rrect("blue"), parent=bd))
    c.append(node(f"{P}_mcprag", "MCP-RAG server\nsearch_product_manual / similar_cases",
                  25, 160, 275, 64, rrect("orange"), parent=bd))
    c.append(node(f"{P}_brandDB", "品牌庫 pgvector\n~100 表 · 業務 ＋ 唯一事實語料",
                  40, 372, 250, 155, cyl("purple"), parent=bd))
    c.append(node(f"{P}_redis", "Redis\nWS pub/sub fanout ＋ cache",
                  360, 388, 200, 130, cyl("purple"), parent=bd))

    # ── 集中共用平台（green container）──
    gs = f"{P}_shared"
    c.append(node(gs, "集中共用平台（跨品牌）", 1030, 95, 440, 340, container("green")))
    c.append(node(f"{P}_casdoor", "Casdoor\nIdP（OIDC）＋租戶 org＋License",
                  25, 40, 185, 66, rrect("green"), parent=gs))
    c.append(node(f"{P}_signoz", "SigNoz ＋ OPIK\n系統可觀測性 / LLM Ops",
                  230, 40, 185, 66, rrect("green"), parent=gs))
    c.append(node(f"{P}_pconsole", "平台 console web\n:3003（Super Admin）",
                  25, 122, 185, 62, rrect("green"), parent=gs))
    c.append(node(f"{P}_papi", "platform-api\n:8003 跨租戶治理",
                  230, 122, 185, 62, rrect("green"), parent=gs))
    c.append(node(f"{P}_platDB", "平台庫 platform-db\n管理員 / 品牌申請",
                  110, 200, 220, 118, cyl("purple"), parent=gs))

    # ── technician-platform（teal container）──
    tp = f"{P}_techp"
    c.append(node(tp, "technician-platform 技師共享池（跨租戶）", 1030, 455, 440, 250, container("teal")))
    c.append(node(f"{P}_techapi", "tech-api\n:8002 · OHS ＋ Kafka client",
                  25, 40, 185, 66, rrect("teal"), parent=tp))
    c.append(node(f"{P}_techweb", "師傅 web（technician-web）\n:3001",
                  230, 40, 185, 66, rrect("teal"), parent=tp))
    c.append(node(f"{P}_techDB", "技師庫 lock_tech\n技師身分域 · 單一真相",
                  110, 125, 220, 100, cyl("purple"), parent=tp))

    # ── knowledge-refinery（teal container · License 附加）──
    kr = f"{P}_refinery"
    c.append(node(kr, "knowledge-refinery【License 附加】", 340, 710, 640, 175, container("teal")))
    c.append(node(f"{P}_pipe", "汲取 ＋ Medallion 管線\nraw→bronze→silver → 提煉分流（事實 / 行為）",
                  30, 42, 285, 112, rrect("teal"), parent=kr))
    c.append(node(f"{P}_review", "審核 web UI（HITL）\ndraft → 人審 diff → 核可（Casdoor OIDC）",
                  340, 42, 270, 112, rrect("teal"), parent=kr))

    # ── Kafka 事件骨幹（🔜 階段二）──
    c.append(node(f"{P}_kafka", "Kafka 事件骨幹（commission.accrued / 工單投影）　🔜 階段二",
                  1030, 740, 440, 56, rrect("green")))

    # ── 連線 ──
    def er(i, s, t, v, st):
        c.append(edge(f"{P}_r{i}", f"{P}_{s}", f"{P}_{t}", v, st))
    def eb(i, s, t, v):
        c.append(edge(f"{P}_b{i}", f"{P}_{s}", f"{P}_{t}", v, E_SOLID, parent=bd))

    er(1, "cust", "line", "LINE 訊息", E_MAIN)
    er(2, "line", "agent", "webhook /callback", E_MAIN)
    er(3, "agent", "line", "Reply / Push", E_MAIN)
    er(4, "oper", "web", "OIDC 登入", E_SOLID)
    er(5, "padmin", "pconsole", "OIDC 平台身分", E_SOLID)
    er(6, "tech", "techweb", "OIDC 師傅端", E_SOLID)
    er(7, "api", "techapi", "OHS API（派工 / requote）", E_SOLID + "startArrow=classic;startFill=1;")
    er(8, "api", "casdoor", "OIDC 驗 token", E_SOLID)
    er(9, "review", "brandDB", "核可後灌 pgvector 語料", E_DASH)
    er(10, "api", "signoz", "OTel（全服務示意）", E_DOT)
    er(11, "api", "kafka", "🔜 階段二 事件骨幹", E_DOT)

    eb(1, "agent", "api", "/internal/* 服務憑證")
    eb(2, "agent", "mcprag", "RAG-via-MCP")
    eb(3, "mcprag", "brandDB", "cosine ＋ tenant ACL")
    eb(4, "agent", "brandDB", "記憶 agent.*")
    eb(5, "web", "api", "REST ＋ WS :8001")
    eb(6, "api", "brandDB", "寫 primary / 讀 replica")
    eb(7, "api", "redis", "WS fanout ＋ cache")

    c.append(edge(f"{P}_tp1", f"{P}_techweb", f"{P}_techapi", "REST / WS :8002", E_SOLID, parent=tp))

    # ── 註記 ──
    c.append(node(f"{P}_ntopo",
                  "雲端 3 Cloud Run（api ＝ API_SURFACE=all 單體，無 tech/platform/landing 雲端部署、技師庫雲端未接）；"
                  "本機 compose 多 surface —— 拓撲不對稱為已知缺口。",
                  340, 905, 650, 92, note("yellow")))
    c.append(node(f"{P}_nsig",
                  "可觀測性：api / agent / web / knowledge-refinery / tech-api 皆經 OTel 匯聚 SigNoz，圖中以一條代表線示意。",
                  1030, 905, 520, 72, note("gray")))

    c += legend(P, 40, 560, [
        ("fill", "blue", "per-brand bundle（web·api·agent）"),
        ("fill", "green", "集中共用平台（Casdoor·SigNoz·Kafka）"),
        ("fill", "teal", "獨立子系統（技師平台 / 精煉）"),
        ("fill", "orange", "MCP-RAG 檢索（知識 / AI）"),
        ("fill", "purple", "Data Store（品牌/Redis/技師/平台庫）"),
        ("fill", "gray", "外部 actor / LINE"),
        ("edge", E_MAIN, "粗實線 = 即時客服熱路徑（LINE↔agent）"),
        ("edge", E_SOLID, "實線 = 營運 / 服務憑證 / OHS"),
        ("edge", E_DASH, "虛線 = 核可後灌語料（回流）"),
        ("edge", E_DOT, "點線 = 可觀測性 / 事件（🔜）"),
    ], w=295)
    return ("d03_1", "03-1 Container 主錨（C4 L2）", c)


def d_03_4():
    P = "x4"
    c = [title(f"{P}_ttl", "03-4 State Machines（工單 / 報價 / 問題卡） · BRD §5.7", w=1100),
         subtitle(f"{P}_sub",
                  "三具核心狀態機並排；工單值域由 flow DSL 定義（ADR-P010），報價綁不可變定價快照，問題卡雙 gate 分管派工與精煉。",
                  w=1300)]

    def stt(cid, val, x, y, col, w=150, h=46, parent="1"):
        c.append(node(f"{P}_{cid}", val, x, y, w, h, state_style(col), parent=parent))
    def dot(cid, x, y, parent="1"):
        c.append(node(f"{P}_{cid}", "", x, y, 20, 20,
                      "ellipse;whiteSpace=wrap;html=1;fillColor=#000000;strokeColor=#000000;", parent=parent))
    def tr(cid, s, t, v, parent="1", dash=False, exit=None, entry=None, pts=None):
        st = E_STATE + ("dashed=1;" if dash else "")
        c.append(edge(f"{P}_{cid}", f"{P}_{s}", f"{P}_{t}", v, st,
                      parent=parent, exit=exit, entry=entry, pts=pts))

    # ── WorkOrder（blue）──
    wo = f"{P}_wo"
    c.append(node(wo, "WorkOrder 工單（flow DSL）· ADR-P010", 30, 100, 490, 840, container("blue")))
    dot("wo_s", 108, 20, parent=wo)
    stt("wo_created", "created", 45, 52, "blue", parent=wo)
    stt("wo_dispatched", "dispatched", 45, 150, "blue", parent=wo)
    stt("wo_onsite", "on_site", 45, 248, "blue", parent=wo)
    stt("wo_inprog", "in_progress", 45, 452, "blue", parent=wo)
    stt("wo_completed", "completed", 45, 580, "blue", parent=wo)
    stt("wo_settled", "settled", 45, 678, "green", parent=wo)
    stt("wo_quoted", "quoted", 285, 300, "blue", parent=wo)
    stt("wo_approved", "approved", 285, 400, "blue", parent=wo)
    stt("wo_cancelled", "cancelled", 165, 772, "gray", parent=wo)
    tr("wot0", "wo_s", "wo_created", "", parent=wo)
    tr("wot1", "wo_created", "wo_dispatched", "assign · role:dispatcher", parent=wo)
    tr("wot2", "wo_created", "wo_dispatched", "急件直通：emergency 4 類 · 4h 內補審",
       parent=wo, dash=True, exit=(1, 0.4), entry=(1, 0.4), pts=[(235, 74), (235, 172)])
    tr("wot3", "wo_dispatched", "wo_onsite", "arrive · onsite_consent", parent=wo)
    tr("wot4", "wo_onsite", "wo_inprog", "start（無異動直進）", parent=wo)
    tr("wot5", "wo_onsite", "wo_quoted", "requote：估價誤差 / 加價 / 改項", parent=wo)
    tr("wot6", "wo_quoted", "wo_approved", "customer_approve v+1", parent=wo)
    tr("wot7", "wo_approved", "wo_inprog", "start", parent=wo)
    tr("wot8", "wo_inprog", "wo_completed", "finish · 存證三件", parent=wo)
    tr("wot9", "wo_completed", "wo_settled", "settle · 收款 / 結算", parent=wo)
    tr("wot10", "wo_dispatched", "wo_cancelled", "", parent=wo, dash=True)
    tr("wot11", "wo_onsite", "wo_cancelled", "任一非終態 → cancelled", parent=wo, dash=True)
    tr("wot12", "wo_inprog", "wo_cancelled", "", parent=wo, dash=True)

    # ── Quote（yellow）──
    qt = f"{P}_qt"
    c.append(node(qt, "Quote 報價 · BR-PRICING / ADR-P014", 545, 100, 445, 840, container("yellow")))
    dot("qt_s1", 108, 20, parent=qt)
    stt("qt_draft", "draft", 55, 52, "yellow", parent=qt)
    stt("qt_iapp", "internal_approved", 55, 150, "yellow", parent=qt)
    stt("qt_sent", "customer_sent", 55, 258, "yellow", parent=qt)
    stt("qt_reject", "rejected", 255, 190, "gray", parent=qt)
    stt("qt_expire", "expired（48h）", 255, 316, "gray", parent=qt)
    stt("qt_confirm", "customer_confirmed", 55, 490, "green", parent=qt)
    stt("qt_retro", "retrospective_audit_only\n（急件事後）", 55, 640, "yellow", h=56, parent=qt)
    dot("qt_s2", 300, 610, parent=qt)
    tr("qtt0", "qt_s1", "qt_draft", "", parent=qt)
    tr("qtt1", "qt_draft", "qt_iapp", "內部核可", parent=qt)
    tr("qtt2", "qt_iapp", "qt_sent", "AI 僅 range · final 需人核", parent=qt)
    tr("qtt3", "qt_sent", "qt_confirm", "客戶 LIFF 確認", parent=qt)
    tr("qtt4", "qt_sent", "qt_reject", "客戶拒絕", parent=qt)
    tr("qtt5", "qt_sent", "qt_expire", "48h 未確認", parent=qt)
    tr("qtt6", "qt_reject", "qt_draft", "re-version v+1（supersedes 串鏈）", parent=qt, dash=True)
    tr("qtt7", "qt_expire", "qt_draft", "re-version v+1", parent=qt, dash=True)
    tr("qtt8", "qt_s2", "qt_retro", "急件事後補", parent=qt)
    tr("qtt9", "qt_retro", "qt_confirm", "事後 LIFF / 紙本確認", parent=qt)

    # ── ProblemCard（orange · 雙 gate）──
    pc = f"{P}_pc"
    c.append(node(pc, "ProblemCard 問題卡（雙 gate）· SDS §4.6", 1015, 100, 445, 840, container("orange")))
    dot("pc_s", 108, 20, parent=pc)
    stt("pc_draft", "draft（incomplete）\nAI 起草", 50, 52, "orange", h=52, parent=pc)
    stt("pc_triaged", "triaged 已分流\nL1 / L2 / L3", 50, 240, "orange", h=52, parent=pc)
    stt("pc_handled", "handled 已處理\n（resolved）", 50, 430, "orange", h=52, parent=pc)
    stt("pc_kr", "knowledge_ready\n② 知識閘通過", 50, 620, "green", h=52, parent=pc)
    c.append(node(f"{P}_pc_pick", "knowledge-refinery 汲取\n只吃 knowledge_ready=true",
                  50, 740, 300, 56, rrect("orange"), parent=pc))
    c.append(node(f"{P}_pc_g1",
                  "Gate ① 進料閘\n完整度 ≥ 0.8 ＋ 必填集\n（brand/model/failure_mode\n/triage_tier /[L3]address）\n→ 派工放行、防假工單",
                  240, 110, 185, 118, note("yellow"), parent=pc))
    c.append(node(f"{P}_pc_g2",
                  "Gate ② 知識閘\n失效分析 spine\n（root_cause/corrective_action\n/verification/disposition）\n→ 供精煉汲取（可事後補）",
                  240, 470, 185, 118, note("yellow"), parent=pc))
    tr("pct0", "pc_s", "pc_draft", "", parent=pc)
    tr("pct1", "pc_draft", "pc_triaged", "① 進料閘（小編補缺）", parent=pc)
    tr("pct2", "pc_triaged", "pc_handled", "L1 AI直回 / L2 文字客服·電話回撥 / L3 現場完工", parent=pc)
    tr("pct3", "pc_handled", "pc_kr", "② 知識閘", parent=pc)
    tr("pct4", "pc_kr", "pc_pick", "供知識精煉汲取（§9）", parent=pc, dash=True)

    # ── 每機註記 ──
    c.append(node(f"{P}_nwo",
                  "created 前置 ＝ 線上報價已客戶確認 或 急件（BR-WO-01）；completed 硬閘 ＝ 地址 ＋ 報價確認 ＋ 存證三件。",
                  30, 950, 490, 78, note("yellow")))
    c.append(node(f"{P}_nqt",
                  "每筆報價綁不可變定價快照（sha256）；AI 僅可給 range，永禁 final quote / 折扣 / 免費保固。",
                  545, 950, 445, 78, note("yellow")))
    c.append(node(f"{P}_npc",
                  "「operational 已處理」≠「知識完整」：卡可先結案、知識欄事後補；精煉只汲取 knowledge_ready=true。",
                  1015, 950, 445, 78, note("yellow")))

    c += legend(P, 1490, 100, [
        ("fill", "blue", "WorkOrder 狀態（flow DSL）"),
        ("fill", "yellow", "Quote 狀態 / 定價設計態"),
        ("fill", "orange", "ProblemCard 狀態"),
        ("fill", "green", "終態 / knowledge_ready（下游可取）"),
        ("fill", "gray", "cancelled / rejected / expired"),
        ("edge", E_STATE, "實線 = 狀態轉移（標籤＝事件/guard）"),
        ("edge", E_STATE + "dashed=1;", "虛線 = re-version / 精煉 / 取消"),
    ], w=205)
    return ("d03_4", "03-4 State Machines（工單/報價/問題卡）", c)


def d_05_1():
    P = "s1"
    c = [title(f"{P}_ttl", "05-1 平台共用核心 Kernel · 15_SDS §3 / 13_Security", w=1100),
         subtitle(f"{P}_sub",
                  "產業無關的可重用核心（永不隨 Vertical Pack 改）；產業深度活在積木庫 / 知識 / flow DSL，經契約掛載。",
                  w=1300)]

    # ── Vertical Pack（yellow · 經契約掛載）──
    vp = f"{P}_vp"
    c.append(node(vp, "Vertical Pack 產業配置層（locksmith@1.2.0 …；核心不隨其改）",
                  350, 58, 1000, 92, container("yellow")))
    for i, t in enumerate(["catalog（服務/料件/定價）", "flow DSL（狀態機）",
                           "knowledge（skills＋RAG 語料）", "ui_composition（畫面組裝）"]):
        c.append(node(f"{P}_vp{i}", t, 15 + i * 246, 38, 232, 44, rrect("yellow"), parent=vp))

    # ── Kernel（green container）── 5 群
    ker = f"{P}_ker"
    c.append(node(ker, "平台共用核心 Kernel（產業無關 · 永不隨 Vertical Pack 改）",
                  120, 200, 1460, 555, container("green")))
    groups = [
        ("g1", "① 工單引擎", 15, [
            ("flow DSL executor\nguard → block → 持久化", "yellow"),
            ("積木契約 registry\ndomain block / primitives 雙層", "yellow"),
            ("SLA timer（Redis）", "green"),
            ("事件溯源 work_order_events", "green"),
            ("outbox（side-effect 保證）", "green"),
        ]),
        ("g2", "② 身分與授權", 303, [
            ("Casdoor\norg / License / OIDC", "green"),
            ("四方 RBAC\nrole_required · deny-by-default", "green"),
            ("SoD 雙簽\nInitiator / Approver / Executor", "green"),
        ]),
        ("g3", "③ 金流軌", 591, [
            ("7 帳本 append-only", "green"),
            ("reversal entry（只增不改）", "green"),
            ("pricing snapshot（sha256）", "green"),
            ("reconcile 對帳閘門", "green"),
        ]),
        ("g4", "④ 可觀測性", 879, [
            ("SigNoz\nmetrics / logs / traces / alerts", "green"),
            ("OPIK（LLM 品質）", "orange"),
            ("audit log（hash chain）", "green"),
        ]),
        ("g5", "⑤ 事件骨幹", 1167, [
            ("Kafka 事件骨幹\ncommission.accrued / 工單投影\n🔜 階段二", "green"),
            ("Phase 1：outbox 輪詢\n（過渡替代）", "green"),
        ]),
    ]
    gids = {}
    for gid, gttl, gx, items in groups:
        cid = f"{P}_{gid}"
        gids[gid] = cid
        c.append(node(cid, gttl, gx, 40, 270, 495, container("green"), parent=ker))
        for j, (label, col) in enumerate(items):
            c.append(node(f"{cid}_i{j}", label, 12, 40 + j * 74, 246, 62, rrect(col), parent=cid))

    # ── 下方三庫（purple cyl，物理隔離）──
    c.append(node(f"{P}_brandDB", "品牌庫 pgvector\n業務 ＋ 唯一事實語料", 340, 800, 260, 120, cyl("purple")))
    c.append(node(f"{P}_techDB", "技師庫 lock_tech\n技師身分域", 720, 800, 260, 120, cyl("purple")))
    c.append(node(f"{P}_platDB", "平台庫 platform-db\n管理員 / 品牌申請", 1100, 800, 260, 120, cyl("purple")))
    c.append(node(f"{P}_niso", "三庫物理隔離\n＝ 租戶模型 ADR-020\n（不跨庫 FK · 跨系統 ref）",
                  1390, 805, 200, 110, note("purple")))

    # ── 連線 ──
    c.append(edge(f"{P}_e1", vp, ker, "契約掛載 · 核心／pack 邊界 ＝ ADR-001", E_DASH))
    c.append(edge(f"{P}_e2", gids["g1"], f"{P}_brandDB", "work_order_events / outbox 持久化", E_SOLID))
    c.append(edge(f"{P}_e3", gids["g3"], f"{P}_brandDB", "7 帳本 / pricing snapshot", E_SOLID))
    c.append(edge(f"{P}_e4", gids["g5"], f"{P}_techDB", "commission.accrued → Settlement 投影", E_DASH))
    c.append(edge(f"{P}_e5", gids["g2"], f"{P}_platDB", "平台治理 / 品牌申請", E_DASH))

    c += legend(P, 1390, 930, [
        ("fill", "green", "平台共用核心 / 共用服務"),
        ("fill", "yellow", "flow DSL / 積木契約 / Vertical Pack（設計態）"),
        ("fill", "orange", "OPIK LLM 品質（知識 / AI）"),
        ("fill", "purple", "三庫 Data Store（物理隔離）"),
        ("edge", E_SOLID, "實線 = 持久化 / 依賴"),
        ("edge", E_DASH, "虛線 = 契約掛載 / 事件投影（🔜）"),
    ], w=300)
    return ("d05_1", "05-1 平台共用核心 Kernel", c)


def d_04_2():
    P = "f2"
    c = [title(f"{P}_ttl", "04-2 跨系統資料流 DAG（left → right）  ·  00_platform / P2 / 09", w=1100),
         subtitle(f"{P}_sub",
                  "色彩語意：紅＝即時客服熱路徑　藍＝品牌後台營運　綠＝平台共用服務　"
                  "青＝獨立子系統　橙＝知識 / AI　紫＝Data Store　灰＝外部", w=1250)]

    # ── 區帶（背景框，fillColor=none 不遮節點）─────────────────────────
    def zone(cid, label, x, y, w, h, stroke):
        st = (f"rounded=1;whiteSpace=wrap;html=1;fillColor=none;strokeColor={stroke};"
              f"verticalAlign=top;align=left;fontStyle=1;fontSize=12;dashed=1;spacingLeft=8;")
        return node(cid, label, x, y, w, h, st)
    c.append(zone(f"{P}_zA", "品牌 per-brand bundle　─　客服熱路徑（紅）＋ 後台營運（藍）",
                  20, 80, 1570, 210, "#6C8EBF"))
    c.append(zone(f"{P}_zB", "technician-platform　─　跨租戶技師共享池（獨立子系統）",
                  800, 310, 790, 120, "#0E8088"))
    c.append(zone(f"{P}_zC", "knowledge-refinery 閉環　─　知識精煉（License 附加，ADR-P001）",
                  20, 600, 780, 170, "#D79B00"))

    # ── 品牌 · 客服熱路徑（y=110）+ 後台營運（y=210）──────────────────
    c.append(node(f"{P}_line",    "📱 LINE 客戶",                     40, 110, 150, 54, rect("gray")))
    c.append(node(f"{P}_agent",   "agent 對話\n（LockCore 客服）",    230, 110, 150, 54, rrect("red")))
    c.append(node(f"{P}_pc",      "問題卡 draft\n（AI 草擬 · incomplete）", 420, 110, 150, 54, rrect("red")))
    c.append(node(f"{P}_cs",      "小編確認\n（completeness gate）",   620, 210, 150, 54, rrect("blue")))
    c.append(node(f"{P}_qe",      "報價引擎\n線上估價 → 送客戶",        820, 210, 150, 54, rrect("blue")))
    c.append(node(f"{P}_liff",    "客戶 LIFF 確認\n（postback 同意）", 1020, 210, 150, 54, rect("gray")))
    c.append(node(f"{P}_wo",      "工單 created\n（綁已確認報價）",    1220, 210, 150, 54, rrect("blue")))
    c.append(node(f"{P}_ohs",     "OHS 派工媒合\n（api → 技師池）",    1420, 210, 150, 54, rrect("blue")))

    # ── 技師平台（y=360，teal）────────────────────────────────────────
    c.append(node(f"{P}_done",    "完工三硬閘\n（照片 ≥ 3 · 簽名 · 序號）", 820, 360, 150, 54, rrect("teal")))
    c.append(node(f"{P}_onsite",  "現場\n到府 / 門檢 / 存證",         1020, 360, 150, 54, rrect("teal")))
    c.append(node(f"{P}_accept",  "師傅 web 接單\n（active 技師）",    1220, 360, 150, 54, rrect("teal")))
    c.append(node(f"{P}_tapi",    "tech-api\n（技師平台）",           1420, 360, 150, 54, rrect("teal")))

    # ── 結算軌（y=480）────────────────────────────────────────────────
    c.append(node(f"{P}_slbl",
                  "結算軌 ▸ 完工事實 → 品牌計費（per-job）→ commission.accrued → 技師平台 Settlement → reconcile",
                  40, 448, 500, 30, txt() + "fontSize=11;fontColor=#666666;"))
    c.append(node(f"{P}_bill",    "計費 Billing\n（品牌庫 · per-job 佣金明細）", 820, 480, 170, 56, rrect("blue")))
    c.append(node(f"{P}_settle",  "技師平台 Settlement\n（statement / payout）", 560, 480, 170, 56, rrect("teal")))
    c.append(node(f"{P}_recon",
                  "reconcile 對帳閘門：品牌計費總額 ↔ 技師平台彙總必對平（事件最終一致，金流以閘門把關）",
                  560, 550, 430, 44, note("green")))

    # ── 知識精煉閉環（y=600，orange / purple）─────────────────────────
    c.append(node(f"{P}_msgs",    "messages 三方全量\ncustomer / ai / human\n（BR-CONV-03）",
                  60, 608, 180, 64, cyl("purple")))
    c.append(node(f"{P}_kr",      "knowledge_ready\n問題卡",          60, 700, 180, 56, rrect("orange")))
    c.append(node(f"{P}_refinery","knowledge-refinery\nraw → bronze → silver → HITL 審核",
                  320, 636, 200, 72, rrect("orange")))
    c.append(node(f"{P}_pgv",     "品牌庫 pgvector\n唯一事實語料",     600, 608, 180, 64, cyl("purple")))
    c.append(node(f"{P}_skill",   "agent skill\n（行為 · git-tracked）", 600, 700, 180, 56, rrect("orange")))

    # ── 主資料鏈（E_MAIN）────────────────────────────────────────────
    c.append(edge(f"{P}_m1", f"{P}_line",  f"{P}_agent", "LINE webhook",                E_MAIN))
    c.append(edge(f"{P}_m2", f"{P}_agent", f"{P}_pc",    "AI 診斷 → 草擬",              E_MAIN))
    c.append(edge(f"{P}_m3", f"{P}_pc",    f"{P}_cs",    "transfer_to_human → 補齊",    E_MAIN))
    c.append(edge(f"{P}_m4", f"{P}_cs",    f"{P}_qe",    "confirmed → 建報價",          E_MAIN))
    c.append(edge(f"{P}_m5", f"{P}_qe",    f"{P}_liff",  "LINE Flex / LIFF 送出",       E_MAIN))
    c.append(edge(f"{P}_m6", f"{P}_liff",  f"{P}_wo",    "customer_confirmed → 1-click 開單", E_MAIN))
    c.append(edge(f"{P}_m7", f"{P}_wo",    f"{P}_ohs",   "派工",                        E_MAIN))

    # ── 跨系統 command / 事件（E_SOLID）──────────────────────────────
    c.append(edge(f"{P}_s1", f"{P}_ohs",    f"{P}_tapi",   "OHS API 媒合",              E_SOLID))
    c.append(edge(f"{P}_s2", f"{P}_tapi",   f"{P}_accept", "推播新工單",                E_SOLID))
    c.append(edge(f"{P}_s3", f"{P}_accept", f"{P}_onsite", "接單 → 到場",               E_SOLID))
    c.append(edge(f"{P}_s4", f"{P}_onsite", f"{P}_done",   "施工 → 完工",               E_SOLID))
    c.append(edge(f"{P}_req", f"{P}_onsite", f"{P}_qe",
                  "現場報價修正 requote command\nADR-027：只收 diff · 零定價權", E_SOLID))
    c.append(edge(f"{P}_s5", f"{P}_done",   f"{P}_bill",   "完工事實 → 計費",           E_MAIN))
    c.append(edge(f"{P}_s6", f"{P}_bill",   f"{P}_settle",
                  "commission.accrued　🔜 Kafka（Phase 1 outbox）", E_SOLID))
    c.append(edge(f"{P}_d1", f"{P}_bill",   f"{P}_recon",  "",                          E_DOT))
    c.append(edge(f"{P}_d2", f"{P}_settle", f"{P}_recon",  "",                          E_DOT))

    # ── 知識學習回流（E_DASH）────────────────────────────────────────
    c.append(edge(f"{P}_k1", f"{P}_agent", f"{P}_msgs", "對話全量存檔 · BR-CONV-03",
                  E_DASH, exit=(0.2, 1), entry=(0.5, 0)))
    c.append(edge(f"{P}_k2", f"{P}_pc", f"{P}_kr", "knowledge_ready",
                  E_DASH, exit=(0.2, 1), entry=(1, 0.5), pts=[(300, 450)]))
    c.append(edge(f"{P}_k3", f"{P}_msgs",     f"{P}_refinery", "診斷素材",              E_DASH))
    c.append(edge(f"{P}_k4", f"{P}_kr",       f"{P}_refinery", "",                      E_DASH))
    c.append(edge(f"{P}_k5", f"{P}_refinery", f"{P}_pgv",      "事實 chunk+embedding",  E_DASH))
    c.append(edge(f"{P}_k6", f"{P}_refinery", f"{P}_skill",    "行為 / 精選",           E_DASH))
    c.append(edge(f"{P}_k7", f"{P}_pgv", f"{P}_agent",
                  "RAG-via-MCP 檢索唯一語料 ＋ 載入 skill · 閉環（詳見 04-4）",
                  E_DASH, exit=(0.3, 1), entry=(0.5, 0),
                  pts=[(654, 800), (15, 800), (15, 88), (315, 88)]))

    c += legend(P, 1150, 560, [
        ("fill", "red",    "即時客服熱路徑"),
        ("fill", "blue",   "品牌後台營運"),
        ("fill", "teal",   "獨立子系統（技師平台）"),
        ("fill", "orange", "知識 / AI"),
        ("fill", "purple", "Data Store"),
        ("fill", "green",  "平台共用服務 / 對帳閘門"),
        ("fill", "gray",   "外部實體"),
        ("edge", E_MAIN,   "粗實線 ＝ 即時主資料鏈"),
        ("edge", E_SOLID,  "實線 ＝ 跨系統 command / 事件"),
        ("edge", E_DASH,   "虛線 ＝ 知識學習回流"),
        ("edge", E_DOT,    "點線 ＝ 對帳閘門支撐"),
    ], w=310)
    return ("d04_2", "04-2 跨系統資料流 DAG", c)


def d_04_3():
    P = "f3"
    c = [title(f"{P}_ttl", "04-3 Sequence — 單次工單全程（報價先行）  ·  BRD §5.6", w=1100)]

    parts = [("C",   "客戶（LINE）",          "gray"),
             ("AI",  "AI 客服 agent",         "red"),
             ("CS",  "派工小編",              "blue"),
             ("QE",  "報價引擎",              "blue"),
             ("T",   "技師",                  "teal"),
             ("SYS", "系統（API·DB·Outbox）", "green")]
    x0, gap, w, top, life_bottom = 60, 215, 170, 70, 1120
    px = {}
    for i, (k, lbl, col) in enumerate(parts):
        x = x0 + i * gap
        px[k] = x + w // 2
        c.append(node(f"{P}_p{i}", lbl, x, top, w, 44, rrect(col)))
        c.append(free_edge(f"{P}_ll{i}", x + w // 2, top + 44, x + w // 2, life_bottom, "",
                           "html=1;endArrow=none;strokeColor=#999999;", dash=True))
    c.append(node(f"{P}_pre", "前置：技師須經技師平台核准 status ＝ active 方可被派工",
                  px["T"] - 90, 116, 420, 30, note("teal")))

    def msg(mid, y, a, b, label, dash=False, self_=False):
        xa, xb = px[a], px[b]
        if self_:
            c.append(free_edge(f"{P}_m{mid}", xa, y, xa + 72, y, label,
                               "html=1;endArrow=classic;endFill=1;strokeColor=#333333;fontSize=10;"
                               "rounded=1;exitX=1;", dash=dash))
            c.append(free_edge(f"{P}_m{mid}b", xa + 72, y, xa, y + 20, "",
                               "html=1;endArrow=classic;endFill=1;strokeColor=#333333;", dash=dash))
        else:
            c.append(free_edge(f"{P}_m{mid}", xa, y, xb, y, label,
                               "html=1;endArrow=classic;endFill=1;strokeColor=#333333;fontSize=10;", dash=dash))

    def frame(fid, label, y, h, stroke):
        c.append(node(f"{P}_{fid}", label, 45, y, 1285, h,
                      f"rounded=0;whiteSpace=wrap;html=1;fillColor=none;strokeColor={stroke};"
                      f"verticalAlign=top;align=left;fontSize=11;fontStyle=1;dashed=1;"))

    msg(1, 170, "C", "AI", "① LINE 文字訊息")
    msg(2, 212, "AI", "AI", "② 意圖判斷（決策樹）", self_=True)
    msg(3, 270, "AI", "SYS", "③ transfer_to_human（escalation）")
    frame("par", "par　並行（互不依賴）", 300, 86, "#B85450")
    msg("4a", 328, "AI", "C", "④ 回覆「已為您轉接專員」", dash=True)
    msg("4b", 362, "SYS", "CS", "④ 建立 AI 草擬問題卡")
    msg(5, 410, "CS", "SYS", "⑤ 補齊欄位並確認（completeness gate）")
    msg(6, 448, "CS", "QE", "⑥ 建立線上估價報價並送出")
    msg(7, 486, "QE", "SYS", "⑦ 寫入 LINE 外送佇列（quote_proposal）")
    frame("loop", "loop　背景輪詢（每 10 秒）", 516, 54, "#B85450")
    msg(8, 544, "SYS", "C", "⑧ 推送報價 Flex")
    msg(9, 598, "C", "SYS", "⑨ postback 同意（q:a）")
    msg(10, 636, "SYS", "QE", "⑩ 驗擁有權 → 報價 customer_confirmed")
    msg("10b", 674, "QE", "CS", "同步「客戶已同意」至對話管理", dash=True)
    msg(11, 712, "CS", "SYS", "⑪ 1-click 開立工單（綁已確認報價）")
    msg(12, 750, "CS", "SYS", "⑫ 派工（檢查 active 技師）")
    msg(13, 788, "SYS", "T", "⑬ 通知新工單")
    msg(14, 826, "T", "SYS", "⑭ 接單 → 到場 → 門檢")
    frame("opt", "opt　現場與線上報價不符（估價誤差 / 加價 / 改項）", 856, 128, "#D6B656")
    msg("o1", 884, "T", "QE", "發起 requote v+1（只提交 diff · 零定價權）")
    msg("o2", 922, "QE", "C", "LIFF 推送修正報價（fallback QR / 紙本）")
    msg("o3", 960, "C", "SYS", "確認 v+1 後復工")
    msg(15, 1014, "T", "SYS", "⑮ 施工 → 完工（硬閘三件）")
    msg(16, 1052, "SYS", "C", "⑯ 通知工單已完工待確認")
    msg(17, 1090, "C", "SYS", "⑰ 確認結案並評分")

    c.append(node(f"{P}_note",
                  "急件 4 類 carve-out：跳過 ⑥–⑩ 直接開單派工；"
                  "onsite 結束後 4h 內補 retrospective 報價（15_SDS §4.5）。",
                  400, 1140, 720, 44, note("yellow")))
    c += legend(P, 60, 1140, [
        ("edge", E_STRAIGHT, "實線箭頭 ＝ 同步訊息 / 呼叫"),
        ("edge", "html=1;endArrow=classic;endFill=1;strokeColor=#333333;dashed=1;",
         "虛線箭頭 ＝ 非同步回覆 / 回寫"),
        ("line", "yellow", "opt 框 ＝ 現場報價修正輪（可選）"),
        ("line", "red",    "par / loop 框 ＝ 並行 / 輪詢"),
        ("fill", "red",    "AI 客服（熱路徑）"),
        ("fill", "blue",   "品牌後台（小編 / 報價引擎）"),
        ("fill", "teal",   "技師（獨立子系統）"),
        ("fill", "green",  "系統（API·DB·Outbox）"),
    ], w=320)
    return ("d04_3", "04-3 Sequence — 單次工單全程", c)


def d_04_4():
    P = "f4"
    c = [title(f"{P}_ttl", "04-4 知識精煉閉環（HITL MLOps）  ·  BRD §5.5", w=1100)]

    # 環形 6 節點（順時針，橢圓座標）
    ring = [
        ("n1", "① 輸入汲取\n診斷對話：messages 三方全量\n＋ knowledge_ready 問題卡\n"
               "產品素材：YouTube / 官網 / 手冊", "orange", 655, 138),
        ("n2", "② Medallion\nraw → bronze → silver", "purple", 915, 263),
        ("n3", "③ LLM 提煉分流\n事實　vs　行為 / 精選", "orange", 915, 513),
        ("n4", "④ HITL 審核 UI\ndraft → 人審 diff → 核可\n（human-in-the-loop · 獨立 web）",
               "green", 655, 638),
        ("n5", "⑤ 落地\n事實 chunk+embedding → 品牌庫 pgvector 唯一語料\n"
               "行為 → agent skill（git-tracked）", "orange", 395, 513),
        ("n6", "⑥ agent RAG-via-MCP 檢索\n（🔜 pgvector 語義層 · Phase 2）", "red", 395, 263),
    ]
    for cid, v, col, x, y in ring:
        c.append(node(f"{P}_{cid}", v, x, y, 210, 84, rrect(col)))

    # 附屬 data store（⑤ 落地 → 唯一語料）
    c.append(node(f"{P}_pgv", "品牌庫 pgvector\n唯一事實語料", 395, 632, 150, 64, cyl("purple")))
    c.append(edge(f"{P}_epgv", f"{P}_n5", f"{P}_pgv", "灌注唯一語料", E_SOLID))

    # 環線（E_MAIN）+ 閉環回流（E_DASH）
    for eid, a, b, lbl, st in [
        ("r1", "n1", "n2", "Medallion 治理",                    E_MAIN),
        ("r2", "n2", "n3", "silver 知識點",                     E_MAIN),
        ("r3", "n3", "n4", "draft（事實 / 行為）",              E_MAIN),
        ("r4", "n4", "n5", "核可 → 落地",                       E_MAIN),
        ("r5", "n5", "n6", "RAG 檢索唯一語料 ＋ 載入 skill",    E_MAIN),
        ("r6", "n6", "n1", "回饋下一輪對話品質提升 🔁",        E_DASH),
    ]:
        c.append(edge(f"{P}_{eid}", f"{P}_{a}", f"{P}_{b}", lbl, st))

    # 中央前提 note（yellow）
    c.append(node(f"{P}_center",
                  "閉環資料前提　BR-CONV-03\n"
                  "客戶 / AI / 真人接管三方訊息全量存檔，\n缺一樣本失真，閉環不成立",
                  610, 372, 300, 116, note("yellow")))
    # 角落 note（孿生對稱）
    c.append(node(f"{P}_corner",
                  "License 附加模組（ADR-018）\n"
                  "與 AI Onboarding Compiler 孿生對稱：\n"
                  "一煉知識、一煉流程，共用 HITL 骨架（階段二）",
                  1090, 120, 320, 104, note("gray")))

    c += legend(P, 1150, 560, [
        ("fill", "orange", "知識 / AI（汲取・提煉・行為）"),
        ("fill", "purple", "Data Store（Medallion · pgvector）"),
        ("fill", "green",  "平台共用服務（HITL 審核 UI）"),
        ("fill", "red",    "即時客服（agent RAG 檢索）"),
        ("edge", E_MAIN,   "粗實線 ＝ 精煉主環"),
        ("edge", E_DASH,   "虛線 ＝ 閉環回饋回流"),
    ], w=300)
    return ("d04_4", "04-4 知識精煉閉環（HITL MLOps）", c)


def d_06_1():
    """Solution Architecture Overview：L1 責任區 + L2 元件 + 四種資料路徑。"""
    P = "r1"
    c = [
        title(
            f"{P}_ttl",
            "06-1 高階端到端參考架構  ·  Logical Components + Data Flow + Integration",
            x=25,
            w=1450,
        ),
        subtitle(
            f"{P}_sub",
            "Smart Lock AI 客服與派工 SaaS｜工業視覺語意轉譯：即時互動、領域事件、控制治理、持久化/重播/證據",
            x=25,
            w=1500,
        ),
    ]

    zones = {
        "z1": ("Z1  Actors & Inbound Signals", 25, 75, 220, 700, "#F8FAFC", "#94A3B8"),
        "z2": ("Z2  Channel & AI Runtime", 260, 75, 295, 700, "#EFF6FF", "#60A5FA"),
        "z3": ("Z3  Interaction & Event Distribution", 570, 75, 310, 700, "#F0FDF4", "#4ADE80"),
        "z4": ("Z4  Domain Services & Data", 895, 75, 440, 700, "#FFF7ED", "#FB923C"),
        "z5": ("Z5  Applications & External Systems", 1350, 75, 325, 700, "#F8FAFC", "#64748B"),
        "z6": ("Z6  Cross-Cutting Management Capabilities", 25, 800, 1650, 220, "#FAF5FF", "#C084FC"),
    }
    for zid, (label, x, y, w, h, fill, stroke) in zones.items():
        c.append(node(f"{P}_{zid}", label, x, y, w, h, ref_zone(fill, stroke)))

    # Z1 — 外部角色與訊號（不承擔業務狀態）
    z1 = f"{P}_z1"
    c.extend(
        [
            node(f"{P}_cust", "Customer Interaction Signal\nLINE 詢問 · LIFF/postback 決策", 15, 55, 190, 75, ref_component("#64748B", "#FFFFFF"), parent=z1),
            node(f"{P}_ops", "Brand Operations Decision\n問題卡 · 報價 · 派工 · 結算", 15, 175, 190, 75, ref_component("#64748B", "#FFFFFF"), parent=z1),
            node(f"{P}_techsig", "Technician Field Action\n接單 · 到場 · requote · 存證", 15, 295, 190, 75, ref_component("#64748B", "#FFFFFF"), parent=z1),
            node(f"{P}_know", "Knowledge & Diagnostic Source\n產品素材 · 三方診斷對話", 15, 415, 190, 75, ref_component("#64748B", "#FFFFFF"), parent=z1),
            node(
                f"{P}_z1note",
                "Signal only\n角色意圖在此表達；\n業務真相一律由 Z4 擁有",
                15,
                545,
                190,
                95,
                ref_component("#94A3B8", "#F8FAFC", dashed=True),
                parent=z1,
            ),
        ]
    )

    # Z2 — Channel / AI Runtime
    z2 = f"{P}_z2"
    c.extend(
        [
            node(f"{P}_gw", "LINE Gateway\n驗簽 · dedup · handover", 15, 55, 125, 90, ref_component("#2563EB", "#EFF6FF"), parent=z2),
            node(f"{P}_agent", "LockCore Agent Runtime\nTurn · Skill · Memory · Tools", 155, 55, 125, 90, ref_component("#2563EB", "#EFF6FF"), parent=z2),
            node(f"{P}_rag", "RAG-MCP Knowledge Access\ntenant ACL · pgvector citation", 15, 205, 265, 80, ref_component("#2563EB", "#FFFFFF"), parent=z2),
            node(f"{P}_model", "LiteLLM Model Gateway\nprovider routing · fallback · budget", 15, 330, 265, 80, ref_component("#2563EB", "#FFFFFF"), parent=z2),
            node(
                f"{P}_z2note",
                "責任紅線\nAI 只做對話判斷、知識回覆與 transfer_to_human；\n不擁有 final quote／工單／派工／金流真相",
                15,
                480,
                265,
                115,
                ref_component("#B91C1C", "#FEF2F2", dashed=True),
                parent=z2,
            ),
        ]
    )

    # Z3 — Integration / Distribution
    z3 = f"{P}_z3"
    c.extend(
        [
            node(f"{P}_api", "API / ACL Integration Gateway\nOIDC/S2S · tenant/role guard · idempotency", 15, 55, 280, 90, ref_component("#16A34A", "#F0FDF4"), parent=z3),
            node(f"{P}_rt", "Realtime WS\n+ Redis fan-out", 15, 190, 130, 80, ref_component("#16A34A", "#FFFFFF"), parent=z3),
            node(f"{P}_outbox", "Reliable Outbox\nLINE / notification retry", 165, 190, 130, 80, ref_component("#16A34A", "#FFFFFF"), parent=z3),
            node(f"{P}_kafka", "Event Backbone  🔜\nKafka · AsyncAPI · replay", 15, 330, 280, 85, ref_component("#16A34A", "#F0FDF4", dashed=True), parent=z3),
            node(f"{P}_ohs", "Technician OHS Adapter\nmatch/query · requote command · ACL", 15, 465, 280, 85, ref_component("#16A34A", "#FFFFFF"), parent=z3),
            node(
                f"{P}_z3note",
                "機制分工：Outbox＝可靠副作用｜Kafka＝跨系統事實｜Redis＝暫態 fan-out",
                15,
                590,
                280,
                65,
                ref_component("#15803D", "#F0FDF4", dashed=True),
                parent=z3,
            ),
        ]
    )

    # Z4 — Domain / Data
    z4 = f"{P}_z4"
    c.extend(
        [
            node(
                f"{P}_brand",
                "Brand Domain Services\nProblem Card · Quote · Work Order · Dispatch · Billing\n品牌交易與規則唯一權威",
                15,
                55,
                270,
                100,
                ref_component("#EA580C", "#FFF7ED"),
                parent=z4,
            ),
            node(
                f"{P}_tech",
                "Technician Platform\n技師身分/准入/媒合 · Work Order CQRS · Settlement",
                15,
                190,
                270,
                90,
                ref_component("#EA580C", "#FFFFFF"),
                parent=z4,
            ),
            node(
                f"{P}_ref",
                "Knowledge Refinery + HITL\nRaw/Bronze/Silver · provenance · 人審核可發布",
                15,
                320,
                270,
                90,
                ref_component("#EA580C", "#FFFFFF"),
                parent=z4,
            ),
            node(f"{P}_dbb", "Brand DB + pgvector\nSQL · JSONB · Outbox\n唯一事實語料", 300, 55, 125, 100, ref_store(), parent=z4),
            node(f"{P}_dbt", "Technician DB\n技能 · KYC · 排班\nEncrypted PII", 300, 190, 125, 90, ref_store(), parent=z4),
            node(f"{P}_obj", "Platform DB /\nEvidence Store\nLicense · GCS object\nhash · retention", 300, 320, 125, 90, ref_store(), parent=z4),
            node(
                f"{P}_z4note",
                "隔離原則：品牌不直連技師庫；跨域只走 OHS／event；CQRS 投影欄位最小化",
                15,
                590,
                410,
                65,
                ref_component("#C2410C", "#FFF7ED", dashed=True),
                parent=z4,
            ),
        ]
    )

    # Z5 — Applications / External
    z5 = f"{P}_z5"
    c.extend(
        [
            node(f"{P}_appline", "LINE / LIFF / Flex\nMessaging API · 客戶確認", 15, 55, 295, 80, ref_component("#475569", "#FFFFFF"), parent=z5),
            node(f"{P}_appbrand", "Brand Operations Portal\n對話 · 報價 · 派工 · 對帳", 15, 175, 295, 80, ref_component("#475569", "#FFFFFF"), parent=z5),
            node(f"{P}_apptech", "Technician Portal\n准入 · 接單 · 現場 · statement", 15, 295, 295, 80, ref_component("#475569", "#FFFFFF"), parent=z5),
            node(f"{P}_appplat", "Platform Console\n租戶 · License · 治理", 15, 415, 295, 80, ref_component("#475569", "#FFFFFF"), parent=z5),
            node(
                f"{P}_external",
                "External Shared Services\nCasdoor OIDC/JWKS · LLM Providers HTTPS\nGCP Runtime / Secret / Object Storage",
                15,
                535,
                295,
                100,
                ref_component("#475569", "#F8FAFC"),
                parent=z5,
            ),
        ]
    )

    # Z6 — Cross-cutting management
    z6 = f"{P}_z6"
    cross = [
        ("dev", "Channel & Client Management\nLINE OA 綁定 · webhook health\n技師客戶端准入"),
        ("cfg", "Configuration\n品牌 · 模型 · SLA\nChannel · feature flag"),
        ("sec", "Security & Governance\nOIDC · RBAC/SoD · S2S\nTenant ACL · PII policy"),
        ("obs", "Observability & Operations\nOTel · LLM trace · SLO\nAlert · audit · runbook"),
        ("cp", "Control Plane\nProvisioning · License\nVertical Pack · rollout"),
    ]
    for i, (cid, label) in enumerate(cross):
        c.append(
            node(
                f"{P}_{cid}",
                label,
                20 + i * 320,
                55,
                290,
                95,
                ref_component("#9333EA", "#FAF5FF"),
                parent=z6,
            )
        )

    # ── 藍色實線：即時互動／交易請求 ────────────────────────────────
    c.extend(
        [
            edge(
                f"{P}_i1",
                f"{P}_cust",
                f"{P}_gw",
                "LINE Webhook JSON\nX-Line-Signature",
                E_REF_INTERACTION,
                pts=[(135, 225), (338, 225)],
            ),
            edge(
                f"{P}_i2",
                f"{P}_gw",
                f"{P}_agent",
                "Normalized Turn JSON",
                E_REF_INTERACTION,
                pts=[(338, 245), (478, 245)],
            ),
            edge(
                f"{P}_i3",
                f"{P}_agent",
                f"{P}_api",
                "HTTPS Internal JSON",
                E_REF_INTERACTION,
                pts=[(478, 245), (725, 245)],
            ),
            edge(
                f"{P}_i4",
                f"{P}_api",
                f"{P}_brand",
                "REST JSON\nIdempotency-Key",
                E_REF_INTERACTION,
                pts=[(725, 245), (1115, 245)],
            ),
            edge(
                f"{P}_i5",
                f"{P}_outbox",
                f"{P}_appline",
                "Messaging API / Flex JSON",
                E_REF_INTERACTION,
                pts=[(885, 305), (885, 65), (1340, 65), (1340, 170)],
            ),
            edge(
                f"{P}_i6",
                f"{P}_rt",
                f"{P}_appbrand",
                "WebSocket JSON",
                E_REF_INTERACTION,
                pts=[(650, 255), (885, 255), (1340, 255), (1340, 290)],
            ),
            edge(
                f"{P}_i7",
                f"{P}_tech",
                f"{P}_apptech",
                "REST / WebSocket JSON",
                E_REF_INTERACTION,
                pts=[(1115, 370), (1340, 370), (1340, 410)],
            ),
            edge(
                f"{P}_i8",
                f"{P}_ops",
                f"{P}_api",
                "HTTPS Command JSON",
                E_REF_INTERACTION,
                pts=[(250, 288), (250, 675), (560, 675), (560, 170)],
            ),
            edge(
                f"{P}_i9",
                f"{P}_techsig",
                f"{P}_ohs",
                "Field Command JSON\nEvidence Metadata",
                E_REF_INTERACTION,
                pts=[(250, 408), (250, 710), (560, 710), (560, 583)],
            ),
            edge(
                f"{P}_i10",
                f"{P}_agent",
                f"{P}_model",
                "OpenAI-compatible JSON",
                E_REF_INTERACTION,
                pts=[(548, 170), (548, 445)],
            ),
            edge(
                f"{P}_i11",
                f"{P}_model",
                f"{P}_external",
                "HTTPS Model Request",
                E_REF_INTERACTION,
                pts=[(560, 445), (560, 750), (1340, 750), (1340, 660)],
            ),
            edge(
                f"{P}_i12",
                f"{P}_ohs",
                f"{P}_tech",
                "HTTPS OHS Command JSON\nS2S Credential",
                E_REF_INTERACTION,
                pts=[(890, 583), (890, 310)],
            ),
        ]
    )

    # ── 綠色虛線：AI metadata／domain event ─────────────────────────
    c.extend(
        [
            edge(
                f"{P}_e1",
                f"{P}_agent",
                f"{P}_api",
                "Escalation Metadata\nInternal JSON",
                E_REF_EVENT,
                pts=[(555, 225), (565, 225), (565, 215), (585, 215)],
            ),
            edge(
                f"{P}_e2",
                f"{P}_brand",
                f"{P}_kafka",
                "workorder.* / dispatch.*\nAsyncAPI JSON",
                E_REF_EVENT,
                pts=[(890, 180), (890, 448)],
            ),
            edge(
                f"{P}_e3",
                f"{P}_kafka",
                f"{P}_tech",
                "dispatch.* ↔ technician.*\nAsyncAPI JSON",
                E_REF_EVENT + "startArrow=classic;startFill=1;",
                pts=[(885, 448), (885, 310)],
            ),
            edge(f"{P}_e4", f"{P}_kafka", f"{P}_rt", "Projection Update\nRedis Event", E_REF_EVENT),
            edge(
                f"{P}_e5",
                f"{P}_know",
                f"{P}_ref",
                "Provenance / Diagnostic Metadata",
                E_REF_EVENT,
                pts=[(250, 528), (250, 730), (890, 730), (890, 455)],
            ),
            edge(f"{P}_e6", f"{P}_agent", f"{P}_rag", "MCP Query / Citation", E_REF_EVENT),
            edge(f"{P}_e7", f"{P}_rag", f"{P}_agent", "Tenant-filtered Result", E_REF_EVENT, pts=[(550, 320), (550, 235)]),
        ]
    )

    # ── 橘色虛線：持久化／重播／證據 ───────────────────────────────
    c.extend(
        [
            edge(f"{P}_s1", f"{P}_brand", f"{P}_dbb", "SQL / JSONB / Outbox", E_REF_STORAGE),
            edge(f"{P}_s2", f"{P}_tech", f"{P}_dbt", "SQL / Encrypted PII", E_REF_STORAGE),
            edge(
                f"{P}_s3",
                f"{P}_ref",
                f"{P}_dbb",
                "Chunk / Embedding /\nSkill Patch",
                E_REF_STORAGE,
                pts=[(1188, 440), (1188, 180)],
            ),
            edge(
                f"{P}_s4",
                f"{P}_brand",
                f"{P}_obj",
                "Evidence Object + Hash",
                E_REF_STORAGE,
                pts=[(1115, 245), (1330, 245), (1330, 440)],
            ),
            edge(
                f"{P}_s5",
                f"{P}_brand",
                f"{P}_outbox",
                "Transactional Outbox Row",
                E_REF_STORAGE,
                pts=[(890, 195), (890, 305)],
            ),
            edge(
                f"{P}_s6",
                f"{P}_kafka",
                f"{P}_obj",
                "Event Log / Replay Checkpoint",
                E_REF_STORAGE,
                pts=[(885, 500), (885, 510), (1258, 510), (1258, 485)],
            ),
        ]
    )

    # ── 紫色虛線：控制／設定／安全／可觀測 ─────────────────────────
    c.extend(
        [
            edge(
                f"{P}_c1",
                f"{P}_dev",
                f"{P}_gw",
                "LINE OA / client policy",
                E_REF_CONTROL,
                pts=[(195, 790), (250, 790), (250, 110), (342, 110)],
            ),
            edge(
                f"{P}_c2",
                f"{P}_cfg",
                f"{P}_agent",
                "Versioned runtime config",
                E_REF_CONTROL,
                pts=[(515, 790), (560, 790), (560, 110), (478, 110)],
            ),
            edge(
                f"{P}_c3",
                f"{P}_sec",
                f"{P}_api",
                "OIDC / RBAC / S2S /\ntenant policy",
                E_REF_CONTROL,
                pts=[(835, 790), (885, 790), (885, 110), (725, 110)],
            ),
            edge(
                f"{P}_c4",
                f"{P}_agent",
                f"{P}_obs",
                "OTLP / LLM trace /\ncorrelation ID",
                E_REF_CONTROL,
                pts=[(555, 200), (555, 780), (1155, 780)],
            ),
            edge(
                f"{P}_c5",
                f"{P}_appplat",
                f"{P}_cp",
                "Governance command\nOIDC",
                E_REF_CONTROL,
                pts=[(1340, 530), (1340, 790), (1475, 790)],
            ),
        ]
    )

    c += legend(
        P,
        25,
        1035,
        [
            ("edge", E_REF_INTERACTION, "藍實線 = 即時互動 / 同步交易（LINE、REST、WS、Flex）"),
            ("edge", E_REF_EVENT, "綠虛線 = AI metadata / 非同步領域事件（Internal JSON、Kafka）"),
            ("edge", E_REF_CONTROL, "紫虛線 = 控制 / 設定 / 身分 / 安全 / 可觀測"),
            ("edge", E_REF_STORAGE, "橘虛線 = SQL / Outbox / pgvector / replay / evidence"),
            ("fill", "white", "🔜 虛線元件框 = 參考目標能力，落地狀態另依證據對帳"),
        ],
        w=520,
        ttl="資料路徑與狀態圖例",
    )
    c.append(
        node(
            f"{P}_principles",
            "架構鐵律\n"
            "① AI 不擁有報價/工單/派工/金流真相　② 品牌不直連技師庫　"
            "③ 同步查詢與非同步事實分流　④ Outbox/Kafka/Redis 各有單一責任　"
            "⑤ 所有箭頭均標方向、協定或資料格式",
            570,
            1040,
            1105,
            105,
            ref_component("#334155", "#F8FAFC"),
        )
    )
    return ("d06_1", "06-1 高階端到端參考架構", c)


def d_06_2():
    """將 06-1 的 L2 元件畫成可獨立取用的責任卡。"""
    P = "r2"
    c = [
        title(f"{P}_ttl", "06-2 L2 Component Catalog  ·  Responsibility + Interface", x=25, w=1300),
        subtitle(
            f"{P}_sub",
            "每張卡可獨立搬入簡報、SAD、ADR 或細化圖；只保留責任與主要介面，不展開 class / endpoint / pod / table。",
            x=25,
            w=1500,
        ),
    ]

    groups = [
        (
            "g1",
            "Z1 Actors & Inbound Signals",
            25,
            75,
            520,
            420,
            "#F8FAFC",
            "#64748B",
            [
                ("Customer Interaction Signal", "客戶訊息、LIFF/postback 決策", "LINE webhook JSON"),
                ("Brand Operations Decision", "問題卡、報價、派工、結算操作", "Browser / REST JSON"),
                ("Technician Field Action", "接單、到場、requote、施工存證", "Web command / evidence metadata"),
                ("Knowledge & Diagnostic Source", "產品素材與三方診斷原始來源", "URL / transcript / provenance"),
            ],
        ),
        (
            "g2",
            "Z2 Channel & AI Runtime",
            570,
            75,
            520,
            420,
            "#EFF6FF",
            "#2563EB",
            [
                ("LINE Gateway", "驗簽、去重、handover 與通道交付", "HTTPS / X-Line-Signature"),
                ("LockCore Agent Runtime", "Turn、Skill、Memory、Tool allowlist", "Normalized Turn / Internal JSON"),
                ("RAG-MCP Knowledge Access", "tenant-filtered 語意檢索與引用", "MCP / pgvector result"),
                ("LiteLLM Model Gateway", "模型路由、fallback、timeout 與 budget", "HTTPS / OpenAI-compatible JSON"),
            ],
        ),
        (
            "g3",
            "Z3 Interaction & Event Distribution",
            1115,
            75,
            560,
            420,
            "#F0FDF4",
            "#16A34A",
            [
                ("API / ACL Integration Gateway", "同步 command/query、身分與租戶守衛", "REST / OIDC / S2S / RFC7807"),
                ("Realtime WS + Redis", "跨實例暫態 fan-out", "WebSocket JSON / Redis pub-sub"),
                ("Reliable Outbox Delivery", "可靠 LINE/通知副作用與 retry", "Outbox row / Flex JSON"),
                ("Event Backbone 🔜", "跨系統事實、重播與最終一致", "Kafka / AsyncAPI JSON"),
                ("Technician OHS Adapter", "隔離品牌域與技師域", "HTTPS OHS / S2S credential"),
            ],
        ),
        (
            "g4",
            "Z4 Domain Services & Data",
            25,
            525,
            650,
            590,
            "#FFF7ED",
            "#EA580C",
            [
                ("Brand Domain Services", "Problem Card、Quote、Work Order、Dispatch、Billing 權威", "Domain command/event / SQL"),
                ("Technician Platform", "技師真相、媒合、CQRS、Settlement", "OHS / Kafka / REST-WS"),
                ("Knowledge Refinery + HITL", "Medallion、provenance、人審與發布", "Bronze/Silver / Draft / Patch"),
                ("Brand DB + pgvector", "交易、對話、Outbox、唯一事實語料", "PostgreSQL / JSONB / pgvector"),
                ("Technician DB", "技師、KYC、技能、排班、結算真相", "PostgreSQL / encrypted PII"),
                ("Platform DB / Evidence Store", "License、平台治理與證據保存", "PostgreSQL / GCS object + hash"),
            ],
        ),
        (
            "g5",
            "Z5 Applications & External Systems",
            700,
            525,
            470,
            590,
            "#F8FAFC",
            "#475569",
            [
                ("LINE / LIFF / Flex", "客戶互動、報價確認與通知交付", "Messaging API / LIFF / Flex JSON"),
                ("Brand Operations Portal", "對話、報價、派工與對帳工作台", "OIDC / REST / WebSocket"),
                ("Technician Portal", "准入、接單、現場與 statement", "OIDC / REST / WebSocket"),
                ("Platform Console", "租戶、License 與治理操作", "OIDC / Platform API"),
                ("External Shared Services", "IdP、模型供應商與 GCP runtime", "OIDC/JWKS / HTTPS / Cloud API"),
            ],
        ),
        (
            "g6",
            "Z6 Cross-Cutting Management",
            1195,
            525,
            480,
            590,
            "#FAF5FF",
            "#9333EA",
            [
                ("Control Plane", "Provisioning、License、Pack、rollout", "Versioned control command"),
                ("Configuration", "品牌、模型、SLA、通道與 feature 設定", "Config registry / secret ref"),
                ("Channel & Client Management", "LINE OA、webhook 與技師客戶端准入", "Credential / health / client state"),
                ("Security & Governance", "OIDC、RBAC/SoD、S2S、tenant、PII", "JWT/JWKS / policy / audit"),
                ("Observability & Operations", "OTel、LLM trace、SLO、alert、runbook", "OTLP / trace ID / dashboard"),
            ],
        ),
    ]

    for gid, label, x, y, w, h, fill, stroke, cards in groups:
        parent = f"{P}_{gid}"
        c.append(node(parent, label, x, y, w, h, ref_zone(fill, stroke)))
        cols = 2
        gap = 12
        card_w = (w - 30 - gap) / cols
        rows = math.ceil(len(cards) / cols)
        card_h = min(145, (h - 70 - (rows - 1) * 14) / rows)
        for i, (name, responsibility, interface) in enumerate(cards):
            col = i % cols
            row = i // cols
            cx = 15 + col * (card_w + gap)
            cy = 55 + row * (card_h + 14)
            c.append(
                node(
                    f"{parent}_c{i}",
                    f"{name}\n\n責任：{responsibility}\n\n介面：{interface}",
                    cx,
                    cy,
                    card_w,
                    card_h,
                    ref_card(stroke, "#FFFFFF"),
                    parent=parent,
                )
            )

    return ("d06_2", "06-2 L2 元件責任與介面目錄", c)


# ---------------------------------------------------------------------------
# 組裝與輸出
# ---------------------------------------------------------------------------
def wrap_mxfile(diagrams):
    parts = ['<mxfile host="app.diagrams.net" agent="claude-code" version="24.7.17">']
    for did, name, cells in diagrams:
        parts.append(f'<diagram id="{did}" name="{esc(name)}">')
        parts.append('<mxGraphModel dx="1400" dy="900" grid="1" gridSize="10" guides="1" '
                     'tooltips="1" connect="1" arrows="1" fold="1" page="1" pageScale="1" '
                     'pageWidth="1700" pageHeight="1200" math="0" shadow="0"><root>'
                     '<mxCell id="0"/><mxCell id="1" parent="0"/>')
        parts.append("".join(cells))
        parts.append('</root></mxGraphModel></diagram>')
    parts.append('</mxfile>')
    return "\n".join(parts)


# 順序 = 閱讀序：總覽與參考架構先，主要設計圖居中，能力附錄最後。
BUILDERS = [
    # ── 主 deck ──
    ("00_總覽", "00-1_mindmap", d_00_1),                    # 商業模式心智模型(開場)
    ("00_總覽", "00-2_system-context", d_00_2),             # C4 L1 Context
    ("06_參考架構", "06-1_end-to-end-reference", d_06_1),   # Solution Architecture Overview
    ("01_平台層", "01-1_deployment-layers", d_01_1),        # 部署三分層
    ("03_執行層", "03-1_container", d_03_1),                # C4 L2 部署主錨
    ("03_執行層", "03-2_agent-components", d_03_2),         # agent(LockCore)元件
    ("03_執行層", "03-3_api-components", d_03_3),           # api 元件(守衛鏈+Quote BC)
    ("04_流程圖", "04-3_sequence", d_04_3),                 # 行為:單次工單全程
    ("03_執行層", "03-4_state-machine", d_03_4),            # 行為:三具狀態機
    ("04_流程圖", "04-2_dataflow", d_04_2),                 # 跨系統資料流 DAG
    ("04_流程圖", "04-4_knowledge-loop", d_04_4),           # 知識精煉閉環
    ("05_共用核心", "05-1_kernel", d_05_1),                 # 平台共用核心
    # ── 附錄 ──
    ("01_平台層", "01-2_core-vs-pack", d_01_2),             # 附錄A(階段二)
    ("02_能力資產層", "02-1_knowledge-layers", d_02_1),     # 附錄B
    ("02_能力資產層", "02-2_ai-guardrails", d_02_2),        # 附錄C
    ("06_參考架構", "06-2_component-catalog", d_06_2),      # 附錄D：L2 元件責任卡
]


def main():
    diagrams = []
    for folder, fname, fn in BUILDERS:
        did, name, cells = fn()
        diagrams.append((did, name, cells))
        single = wrap_mxfile([(did, name, cells)])
        path = os.path.join(BASE, folder, f"{fname}.drawio")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(single)
        print(f"  ✓ {folder}/{fname}.drawio")

        if folder == "06_參考架構":
            from _render_reference_svg import render_drawio_to_svg

            svg_path = os.path.join(BASE, folder, f"{fname}.svg")
            render_drawio_to_svg(single, svg_path)
            print(f"  ✓ {folder}/{fname}.svg")

    combined = wrap_mxfile(diagrams)
    cpath = os.path.join(BASE, "smartlock-platform-architecture.drawio")
    with open(cpath, "w", encoding="utf-8") as fh:
        fh.write(combined)
    print(f"\n  ✓ smartlock-platform-architecture.drawio  ({len(diagrams)} 分頁)")


if __name__ == "__main__":
    main()
