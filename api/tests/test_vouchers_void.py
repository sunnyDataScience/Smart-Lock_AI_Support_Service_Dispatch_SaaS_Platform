"""Voucher Void v2 endpoint tests（Track B S7 / ADR-VCH-001/002 / CR-0004 §8）。

@pytest.mark.component — 需 live DB（saas.voucher / saas.voucher_void_event / saas.tenant）

測資策略：
  - 每個 component test 自建 saas.voucher row（INSERT 直打 DB）
  - tenant = DEFAULT_TENANT_ID（00000000-…-0001，migration 004 已 seed saas.tenant）
  - 測試後 cleanup（DELETE by id，由 void_event→reversal→original 順序刪，繞過 append-only trigger）
  - 驗原傳票 append-only：INSERT 後確認原列無被 UPDATE（created_at / debit / credit 不變）

覆蓋測案：
  T01  void happy — 建反向分錄 debit/credit 對調 + reverses_voucher_id + voucher_void_event 寫入 + hash_self 非空
  T02  重複 void → 409 ALREADY_VOIDED
  T03  void 反向分錄本身 → 410 ALREADY_REVERSED
  T04  缺 X-Keeper-Role → 403 KEEPER_ROLE_REQUIRED
  T05  非 keeper role → 403 KEEPER_FORBIDDEN
  T06  原傳票不存在 → 404 NOT_FOUND
  T07  驗原傳票 append-only（原列 debit/credit 未被改）
"""

from __future__ import annotations

import uuid

import pytest
import pytest_asyncio

from tests.conftest import DEFAULT_TENANT_ID, ADMIN_USER_ID

# ─────────────────────────────────────────────────────────────────────────────
# 常數
# ─────────────────────────────────────────────────────────────────────────────

_KEEPER_USER_ID = ADMIN_USER_ID  # admin 屬 _KEEPER_ROLES 集合
_NON_KEEPER_USER_ID = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"


# ─────────────────────────────────────────────────────────────────────────────
# DB helpers（直接操作 saas.voucher，繞過業務邏輯）
# ─────────────────────────────────────────────────────────────────────────────


async def _insert_voucher(
    *,
    tenant_id: str = DEFAULT_TENANT_ID,
    voucher_no: str | None = None,
    debit_account: str = "1100",
    credit_account: str = "2200",
    amount: float = 500.00,
    reverses_voucher_id: str | None = None,
    hash_self: str | None = None,
) -> str:
    """直接 INSERT 一筆 saas.voucher，回傳 id。

    reverses_voucher_id 非 None 時代表此筆本身是反向分錄（用於 T03 測案）。
    """
    import core.db as db_module
    from core.db import _ensure_conn

    await _ensure_conn()
    vid = str(uuid.uuid4())
    vno = voucher_no or f"TST-{vid[:8]}"

    await db_module._conn.execute(
        """
        INSERT INTO saas.voucher (
            id, tenant_id, voucher_no,
            debit_account, credit_account, amount, currency,
            posting_date, reverses_voucher_id, hash_self
        ) VALUES (
            %s::uuid, %s::uuid, %s,
            %s, %s, %s, 'TWD',
            CURRENT_DATE, %s, %s
        )
        """,
        (
            vid, tenant_id, vno,
            debit_account, credit_account, amount,
            reverses_voucher_id,
            hash_self,
        ),
    )
    return vid


async def _fetch_voucher(voucher_id: str) -> dict | None:
    """從 saas.voucher SELECT 單筆，回 dict。"""
    import core.db as db_module
    from core.db import _ensure_conn

    await _ensure_conn()
    cur = await db_module._conn.execute(
        "SELECT id, debit_account, credit_account, amount, reverses_voucher_id, hash_self, created_at "
        "FROM saas.voucher WHERE id = %s::uuid",
        [voucher_id],
    )
    row = await cur.fetchone()
    if not row:
        return None
    return {
        "id": str(row[0]),
        "debit_account": row[1],
        "credit_account": row[2],
        "amount": float(row[3]),
        "reverses_voucher_id": str(row[4]) if row[4] else None,
        "hash_self": row[5],
        "created_at": row[6],
    }


async def _cleanup_void_event_by_voucher(original_id: str) -> str | None:
    """刪 voucher_void_event，回 reversal_voucher_id（如有）。

    append-only trigger 封鎖 UPDATE/DELETE，需用 DISABLE TRIGGER 繞過——
    測試環境清理專用，絕不在生產邏輯使用。
    """
    import core.db as db_module
    from core.db import _ensure_conn

    await _ensure_conn()
    # 取 reversal_voucher_id 供後續刪除
    cur = await db_module._conn.execute(
        "SELECT reversal_voucher_id FROM saas.voucher_void_event WHERE voucher_id = %s::uuid",
        [original_id],
    )
    row = await cur.fetchone()
    reversal_id = str(row[0]) if row else None

    # 測試清理：暫停 trigger
    await db_module._conn.execute(
        "ALTER TABLE saas.voucher_void_event DISABLE TRIGGER tg_saas_voucher_void_event_block_mutation"
    )
    await db_module._conn.execute(
        "DELETE FROM saas.voucher_void_event WHERE voucher_id = %s::uuid",
        [original_id],
    )
    await db_module._conn.execute(
        "ALTER TABLE saas.voucher_void_event ENABLE TRIGGER tg_saas_voucher_void_event_block_mutation"
    )
    return reversal_id


async def _cleanup_voucher(voucher_id: str) -> None:
    """刪 saas.voucher（暫停 append-only trigger，測試清理專用）。"""
    import core.db as db_module
    from core.db import _ensure_conn

    await _ensure_conn()
    await db_module._conn.execute(
        "ALTER TABLE saas.voucher DISABLE TRIGGER tg_saas_voucher_block_mutation"
    )
    await db_module._conn.execute(
        "DELETE FROM saas.voucher WHERE id = %s::uuid",
        [voucher_id],
    )
    await db_module._conn.execute(
        "ALTER TABLE saas.voucher ENABLE TRIGGER tg_saas_voucher_block_mutation"
    )


def _make_keeper_headers(
    user_id: str = _KEEPER_USER_ID,
    role: str = "admin",
    tenant_id: str = DEFAULT_TENANT_ID,
    with_keeper_role: bool = True,
) -> dict[str, str]:
    """建 keeper 用 headers。"""
    from core.auth import create_token

    token, _jti, _exp = create_token(
        user_id=user_id,
        role=role,
        tenant_id=tenant_id,
        token_type="access",
    )
    headers = {
        "Authorization": f"Bearer {token}",
        "Idempotency-Key": str(uuid.uuid4()),
    }
    if with_keeper_role:
        headers["X-Keeper-Role"] = "platform_keeper"
    return headers


# ─────────────────────────────────────────────────────────────────────────────
# Component tests — live DB
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.component
class TestVoidVoucherHappy:
    """T01: void happy path — 所有核心不變量斷言。"""

    @pytest.mark.asyncio
    async def test_void_creates_reversal_entry(self, client):
        """紅字沖銷：反向分錄 debit/credit 對調 + reverses_voucher_id 指向原傳票。"""
        original_id = await _insert_voucher(
            debit_account="1100",
            credit_account="2200",
            amount=500.00,
        )
        try:
            headers = _make_keeper_headers()
            resp = await client.post(
                f"/vouchers/{original_id}/void",
                json={"reason": "error_correction"},
                headers=headers,
            )
            assert resp.status_code == 201, resp.text
            body = resp.json()

            # 反向分錄基本欄位
            assert body["reverses_voucher_id"] == original_id
            # debit/credit 對調（紅字沖銷語意）
            assert body["debit_account"] == "2200"    # 原 credit → 新 debit
            assert body["credit_account"] == "1100"   # 原 debit → 新 credit
            assert float(body["amount"]) == 500.00
            # hash_self 非空（HD-VCH-001 hash chain）
            assert body["hash_self"] is not None
            assert len(body["hash_self"]) == 64  # sha256 hex = 64 chars
            # reason_code 填入
            assert body["reason_code"] == "error_correction"
            # voucher_no 以 '-R' 結尾
            assert body["voucher_no"].endswith("-R")
        finally:
            # cleanup：event → reversal → original
            reversal_id = await _cleanup_void_event_by_voucher(original_id)
            if reversal_id:
                await _cleanup_voucher(reversal_id)
            await _cleanup_voucher(original_id)

    @pytest.mark.asyncio
    async def test_void_event_written(self, client):
        """voucher_void_event 寫入驗證。"""
        import core.db as db_module
        from core.db import _ensure_conn

        original_id = await _insert_voucher(
            debit_account="1100",
            credit_account="2200",
            amount=300.00,
        )
        try:
            headers = _make_keeper_headers()
            resp = await client.post(
                f"/vouchers/{original_id}/void",
                json={"reason": "customer_dispute", "comment": "客戶申訴"},
                headers=headers,
            )
            assert resp.status_code == 201, resp.text
            reversal_id = resp.json()["id"]

            # 直查 DB 確認 event 存在
            await _ensure_conn()
            cur = await db_module._conn.execute(
                "SELECT voucher_id, reversal_voucher_id, reason, comment "
                "FROM saas.voucher_void_event WHERE voucher_id = %s::uuid",
                [original_id],
            )
            row = await cur.fetchone()
            assert row is not None
            assert str(row[0]) == original_id
            assert str(row[1]) == reversal_id
            assert row[2] == "customer_dispute"
            assert row[3] == "客戶申訴"
        finally:
            reversal_id_c = await _cleanup_void_event_by_voucher(original_id)
            if reversal_id_c:
                await _cleanup_voucher(reversal_id_c)
            await _cleanup_voucher(original_id)

    @pytest.mark.asyncio
    async def test_hash_prev_is_original_hash_self(self, client):
        """hash chain：hash_prev = 原傳票.hash_self（HD-VCH-001）。"""
        original_id = await _insert_voucher(
            hash_self="abc123def456" * 5 + "abcd",  # 64 char fake hash
        )
        original = await _fetch_voucher(original_id)
        try:
            headers = _make_keeper_headers()
            resp = await client.post(
                f"/vouchers/{original_id}/void",
                json={"reason": "tax_adjust"},
                headers=headers,
            )
            assert resp.status_code == 201, resp.text
            body = resp.json()
            assert body["hash_prev"] == original["hash_self"]
        finally:
            reversal_id = await _cleanup_void_event_by_voucher(original_id)
            if reversal_id:
                await _cleanup_voucher(reversal_id)
            await _cleanup_voucher(original_id)


@pytest.mark.component
class TestVoidVoucherAppendOnly:
    """T07: 原傳票 append-only——void 後原列未被 UPDATE。"""

    @pytest.mark.asyncio
    async def test_original_voucher_untouched_after_void(self, client):
        """void 後原傳票的 debit/credit/amount/created_at 均不變。"""
        original_id = await _insert_voucher(
            debit_account="3300",
            credit_account="4400",
            amount=999.99,
        )
        before = await _fetch_voucher(original_id)
        try:
            headers = _make_keeper_headers()
            resp = await client.post(
                f"/vouchers/{original_id}/void",
                json={"reason": "error_correction"},
                headers=headers,
            )
            assert resp.status_code == 201, resp.text

            # 再取原傳票，確認未被改動
            after = await _fetch_voucher(original_id)
            assert after is not None
            assert after["debit_account"] == before["debit_account"]
            assert after["credit_account"] == before["credit_account"]
            assert after["amount"] == before["amount"]
            assert after["created_at"] == before["created_at"]
            # reverses_voucher_id 仍為 None（原傳票不指向任何沖銷對象）
            assert after["reverses_voucher_id"] is None
        finally:
            reversal_id = await _cleanup_void_event_by_voucher(original_id)
            if reversal_id:
                await _cleanup_voucher(reversal_id)
            await _cleanup_voucher(original_id)


@pytest.mark.component
class TestVoidVoucherErrors:
    """T02/T03/T04/T05/T06 錯誤路徑。"""

    @pytest.mark.asyncio
    async def test_duplicate_void_returns_409(self, client):
        """T02: 重複 void → 409 ALREADY_VOIDED。"""
        original_id = await _insert_voucher()
        try:
            headers1 = _make_keeper_headers()
            resp1 = await client.post(
                f"/vouchers/{original_id}/void",
                json={"reason": "error_correction"},
                headers=headers1,
            )
            assert resp1.status_code == 201, resp1.text

            # 第二次：不同 Idempotency-Key（確保不被 dedup replay）
            headers2 = _make_keeper_headers()
            resp2 = await client.post(
                f"/vouchers/{original_id}/void",
                json={"reason": "error_correction"},
                headers=headers2,
            )
            assert resp2.status_code == 409
            assert resp2.json()["error_code"] == "ALREADY_VOIDED"
        finally:
            reversal_id = await _cleanup_void_event_by_voucher(original_id)
            if reversal_id:
                await _cleanup_voucher(reversal_id)
            await _cleanup_voucher(original_id)

    @pytest.mark.asyncio
    async def test_void_reversal_returns_410(self, client):
        """T03: void 反向分錄本身（reverses_voucher_id IS NOT NULL）→ 410 ALREADY_REVERSED。"""
        # 先建一個「原傳票」作為 FK 目標
        target_id = await _insert_voucher(voucher_no=f"TST-TARGET-{uuid.uuid4().hex[:6]}")
        # 建一筆本身就是反向分錄的傳票
        reversal_id = await _insert_voucher(
            voucher_no=f"TST-REV-{uuid.uuid4().hex[:6]}",
            reverses_voucher_id=target_id,
        )
        try:
            headers = _make_keeper_headers()
            resp = await client.post(
                f"/vouchers/{reversal_id}/void",
                json={"reason": "error_correction"},
                headers=headers,
            )
            assert resp.status_code == 410
            assert resp.json()["error_code"] == "ALREADY_REVERSED"
        finally:
            await _cleanup_voucher(reversal_id)
            await _cleanup_voucher(target_id)

    @pytest.mark.asyncio
    async def test_missing_keeper_role_header_returns_403(self, client):
        """T04: 缺 X-Keeper-Role header → 403 KEEPER_ROLE_REQUIRED。"""
        original_id = await _insert_voucher()
        try:
            headers = _make_keeper_headers(with_keeper_role=False)
            resp = await client.post(
                f"/vouchers/{original_id}/void",
                json={"reason": "error_correction"},
                headers=headers,
            )
            assert resp.status_code == 403
            assert resp.json()["error_code"] == "KEEPER_ROLE_REQUIRED"
        finally:
            await _cleanup_voucher(original_id)

    @pytest.mark.asyncio
    async def test_non_keeper_role_returns_403(self, client):
        """T05: user.role 非 keeper role → 403 KEEPER_FORBIDDEN。"""
        original_id = await _insert_voucher()
        try:
            # technician role — 不屬 _KEEPER_ROLES
            headers = _make_keeper_headers(
                user_id=_NON_KEEPER_USER_ID,
                role="technician",
                with_keeper_role=True,
            )
            resp = await client.post(
                f"/vouchers/{original_id}/void",
                json={"reason": "error_correction"},
                headers=headers,
            )
            assert resp.status_code == 403
            assert resp.json()["error_code"] == "KEEPER_FORBIDDEN"
        finally:
            await _cleanup_voucher(original_id)

    @pytest.mark.asyncio
    async def test_nonexistent_voucher_returns_404(self, client):
        """T06: 原傳票不存在 → 404 NOT_FOUND。"""
        nonexistent_id = str(uuid.uuid4())
        headers = _make_keeper_headers()
        resp = await client.post(
            f"/vouchers/{nonexistent_id}/void",
            json={"reason": "error_correction"},
            headers=headers,
        )
        assert resp.status_code == 404
        assert resp.json()["error_code"] == "NOT_FOUND"


# ─────────────────────────────────────────────────────────────────────────────
# Unit tests — pure logic
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.unit
class TestComputeHashSelf:
    """_compute_hash_self 純函式斷言（HD-VCH-001 hash chain V1）。"""

    def test_returns_64_char_hex(self):
        from services.voucher_void_service import _compute_hash_self

        result = _compute_hash_self("VCH-001", "500.00", "1100", "2200", None, None)
        assert len(result) == 64
        assert all(c in "0123456789abcdef" for c in result)

    def test_deterministic(self):
        from services.voucher_void_service import _compute_hash_self

        h1 = _compute_hash_self("VCH-001", "500.00", "1100", "2200", "uuid-x", "prev-hash")
        h2 = _compute_hash_self("VCH-001", "500.00", "1100", "2200", "uuid-x", "prev-hash")
        assert h1 == h2

    def test_different_inputs_different_hash(self):
        from services.voucher_void_service import _compute_hash_self

        h1 = _compute_hash_self("VCH-001", "500.00", "1100", "2200", None, None)
        h2 = _compute_hash_self("VCH-002", "500.00", "1100", "2200", None, None)
        assert h1 != h2

    def test_none_fields_stable(self):
        from services.voucher_void_service import _compute_hash_self

        h1 = _compute_hash_self("VCH-001", "100.00", None, None, None, None)
        h2 = _compute_hash_self("VCH-001", "100.00", None, None, None, None)
        assert h1 == h2


@pytest.mark.unit
class TestValidReason:
    """_VALID_REASON 集合確認。"""

    def test_valid_reasons(self):
        from services.voucher_void_service import _VALID_REASON

        assert _VALID_REASON == {"error_correction", "customer_dispute", "tax_adjust"}
