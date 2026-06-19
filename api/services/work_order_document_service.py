"""CR-0027 客戶版電子工單 PDF service。

決議 4：客戶端只看最終電子工單（含關防/公司印章、只露最終價）；成本明細只在後台。
**安全不變式：本 service 只讀 customer-facing 欄位（customer_price / customer_final_amount），
絕不讀取或輸出 quote_line_items.unit_price（內部成本）。** 結構上隔離成本外洩。

複用 report_export_service 的 reportlab CID 中文字型範式（STSong-Light，無外部 TTF）。
關防/公司印章：以可配置 placeholder（env WORK_ORDER_SEAL_IMAGE 指章圖；未設則文字佔位）。
"""

from __future__ import annotations

import io
import logging
import os

import core.db as db_module
from core.db import _ensure_conn
from core.errors import ApiError
from services.report_export_service import _PDF_FONT_NAME, _ensure_pdf_font

logger = logging.getLogger("api.work_order_document_service")


def _dec(v) -> str:
    return "—" if v is None else f"NT$ {float(v):,.0f}"


async def _fetch_customer_view(*, tenant_id: str, work_order_id: str) -> dict:
    """只取 customer-facing 欄位（嚴禁 unit_price）。tenant 隔離走 users join。"""
    cur = await db_module._conn.execute(
        "SELECT wo.document_number, wo.brand, wo.model, wo.service_category, "
        "       wo.customer_address, wo.customer_name, wo.customer_final_amount, "
        "       wo.completion_status "
        "FROM work_orders wo "
        "JOIN problem_cards pc ON wo.problem_card_id = pc.id "
        "JOIN conversations c ON pc.conversation_id = c.id "
        "JOIN users u ON c.user_id = u.id "
        "WHERE wo.id = %s::uuid AND u.tenant_id = %s::uuid",
        (work_order_id, tenant_id),
    )
    row = await cur.fetchone()
    if not row:
        raise ApiError("NOT_FOUND", "Work order not found in this tenant", 404)
    # 只取 item_name / quantity / customer_price —— **不 SELECT unit_price**
    icur = await db_module._conn.execute(
        "SELECT item_name, quantity, customer_price "
        "FROM quote_line_items WHERE work_order_id = %s::uuid ORDER BY created_at ASC",
        (work_order_id,),
    )
    items = await icur.fetchall()
    return {
        "document_number": row[0],
        "brand": row[1],
        "model": row[2],
        "service_category": row[3],
        "customer_address": row[4],
        "customer_name": row[5],
        "customer_final_amount": row[6],
        "items": [{"name": i[0], "qty": int(i[1]), "price": i[2]} for i in items],
    }


_SERVICE_LABEL = {
    "install": "安裝", "warranty_in": "保內", "warranty_out": "保外", "repair": "維修",
}


def _render(view: dict) -> bytes:
    _ensure_pdf_font()
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        Image,
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )

    buf = io.BytesIO()
    doc_no = view.get("document_number") or "（未編號）"
    doc = SimpleDocTemplate(
        buf, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm,
        topMargin=18 * mm, bottomMargin=15 * mm, title=f"電子工單 {doc_no}",
    )
    base = getSampleStyleSheet()
    title_style = ParagraphStyle("T", parent=base["Title"], fontName=_PDF_FONT_NAME,
                                 fontSize=18, leading=22, spaceAfter=2)
    sub = ParagraphStyle("S", parent=base["Normal"], fontName=_PDF_FONT_NAME,
                         fontSize=10, textColor=colors.grey, spaceAfter=10)
    normal = ParagraphStyle("N", parent=base["Normal"], fontName=_PDF_FONT_NAME,
                            fontSize=10, leading=16)
    foot = ParagraphStyle("F", parent=base["Normal"], fontName=_PDF_FONT_NAME,
                          fontSize=8, textColor=colors.grey, spaceBefore=10)

    svc = _SERVICE_LABEL.get(view.get("service_category"), view.get("service_category") or "")
    device = f"{view.get('brand') or ''} {view.get('model') or ''}".strip() or "—"

    # CR-0046 Q-12：公司抬頭/電話（config company_profile，範例待業主替換；缺則佔位）
    company = view.get("company") or {}
    company_name = company.get("company_name") or "（公司抬頭｜待業主提供）"
    cs_phone = company.get("customer_service_phone") or "（客服電話｜待提供）"

    story: list = [
        Paragraph(company_name, title_style),
        Paragraph(f"客服專線：{cs_phone}", sub),
        Paragraph("電子工單", title_style),
        Paragraph(f"工單編號：{doc_no}", sub),
        Paragraph(f"客戶：{view.get('customer_name') or '—'}", normal),
        Paragraph(f"服務地址：{view.get('customer_address') or '—'}", normal),
        Paragraph(f"服務類別：{svc or '—'}　設備：{device}", normal),
        Spacer(1, 6 * mm),
    ]

    # 品項表（只露 customer_price，無 unit_price）
    rows = [["項目", "數量", "金額"]]
    for it in view.get("items", []):
        rows.append([str(it["name"]), str(it["qty"]), _dec(it["price"])])
    if len(rows) == 1:
        rows.append(["（服務項目）", "1", _dec(view.get("customer_final_amount"))])
    table = Table(rows, repeatRows=1, hAlign="LEFT", colWidths=[100 * mm, 25 * mm, 45 * mm])
    table.setStyle(TableStyle([
        ("FONT", (0, 0), (-1, -1), _PDF_FONT_NAME, 10),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1E293B")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#CBD5E1")),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(table)
    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph(
        f"<b>應付總額：{_dec(view.get('customer_final_amount'))}</b>", normal))

    # 關防 / 公司印章（placeholder 可配置；待業主提供章圖）
    story.append(Spacer(1, 10 * mm))
    seal_path = os.getenv("WORK_ORDER_SEAL_IMAGE")
    if seal_path and os.path.exists(seal_path):
        try:
            story.append(Image(seal_path, width=30 * mm, height=30 * mm))
        except Exception:  # noqa: BLE001
            story.append(Paragraph("（公司關防）", normal))
    else:
        story.append(Paragraph("（公司關防｜待用印）", normal))

    # CR-0046 Q-12：保固/取消費/追加價條款（config company_profile，範例待業主替換；缺則佔位）
    _clauses = [
        ("保固說明", company.get("warranty_text")),
        ("取消費規則", company.get("cancellation_clause")),
        ("追加價處理方式", company.get("surcharge_clause")),
    ]
    if any(body for _t, body in _clauses):
        story.append(Spacer(1, 8 * mm))
        story.append(Paragraph("<b>服務條款</b>", normal))
        story.append(Spacer(1, 2 * mm))
        for title, body in _clauses:
            if body:
                story.append(Paragraph(f"<b>{title}</b>", foot))
                story.append(Paragraph(f"　　{body}", foot))
                story.append(Spacer(1, 1 * mm))

    # 施工免責與合規（CR-0033，藍圖模組 4 三段佔位文本，待法務 sign-off）
    # 法律文本「永遠顯示」（以 consent_service.CONSENT_TEXTS 為底），同意狀態由 view 疊加；
    # 即使取不到同意紀錄，三段聲明仍出（全 ☐），不因 fetch 失敗而整段消失。
    from services.consent_service import CONSENT_TEXTS

    accepted_map = {c.get("consent_type"): c.get("accepted") for c in (view.get("consents") or [])}
    story.append(Spacer(1, 8 * mm))
    story.append(Paragraph("<b>施工免責與合規聲明</b>", normal))
    story.append(Spacer(1, 2 * mm))
    for c in CONSENT_TEXTS:
        mark = "☑" if accepted_map.get(c["consent_type"]) else "☐"
        story.append(Paragraph(f"{mark} <b>{c['title']}</b>", foot))
        story.append(Paragraph(f"　　{c['body']}", foot))
        story.append(Spacer(1, 1 * mm))

    story.append(Paragraph(
        "本電子工單僅顯示最終金額；成本明細與內部估價不對客戶揭露。", foot))
    doc.build(story)
    return buf.getvalue()


async def render_document(*, tenant_id: str, work_order_id: str) -> bytes:
    """產生客戶版電子工單 PDF bytes（只露最終價 + 關防 + 免責段，無成本明細）。"""
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)
    view = await _fetch_customer_view(tenant_id=tenant_id, work_order_id=work_order_id)
    # CR-0046 Q-12：公司抬頭/電話 + 保固/取消費/追加價條款（M18 config company_profile，範例待業主替換）。
    # best-effort：取不到不阻斷 PDF（_render 用 fallback 佔位）。
    try:
        from services import config_m18_service
        company = await config_m18_service.read_global_value(namespace="company_profile")
        if isinstance(company, dict):
            view = {**view, "company": company}
    except Exception as exc:  # noqa: BLE001
        logger.warning("company_profile fetch failed for wo=%s: %s", work_order_id, exc)
    # 免責段（CR-0033）：best-effort 取三段同意狀態，失敗不阻斷 PDF（_render 仍出三段法律文本，全 ☐）
    try:
        from services import consent_service
        consent_data = await consent_service.get_consents(
            work_order_id=work_order_id, tenant_id=tenant_id)
        # 白名單欄位（防未來 consent_service 回傳意外欄位混入客戶 PDF）
        view = {**view, "consents": [
            {"consent_type": c["consent_type"], "accepted": c["accepted"]}
            for c in consent_data["consents"]
        ]}
    except Exception as exc:  # noqa: BLE001 — 免責段同意狀態取不到仍出法律文本（全 ☐）
        logger.warning("disclaimer status fetch failed for wo=%s (texts still rendered): %s",
                       work_order_id, exc)
    return _render(view)
