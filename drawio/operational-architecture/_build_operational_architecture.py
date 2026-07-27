#!/usr/bin/env python3
"""Build the Smart Lock five-view operational architecture package.

The diagrams deliberately separate code-confirmed behaviour from deployment
evidence, target architecture and open decisions.  They are generated from a
single source so the individual editable files and the combined deck cannot
drift apart.
"""

from __future__ import annotations

import html
from pathlib import Path
import xml.etree.ElementTree as ET


BASE = Path(__file__).resolve().parent
SYSTEM_NAME = "Smart Lock AI 客服與派工 SaaS 平台"
PRODUCT_NAME = "Smart Lock AI 客服與派工 SaaS"

PALETTE = {
    "primary": ("#DAE8FC", "#6C8EBF"),
    "hub": ("#DAE8FC", "#6C8EBF"),
    "red": ("#F8CECC", "#B85450"),
    "blue": ("#DAE8FC", "#6C8EBF"),
    "green": ("#D5E8D4", "#82B366"),
    "teal": ("#B0E3E6", "#0E8088"),
    "orange": ("#FFE6CC", "#D79B00"),
    "yellow": ("#FFF2CC", "#D6B656"),
    "purple": ("#E1D5E7", "#9673A6"),
    "external": ("#F5F5F5", "#666666"),
    "data": ("#D5E8D4", "#82B366"),
    "decision": ("#FFF2CC", "#D6B656"),
    "manual": ("#FFE6CC", "#D79B00"),
    "white": ("#FFFFFF", "#999999"),
}

EDGE = {
    "runtime": ("#333333", "2.5", False, "classic"),
    "data": ("#555555", "1.8", False, "classic"),
    "control": ("#6C8EBF", "1.8", True, "classic"),
    "support": ("#999999", "1.5", True, "open"),
    "feedback": ("#6C8EBF", "1.8", True, "classic"),
}


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


class Page:
    def __init__(self, page_id: str, name: str, subtitle: str) -> None:
        self.page_id = page_id
        self.name = name
        self.root = ET.Element("root")
        ET.SubElement(self.root, "mxCell", id="0")
        ET.SubElement(self.root, "mxCell", id="1", parent="0")
        self._seq = 0
        self.text("title", name, 40, 24, 1840, 42, size=24, bold=True, align="left")
        self.text(
            "subtitle", subtitle, 40, 67, 1840, 32,
            size=11, color="#5F6368", align="left",
        )

    def _id(self, prefix: str) -> str:
        self._seq += 1
        return f"{self.page_id}_{prefix}_{self._seq}"

    def text(
        self,
        key: str,
        label: str,
        x: int,
        y: int,
        w: int,
        h: int,
        *,
        size: int = 12,
        bold: bool = False,
        color: str = "#263238",
        align: str = "center",
    ) -> str:
        cell_id = self._id(key)
        style = (
            "text;html=1;strokeColor=none;fillColor=none;whiteSpace=wrap;"
            f"fontSize={size};fontStyle={1 if bold else 0};fontColor={color};"
            f"align={align};verticalAlign=middle;"
        )
        self._vertex(cell_id, label, x, y, w, h, style)
        return cell_id

    def frame(self, key: str, label: str, x: int, y: int, w: int, h: int) -> str:
        cell_id = self._id(key)
        style = (
            "rounded=1;whiteSpace=wrap;html=1;container=1;collapsible=0;"
            "fillColor=#FFFFFF;fillOpacity=35;strokeColor=#A6A6A6;dashed=1;"
            "verticalAlign=top;align=left;spacingTop=8;spacingLeft=10;"
            "fontSize=13;fontStyle=1;"
        )
        self._vertex(cell_id, label, x, y, w, h, style)
        return cell_id

    def node(
        self,
        key: str,
        label: str,
        x: int,
        y: int,
        w: int = 240,
        h: int = 76,
        *,
        color: str = "primary",
        rounded: bool = True,
        dashed: bool = False,
        bold: bool = False,
    ) -> str:
        cell_id = self._id(key)
        fill, stroke = PALETTE[color]
        style = (
            f"rounded={1 if rounded else 0};whiteSpace=wrap;html=1;"
            f"fillColor={fill};strokeColor={stroke};strokeWidth=1.7;"
            f"fontSize=12;fontStyle={1 if bold else 0};spacing=6;"
            + ("dashed=1;dashPattern=6 4;" if dashed else "")
        )
        self._vertex(cell_id, label, x, y, w, h, style)
        return cell_id

    def store(
        self, key: str, label: str, x: int, y: int, w: int = 230, h: int = 86
    ) -> str:
        cell_id = self._id(key)
        style = (
            "shape=cylinder3;whiteSpace=wrap;html=1;boundedLbl=1;"
            "fillColor=#E1D5E7;strokeColor=#9673A6;strokeWidth=1.7;"
            "fontSize=12;spacing=6;"
        )
        self._vertex(cell_id, label, x, y, w, h, style)
        return cell_id

    def decision(self, key: str, label: str, x: int, y: int, size: int = 90) -> str:
        cell_id = self._id(key)
        style = (
            "rhombus;whiteSpace=wrap;html=1;fillColor=#FFF2CC;"
            "strokeColor=#D6B656;strokeWidth=1.8;fontSize=11;"
        )
        self._vertex(cell_id, label, x, y, size, size, style)
        return cell_id

    def edge(
        self,
        key: str,
        source: str,
        target: str,
        label: str,
        *,
        kind: str = "runtime",
        dashed: bool = False,
    ) -> str:
        cell_id = self._id(key)
        stroke, width, use_dash, arrow = EDGE[kind]
        style = (
            "edgeStyle=orthogonalEdgeStyle;rounded=1;orthogonalLoop=1;"
            f"jettySize=auto;html=1;endArrow={arrow};"
            f"endFill={0 if arrow == 'open' else 1};"
            f"strokeColor={stroke};strokeWidth={width};fontSize=10;"
            "labelBackgroundColor=#FFFFFF;jumpStyle=arc;jumpSize=8;"
            + ("dashed=1;dashPattern=1 4;" if arrow == "open" else "")
            + ("dashed=1;dashPattern=8 5;" if use_dash and arrow != "open" else "")
            + ("dashed=1;dashPattern=7 4;" if dashed else "")
        )
        cell = ET.SubElement(
            self.root,
            "mxCell",
            id=cell_id,
            value=esc(label),
            style=style,
            edge="1",
            parent="1",
            source=source,
            target=target,
        )
        ET.SubElement(cell, "mxGeometry", relative="1", **{"as": "geometry"})
        return cell_id

    def _vertex(
        self, cell_id: str, label: str, x: int, y: int, w: int, h: int, style: str
    ) -> None:
        cell = ET.SubElement(
            self.root,
            "mxCell",
            id=cell_id,
            value=esc(label),
            style=style,
            vertex="1",
            parent="1",
        )
        ET.SubElement(
            cell,
            "mxGeometry",
            x=str(x),
            y=str(y),
            width=str(w),
            height=str(h),
            **{"as": "geometry"},
        )

    def graph_model(self) -> ET.Element:
        model = ET.Element(
            "mxGraphModel",
            dx="1422",
            dy="794",
            grid="1",
            gridSize="10",
            guides="1",
            tooltips="1",
            connect="1",
            arrows="1",
            fold="1",
            page="1",
            pageScale="1",
            pageWidth="1920",
            pageHeight="1080",
            math="0",
            shadow="0",
        )
        model.append(self.root)
        return model


def legend(page: Page) -> None:
    page.text("legend_title", "Relationship semantics", 40, 1010, 170, 28, bold=True)
    labels = (
        ("runtime", "P0 / primary path"),
        ("data", "Normal interaction"),
        ("control", "Async / return"),
        ("support", "Cross-cut support"),
        ("feedback", "Observation / feedback"),
    )
    x = 230
    for kind, label in labels:
        left = page.node(f"legend_{kind}_a", "", x, 1017, 8, 8, color="white")
        right = page.node(f"legend_{kind}_b", "", x + 90, 1017, 8, 8, color="white")
        page.edge(f"legend_{kind}", left, right, "", kind=kind)
        page.text(f"legend_{kind}_text", label, x + 104, 1004, 155, 32, size=10)
        x += 310


def system_context() -> Page:
    p = Page(
        "system_context",
        "00 | Smart Lock System Context — C4 Level 1",
        "產品邊界與對外責任｜依 12_SAD / 15_SDS 與 2026-07-27 codebase 對帳；不展開內部 container 或部署。",
    )
    p.frame("scope", f"System of Interest | {SYSTEM_NAME}", 570, 165, 760, 690)
    customer = p.node("customer", "終端客戶\n（LINE 使用者）", 70, 180, color="external")
    operator = p.node("operator", "品牌營運人員\n（客服／派工／報價）", 70, 410, color="external")
    technician = p.node("technician", "簽約技師／鎖匠\n（跨品牌共享）", 70, 640, color="external")
    system = p.node(
        "system", f"{PRODUCT_NAME}\nAI 協助客服、人工核可報價、派工與營運追溯\nAI 不擁有 final quote／工單／派工／金流真相",
        770, 375, 360, 150, color="hub", bold=True,
    )
    line = p.node("line", "LINE Platform\nWebhook／Reply・Push／LIFF・Flex", 1530, 155, color="external")
    model = p.node("model", "LLM 供應商\n模型推理（HTTPS）", 1530, 385, color="external")
    identity = p.node("identity", "Casdoor 身分平台\nPARTIAL｜OD-004 claim 模型待定", 1530, 615, color="external", dashed=True)
    p.edge("customer_use", customer, system, "報修、報價確認、同意與評分")
    p.edge("operator_use", operator, system, "接管、核可、派工、對帳", kind="control")
    p.edge("technician_use", technician, system, "接單、到場、存證、現場修正", kind="data")
    p.edge("line_rel", system, line, "X-Line-Signature webhook／Reply・Push", kind="runtime")
    p.edge("model_rel", system, model, "模型請求／回覆（供應商無關）", kind="data")
    p.edge("identity_rel", system, identity, "OIDC／JWKS（正式 org／claim 待定）", kind="control")
    p.text(
        "question",
        "責任邊界：平台擁有品牌營運流程與資料真相；LINE、模型供應商、IdP 為外部依賴。技師權威資料在跨租戶技師平台，非品牌庫。",
        270, 900, 1400, 42, size=13, bold=True, color="#174EA6",
    )
    legend(p)
    return p


def operational_processing() -> Page:
    p = Page(
        "operational_processing",
        "01 | Smart Lock Operational Processing — UML Activity + Object Flow",
        "穩定產品加工主幹｜OP ID 與 Process Catalog、Traceability Matrix 對應；不是 UI click sequence。",
    )
    lanes = (
        ("source_lane", "A | 客戶與通道", 40),
        ("ai_lane", "B | AI 協助與分流", 340),
        ("ops_lane", "C | 人工營運與品牌權威", 640),
        ("field_lane", "D | 派工與現場服務", 940),
        ("learn_lane", "E | 證據與知識回饋", 1240),
    )
    for key, label, x in lanes:
        p.frame(key, label, x, 135, 285, 760)
    source = p.node("source", "客戶訊息／照片／\nLIFF postback", 65, 225, 230, 62, color="external")
    intake = p.node("intake", "OP-10 · 接收並驗證互動", 65, 380, 230, 74, color="red", bold=True)
    assist = p.node("assist", "OP-20 · 協助診斷與分流", 365, 290, 230, 74, color="red", bold=True)
    context = p.node("context", "已驗簽事件＋\n租戶／使用者上下文", 365, 520, 230, 70, color="orange")
    human = p.node("human", "OP-30 · 人工確認與處理", 665, 290, 230, 74, color="blue", bold=True)
    gate = p.decision("gate", "是否達成\n人工核可／\n服務 gate？", 725, 505, 110)
    dispatch = p.node("dispatch", "OP-40 · 建立並執行派工", 965, 290, 230, 74, color="teal", bold=True)
    close = p.node("close", "OP-50 · 確認完成與結算", 965, 545, 230, 74, color="blue", bold=True)
    outcome = p.node("outcome", "已交付回覆／\n已確認報價／完成服務", 965, 720, 230, 68, color="green")
    evidence = p.node("evidence", "OP-60 · 保存營運證據", 1265, 290, 230, 74, color="purple", bold=True)
    learn = p.node("learn", "OP-70 · 審核並回饋知識", 1265, 570, 230, 74, color="orange", bold=True)
    p.edge("source_intake", source, intake, "I-10 已簽署 LINE 事件", kind="runtime")
    p.edge("intake_context", intake, context, "I-20 已驗簽／去重輸入", kind="data")
    p.edge("context_assist", context, assist, "記憶、Skill、知識與當次訊息", kind="data")
    p.edge("assist_human", assist, human, "AI 回覆或 transfer_to_human 草稿", kind="data")
    p.edge("human_gate", human, gate, "經核可的報價／問題卡／命令", kind="data")
    p.edge("gate_dispatch", gate, dispatch, "客戶確認或急件 carve-out", kind="runtime")
    p.edge("dispatch_close", dispatch, close, "到場、存證、現場修正", kind="data")
    p.edge("close_outcome", close, outcome, "服務結果／同意／結算", kind="data")
    p.edge("human_evidence", human, evidence, "對話、決策、審計", kind="support")
    p.edge("close_evidence", close, evidence, "工單、事件、存證", kind="support")
    p.edge("evidence_learn", evidence, learn, "可追溯案例／素材", kind="feedback")
    p.edge("learn_assist", learn, assist, "核可 Skill／事實回饋（PARTIAL）", kind="feedback")
    p.text(
        "rule",
        "紅線：OP-20 只協助回覆、查知識與轉真人；最終報價、工單與派工必經 OP-30／OP-40。知識回饋僅限人工核可後發布。",
        220, 925, 1480, 42, size=13, bold=True, color="#174EA6",
    )
    legend(p)
    return p


def container_architecture() -> Page:
    p = Page(
        "container_architecture",
        "02 | Smart Lock Container Architecture — C4 Level 2",
        "可執行／保存責任單位｜CURRENT 是 code-confirmed；PARTIAL／TARGET 不可解讀為 production 已部署。",
    )
    user = p.node("user", "客戶／品牌營運／\n技師／平台管理員", 55, 270, color="external")
    line = p.node("line", "LINE Platform", 55, 610, color="external")
    p.frame("system", f"System of Interest | {SYSTEM_NAME}", 390, 135, 1120, 760)
    agent = p.node("agent", "C-10 · Agent／LockCore\naiohttp｜LINE Turn、Skill、Memory、Tools\nCURRENT", 435, 230, 285, 112, color="red", bold=True)
    web = p.node("web", "C-20 · Web Portals\nNext.js｜brand／tech／platform\nPARTIAL（四站）", 435, 465, 285, 112, color="blue", bold=True)
    api = p.node("api", "C-30 · API Control Plane\nFastAPI｜API_SURFACE、RBAC、領域服務\nCURRENT + deployment-conditional", 805, 230, 300, 112, color="blue", bold=True)
    tech = p.node("tech", "C-40 · Technician Platform\ntech surface + tech portal｜技師權威／投影\nPARTIAL；OHS 邊界 OD-001／OD-003", 805, 465, 300, 112, color="teal", bold=True)
    refinery = p.node("refinery", "C-50 · Knowledge Refinery\nHITL／publish｜License 附加\nPARTIAL；intake OD-002", 805, 680, 300, 100, color="teal", dashed=True)
    brand_store = p.store("brand_store", "C-60 · Brand DB + pgvector\n品牌交易、對話、outbox、唯一事實語料\nCURRENT（環境套用待取證）", 1200, 220, 245, 125)
    tech_store = p.store("tech_store", "C-61 · Technician DB\n技師身分／技能／排班權威\nPARTIAL", 1200, 450, 245, 115)
    platform_store = p.store("platform_store", "C-62 · Platform DB\n治理／License（PARTIAL）", 1200, 670, 245, 100)
    model = p.node("model", "LLM 供應商\nLiteLLM 路由", 1615, 245, color="external")
    identity = p.node("identity", "Casdoor IdP\nPARTIAL／OD-004", 1615, 470, color="external", dashed=True)
    p.edge("user_web", user, web, "Browser／OIDC portal interaction")
    p.edge("line_agent", line, agent, "Webhook／Reply・Push", kind="runtime")
    p.edge("agent_api", agent, api, "/internal/* X-Internal-Token", kind="runtime")
    p.edge("agent_brand", agent, brand_store, "Memory／RAG（tenant scoped）", kind="support")
    p.edge("agent_model", agent, model, "模型 request／response", kind="data")
    p.edge("web_api", web, api, "REST／WebSocket", kind="runtime")
    p.edge("api_brand", api, brand_store, "品牌領域交易／outbox", kind="support")
    p.edge("api_tech", api, tech, "interim direct route；目標 OHS（OD-001）", kind="control")
    p.edge("tech_techstore", tech, tech_store, "技師 authority／投影", kind="support")
    p.edge("api_identity", api, identity, "OIDC／portal claim guard", kind="control")
    p.edge("refinery_brand", refinery, brand_store, "受控 intake／核可 publish（OD-002）", kind="feedback")
    p.edge("refinery_platform", refinery, platform_store, "License／governance（PARTIAL）", kind="control")
    p.text(
        "rule",
        "資料隔離：品牌／技師／平台三庫各自擁有真相；品牌不應直連技師庫。Redis、Kafka、SigNoz 為可選基礎設施，未列為已驗證 container instance。",
        180, 925, 1560, 42, size=13, bold=True, color="#174EA6",
    )
    legend(p)
    return p


def information_flow() -> Page:
    p = Page(
        "information_flow",
        "03 | Smart Lock Information Flow — DFD Level 1",
        "資料產品、方向與保存責任｜同步／非同步、CURRENT／PARTIAL／TARGET 的語意均在 edge label 明示。",
    )
    source = p.node("source", "E-10 | LINE 使用者／\nLIFF postback", 50, 220, color="external", rounded=False)
    operator = p.node("operator", "E-20 | 品牌營運／\n技師工作台", 50, 650, color="external", rounded=False)
    intake = p.node("intake", "P-10 | 通道驗簽、去重與解碼\nline_gateway", 390, 220, 270, 86, color="red", bold=True)
    runtime = p.node("runtime", "P-20 | 對話 Turn 與治理\nLockCore", 770, 220, 270, 86, color="red", bold=True)
    domain = p.node("domain", "P-30 | 品牌領域命令與 guard\nAPI control plane", 770, 590, 270, 86, color="blue", bold=True)
    deliver = p.node("deliver", "P-40 | 回覆、投影與通知交付\nLINE／Portal／WS", 1160, 405, 270, 86, color="blue", bold=True)
    downstream = p.node("downstream", "E-30 | 客戶／營運人員／\n技師", 1600, 405, color="external", rounded=False)
    memory = p.store("memory", "D-10 | Agent Memory\ntenant_id + user_id\nCURRENT", 390, 645)
    brand = p.store("brand", "D-20 | Brand DB + pgvector\n交易／對話／outbox／知識\nCURRENT（環境待取證）", 1160, 700)
    tech = p.store("tech", "D-30 | Technician DB\n身份／技能／排班\nPARTIAL", 770, 835)
    refinery = p.node("refinery", "P-50 | HITL 知識精煉\nPARTIAL／OD-002", 1160, 830, 270, 76, color="teal", dashed=True)
    p.edge("source_intake", source, intake, "I-10 | 已簽署 LINE webhook JSON（sync）", kind="runtime")
    p.edge("intake_runtime", intake, runtime, "I-20 | 已驗簽／去重 Normalized Turn（sync）", kind="data")
    p.edge("memory_runtime", memory, runtime, "I-21 | tenant + user scoped customer facts（sync）", kind="support")
    p.edge("runtime_domain", runtime, domain, "I-30 | escalation／conversation ingest（internal sync）", kind="data")
    p.edge("operator_domain", operator, domain, "I-31 | human command／approval／field evidence（sync）", kind="control")
    p.edge("domain_deliver", domain, deliver, "I-40 | authorized state／outbox notification（sync／worker）", kind="data")
    p.edge("runtime_deliver", runtime, deliver, "I-41 | guarded AI reply／Flex（sync）", kind="runtime")
    p.edge("deliver_downstream", deliver, downstream, "I-50 | reply／portal view／notification", kind="data")
    p.edge("domain_brand", domain, brand, "I-60 | brand transaction、audit、outbox（SQL）", kind="support")
    p.edge("domain_tech", domain, tech, "I-61 | CURRENT interim direct access；TARGET OHS（OD-001）", kind="control")
    p.edge("brand_refinery", brand, refinery, "I-70 | diagnostic／knowledge input（PARTIAL；OD-002）", kind="feedback")
    p.edge("refinery_brand", refinery, brand, "I-71 | approved fact／skill revision（HITL only）", kind="feedback")
    p.text("note", "I-80 Redis WS fan-out 與 I-81 Kafka domain events：程式為 opt-in，production／SIT 尚未取證；不在本圖當成正常主路徑。", 290, 940, 1380, 32, size=12, bold=True, color="#9C6500")
    p.text(
        "rule",
        "Data ownership：Agent Memory 不等同原始 session；Brand DB 保有品牌業務真相；Technician DB 是技師權威。Refinery 只能發布經 HITL 核可的輸出。",
        220, 985, 1480, 32, size=12, bold=True, color="#174EA6",
    )
    legend(p)
    return p


def deployment_runtime() -> Page:
    p = Page(
        "deployment_runtime",
        "04 | Smart Lock Deployment Runtime — C4 Deployment",
        "僅呈現 repository 可確認的部署形態；production host、revision、secret、HA 與外部服務狀態均未由此工作區取證。",
    )
    p.frame("client_node", "N-10 | 外部信任區（CURRENT interface）", 40, 150, 300, 700)
    browser = p.node("browser", "Browser／LINE Client\nHTTPS／WSS／Messaging API", 75, 330, 230, 90, color="external", bold=True)
    p.frame("repo_runtime", "N-20 | Repository-defined runtime（CURRENT source/config；實際環境未驗）", 380, 150, 420, 700)
    agent = p.node("agent", "C-10 instance\nagent aiohttp／LockCore\nLINE callback", 425, 245, 330, 90, color="red", bold=True)
    web = p.node("web", "C-20 instance\nbrand／tech／platform Next.js portals", 425, 500, 330, 90, color="blue", bold=True)
    p.frame("api_runtime", "N-30 | API deployment shape（CURRENT code；revision／scale 未驗）", 840, 150, 420, 700)
    api = p.node("api", "C-30 instance\nFastAPI API_SURFACE=dispatch\nDB_URI_STRICT required in formal env", 885, 225, 330, 105, color="blue", bold=True)
    tech_api = p.node("tech_api", "C-40 instance\nFastAPI API_SURFACE=tech\n共用 codebase；獨立 stack config", 885, 490, 330, 105, color="teal", bold=True)
    p.frame("dependencies", "N-40 | 依賴服務／資料面（連線設定可確認；實際 placement 未驗）", 1300, 150, 535, 700)
    data = p.store("data", "C-60/C-61/C-62\n品牌／技師／平台 PostgreSQL\n三庫 URI／migration 需 SIT 取證", 1340, 230, 220, 125)
    redis = p.node("redis", "Redis WS bridge\nPARTIAL；REDIS_URL 未取證", 1590, 230, 205, 80, color="purple", dashed=True)
    kafka = p.node("kafka", "Kafka／Redpanda\nPARTIAL；KAFKA_BOOTSTRAP 未取證", 1590, 450, 205, 80, color="purple", dashed=True)
    refinery = p.node("refinery", "Knowledge Refinery\nPARTIAL；schedule／OIDC／OTel 未取證", 1340, 490, 220, 90, color="teal", dashed=True)
    idp = p.node("idp", "Casdoor／SigNoz\nPARTIAL；HA／collector 未取證", 1340, 670, 220, 75, color="green", dashed=True)
    p.edge("browser_agent", browser, agent, "LINE Messaging API／HTTPS")
    p.edge("browser_web", browser, web, "HTTPS／WSS")
    p.edge("agent_api", agent, api, "internal HTTPS／X-Internal-Token", kind="runtime")
    p.edge("web_api", web, api, "REST／WS", kind="runtime")
    p.edge("api_tech", api, tech_api, "CURRENT interim route；OHS target OD-001", kind="control")
    p.edge("api_data", api, data, "PostgreSQL")
    p.edge("tech_data", tech_api, data, "TECH_POSTGRES_URI")
    p.edge("api_redis", api, redis, "opt-in pub/sub", kind="feedback")
    p.edge("api_kafka", api, kafka, "opt-in producer／consumer", kind="feedback")
    p.edge("refinery_data", refinery, data, "tenant-scoped intake／publish", kind="support")
    p.edge("api_idp", api, idp, "OIDC／OTLP（conditional）", kind="control")
    p.text(
        "rule",
        "N-20～N-40 不是 production topology 宣告：本工作區無 Cloud Run／Cloud SQL／Kafka／Redis／Casdoor／SigNoz 的存取證據。多實例前須完成 Redis、Kafka 與復原 SIT。",
        170, 925, 1600, 42, size=13, bold=True, color="#9C6500",
    )
    legend(p)
    return p


def pages() -> list[Page]:
    return [
        system_context(),
        operational_processing(),
        container_architecture(),
        information_flow(),
        deployment_runtime(),
    ]


def write_mxfile(path: Path, selected: list[Page]) -> None:
    root = ET.Element(
        "mxfile",
        {
            "host": "app.diagrams.net",
            "modified": "2026-07-27T00:00:00.000Z",
            "agent": "Smart Lock Operational Architecture builder",
            "version": "24.7.17",
            "type": "device",
        },
    )
    for page in selected:
        diagram = ET.SubElement(
            root,
            "diagram",
            id=page.page_id,
            name=page.name.split("|", 1)[0].strip(),
            compressed="false",
        )
        diagram.append(page.graph_model())
    ET.indent(root, space="  ")
    ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)
    ET.parse(path)


def main() -> None:
    generated = pages()
    names = (
        "00_system-context.drawio",
        "01_operational-processing.drawio",
        "02_container-architecture.drawio",
        "03_information-flow.drawio",
        "04_deployment-runtime.drawio",
    )
    for page, name in zip(generated, names, strict=True):
        write_mxfile(BASE / name, [page])
    combined = BASE / "smartlock-operational-architecture.drawio"
    write_mxfile(combined, generated)
    vertices = sum(
        1 for page in generated for cell in page.root.findall("mxCell")
        if cell.get("vertex") == "1"
    )
    edges = sum(
        1 for page in generated for cell in page.root.findall("mxCell")
        if cell.get("edge") == "1"
    )
    print(
        f"generated {combined.name}: pages={len(generated)} "
        f"vertices={vertices} edges={edges}"
    )


if __name__ == "__main__":
    main()
