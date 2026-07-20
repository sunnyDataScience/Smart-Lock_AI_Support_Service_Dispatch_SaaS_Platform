"""CR-0173 — technician line_user_id 欄位級加密(Fernet + blind index)。

驗證:
- crypto round-trip / 非確定性加密 / 確定性 blind index。
- notify_assignment / notify_pool_new 讀出 **解密** 後才 push（漏解密會把密文送進 LINE）。
- 過渡期 enc 空 → 回退 legacy 明文。
- bind_by_code 寫 enc + bidx、**明文不入庫**;換綁去重用 bidx 等值查。
"""

from __future__ import annotations

import pytest

import services.technician_line_service as tls
from core import line_uid_crypto


# ── crypto 純函式 ──────────────────────────────────────────────────────────

def test_crypto_roundtrip_and_properties():
    uid = "Ureal1234567890"
    enc = line_uid_crypto.encrypt(uid)
    assert enc != uid and uid not in enc                       # 密文≠明文
    assert line_uid_crypto.decrypt(enc) == uid                 # 可解回
    assert line_uid_crypto.encrypt(uid) != line_uid_crypto.encrypt(uid)  # 非確定性
    assert line_uid_crypto.blind_index(uid) == line_uid_crypto.blind_index(uid)  # 確定性
    assert len(line_uid_crypto.blind_index(uid)) == 64
    assert line_uid_crypto.encrypt(None) is None
    assert line_uid_crypto.decrypt("garbage") is None          # 毀損不拋


# ── mock conn ─────────────────────────────────────────────────────────────

class _Cur:
    def __init__(self, one=None, many=None):
        self._one = one
        self._many = many

    async def fetchone(self):
        return self._one

    async def fetchall(self):
        return self._many or []


class _Conn:
    def __init__(self, script):
        self.calls: list[tuple] = []
        self._script = list(script)

    async def execute(self, sql, params=None):
        self.calls.append((sql, params))
        return self._script.pop(0) if self._script else _Cur()


@pytest.mark.asyncio
async def test_notify_assignment_decrypts_enc_before_push(monkeypatch):
    """讀出 enc → 解密 → push 明文 uid(絕不把密文送進 LINE)。"""
    uid = "Urealtech0001"
    enc = line_uid_crypto.encrypt(uid)
    conn = _Conn([_Cur(one=(None, enc))])  # (line_user_id=None, line_user_id_enc=enc)

    async def fake_conn():
        return conn

    pushed = {}

    async def fake_push(to, text):
        pushed["to"] = to
        return True

    monkeypatch.setattr(tls.db_module, "require_tech_conn", fake_conn)
    monkeypatch.setattr(tls, "_push", fake_push)

    ok = await tls.notify_assignment(technician_id="t1", wo={"id": "w1"})
    assert ok is True
    assert pushed["to"] == uid          # push 的是解密後明文
    assert pushed["to"] != enc          # 不是密文


@pytest.mark.asyncio
async def test_notify_assignment_legacy_plaintext_fallback(monkeypatch):
    """過渡期 enc 空、legacy 明文有 → 回退用明文 push。"""
    conn = _Conn([_Cur(one=("Ulegacy999", None))])

    async def fake_conn():
        return conn

    pushed = {}

    async def fake_push(to, text):
        pushed["to"] = to
        return True

    monkeypatch.setattr(tls.db_module, "require_tech_conn", fake_conn)
    monkeypatch.setattr(tls, "_push", fake_push)

    await tls.notify_assignment(technician_id="t1", wo={"id": "w1"})
    assert pushed["to"] == "Ulegacy999"


@pytest.mark.asyncio
async def test_bind_by_code_stores_encrypted_not_plaintext(monkeypatch):
    """綁定寫 enc + bidx、明文設 NULL 不入庫;換綁去重用 bidx 等值查。"""
    tls._bind_attempts.clear()
    conn = _Conn([
        _Cur(one=("code-1", "tech-NEW", "師傅B")),  # SELECT bind code
        _Cur(many=[]),                               # dup-unbind（無 dup）
        _Cur(),                                       # self-bind
        _Cur(),                                       # used_at
    ])

    async def fake_conn():
        return conn

    monkeypatch.setattr(tls.db_module, "require_tech_conn", fake_conn)

    res = await tls.bind_by_code(line_user_id="Ubindme777", code="123456")
    assert res == {"technician_id": "tech-NEW", "name": "師傅B"}

    # self-bind：寫 enc、明文 NULL、params 不含明文
    selfbind = [c for c in conn.calls if "line_user_id_enc = %s" in c[0]]
    assert selfbind, "應有寫 enc 的 self-bind UPDATE"
    sql, params = selfbind[0]
    assert "line_user_id = NULL" in sql
    assert "Ubindme777" not in params            # 明文不入庫
    enc, bidx, _tid = params
    assert line_uid_crypto.decrypt(enc) == "Ubindme777"          # enc 可解回
    assert bidx == line_uid_crypto.blind_index("Ubindme777")     # bidx 一致

    # dup-unbind：用 bidx 等值查（+ 明文過渡雙軌）
    dup = [c for c in conn.calls
           if "line_user_id_bidx = %s" in c[0] and "id <> " in c[0]]
    assert dup, "換綁去重應以 bidx 等值查"
    tls._bind_attempts.clear()
