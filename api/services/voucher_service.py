"""Voucher 業務邏輯。

範圍：listVouchers（cursor + limit + posting_date 區間）+ exportVoucher（PDF）。

DB↔OpenAPI 欄位對齊：
  - amount (NUMERIC) → string with pattern '^-?\\d+(\\.\\d{1,2})?$'：用 f"{x:.2f}"
  - currency 必傳 TWD（DB default）
  - related_entity_type 為 NULL 時不傳

租戶隔離：vouchers 自帶 tenant_id 欄位（與 manuals 同 pattern）。

PDF 渲染：使用 reportlab + Adobe CID 內建字型 STSong-Light（中文支援，無需外部字型檔）。
"""

from __future__ import annotations

import io
import logging
from datetime import date

import core.db as db_module
from core.db import _ensure_conn
from core.errors import ApiError
from core.pagination import decode_cursor, encode_cursor

logger = logging.getLogger("api.voucher_service")

_PDF_FONT_REGISTERED = False


def _ensure_pdf_font() -> None:
    """延遲註冊 CID 字型 — 避免 import 時 reportlab 未安裝就失敗。"""
    global _PDF_FONT_REGISTERED
    if _PDF_FONT_REGISTERED:
        return
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont

    pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
    _PDF_FONT_REGISTERED = True


_ENTITY_LABEL = {
    "reconciliation": "對帳",
    "settlement": "結算",
    "refund": "退款",
    "invoice": "發票",
}


_SELECT_COLUMNS = (
    "id, voucher_number, related_entity_type, related_entity_id, "
    "debit_account, credit_account, amount, currency, "
    "posting_date, memo, created_at"
)


def _row_to_dict(row: tuple) -> dict:
    return {
        "id": str(row[0]),
        "voucher_number": row[1],
        "related_entity_type": row[2],
        "related_entity_id": str(row[3]) if row[3] else None,
        "debit_account": row[4],
        "credit_account": row[5],
        "amount": f"{float(row[6]):.2f}",
        "currency": row[7] or "TWD",
        "posting_date": row[8].isoformat() if row[8] else None,
        "memo": row[9],
        "created_at": row[10].isoformat() if row[10] else None,
    }


async def list_vouchers(
    *,
    tenant_id: str,
    cursor: str | None,
    limit: int,
    posting_date_start: date | None,
    posting_date_end: date | None,
) -> dict:
    if (
        posting_date_start is not None
        and posting_date_end is not None
        and posting_date_start > posting_date_end
    ):
        raise ApiError(
            "VALIDATION_ERROR",
            "posting_date_start must be <= posting_date_end",
            422,
        )

    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    where = ["tenant_id = %s::uuid"]
    args: list = [tenant_id]

    if posting_date_start is not None:
        where.append("posting_date >= %s")
        args.append(posting_date_start)
    if posting_date_end is not None:
        where.append("posting_date <= %s")
        args.append(posting_date_end)

    cur_data = decode_cursor(cursor)
    if cur_data and "ts" in cur_data and "id" in cur_data:
        where.append("(posting_date, id) < (%s, %s::uuid)")
        args.extend([cur_data["ts"], cur_data["id"]])

    sql = (
        f"SELECT {_SELECT_COLUMNS} "
        f"FROM vouchers "
        f"WHERE {' AND '.join(where)} "
        f"ORDER BY posting_date DESC, id DESC "
        f"LIMIT %s"
    )
    args.append(limit + 1)
    cur = await db_module._conn.execute(sql, args)
    rows = await cur.fetchall()

    has_more = len(rows) > limit
    rows = rows[:limit]
    items = [_row_to_dict(r) for r in rows]

    next_cursor = None
    if has_more and rows:
        last = rows[-1]
        next_cursor = encode_cursor(
            {"ts": last[8].isoformat(), "id": str(last[0])}
        )

    return {"items": items, "next_cursor": next_cursor, "has_more": has_more}


async def get_voucher(*, tenant_id: str, voucher_id: str) -> dict:
    """取單筆傳票（租戶隔離）。找不到 → 404 NOT_FOUND。"""
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    sql = (
        f"SELECT {_SELECT_COLUMNS} "
        f"FROM vouchers "
        f"WHERE id = %s::uuid AND tenant_id = %s::uuid"
    )
    cur = await db_module._conn.execute(sql, [voucher_id, tenant_id])
    row = await cur.fetchone()
    if not row:
        raise ApiError("NOT_FOUND", "Voucher not found", 404)
    return _row_to_dict(row)


def render_voucher_pdf(voucher: dict) -> bytes:
    """渲染單筆傳票為 A4 PDF（中文使用 STSong-Light CID 內建字型）。"""
    _ensure_pdf_font()

    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas

    buf = io.BytesIO()
    width, height = A4
    c = canvas.Canvas(buf, pagesize=A4)
    font = "STSong-Light"

    margin_x = 20 * mm
    cursor_y = height - 25 * mm

    c.setFont(font, 20)
    c.drawString(margin_x, cursor_y, "會計傳票 Accounting Voucher")
    cursor_y -= 12 * mm
    c.setLineWidth(0.6)
    c.line(margin_x, cursor_y, width - margin_x, cursor_y)
    cursor_y -= 8 * mm

    entity_type = voucher.get("related_entity_type")
    entity_label = _ENTITY_LABEL.get(entity_type, "—") if entity_type else "—"

    fields: list[tuple[str, str]] = [
        ("傳票編號 Voucher No.", voucher.get("voucher_number") or "—"),
        ("入帳日 Posting Date", voucher.get("posting_date") or "—"),
        ("類型 Type", entity_label),
        ("關聯單號 Related ID", voucher.get("related_entity_id") or "—"),
        ("借方科目 Debit", voucher.get("debit_account") or "—"),
        ("貸方科目 Credit", voucher.get("credit_account") or "—"),
        (
            "金額 Amount",
            f"{voucher.get('currency') or 'TWD'} {voucher.get('amount') or '0.00'}",
        ),
    ]

    label_x = margin_x
    value_x = margin_x + 55 * mm
    c.setFont(font, 11)
    for label, value in fields:
        c.drawString(label_x, cursor_y, label)
        c.drawString(value_x, cursor_y, str(value))
        cursor_y -= 8 * mm

    cursor_y -= 4 * mm
    c.setFont(font, 11)
    c.drawString(margin_x, cursor_y, "摘要 Memo")
    cursor_y -= 7 * mm
    memo = voucher.get("memo") or "—"
    text = c.beginText(margin_x, cursor_y)
    text.setFont(font, 10)
    max_chars = 48
    for line in memo.splitlines() or [memo]:
        for i in range(0, len(line), max_chars):
            text.textLine(line[i : i + max_chars])
    c.drawText(text)

    c.setFont(font, 8)
    c.drawRightString(
        width - margin_x,
        15 * mm,
        f"Voucher ID: {voucher.get('id')}",
    )

    c.showPage()
    c.save()
    return buf.getvalue()
