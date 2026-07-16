"""Casdoor bootstrap — org(租戶)/角色/使用者/application 冪等同步(WBS 2.1.1/CR-0141)。

用法(Casdoor 起來後,見 web/platform-console/docker-compose.yml profile idp):
  POSTGRES_URI=postgresql://lock:0000@localhost:5433/lock_AI_data \
    uv run python scripts/idp/casdoor_bootstrap.py [--dry-run]

做什麼(全部冪等:先 get 後 add,存在即略過/更新):
  1. 以內建 admin 登入 Casdoor(--admin-password,本機預設 123;prod 必換 §8-2)
  2. upsert organization:平台庫 tenant 表(slug/company/plan)→ org
     (passwordType=bcrypt 供 hash 遷移;plan 存 org properties——License 資料面就緒,
      gate 隨 ADR-002);平台庫不可達時退 --org/--tenant-id 單租戶模式
  3. upsert 7 角色物件(角色正典,13_Security §3.1;2.1.2 自助開帳 UI 用)
  4. upsert application(smartlock-portal;--client-id/--client-secret 固定值,
     redirect URIs=四站 /auth/callback,R2 授權碼流用)
  5. sync users:品牌庫 users(7 正典角色,排除 line_user)→ Casdoor user,
     bcrypt hash 原樣導入(CR-0141 D4),properties 寫入身分映射三鍵:
     smartlock_user_id / tenant_id / smartlock_role(api OIDC claims 映射依據,D2)
  6. 匯出 cert-built-in 公鑰 PEM → --cert-out(api 端 CASDOOR_JWT_PUBLIC_KEY_FILE 用)
  7. (opt-in)第三方登入 provider:CASDOOR_GOOGLE_CLIENT_ID/SECRET、
     CASDOOR_LINE_CLIENT_ID/SECRET 設定時 upsert Google / LINE provider 並掛上
     application(20260715 會議 16.5.2:鎖匠端支援 Google / Line 第三方登入)。
     未設=完全跳過(零行為變化)。憑證申請與 redirect 設定見
     docs/uat/casdoor-third-party-login-runbook-20260716.md
"""

from __future__ import annotations

import argparse
import json
import os
import sys

import httpx
import psycopg

CANON_ROLES = (
    "admin", "operations_manager", "customer_service",
    "reviewer", "technician", "dispatcher",
)  # platform_admin 屬平台 org,R1 品牌 org 不建

PORTAL_REDIRECT_URIS = [
    "http://localhost:3000/auth/callback",
    "http://localhost:3001/auth/callback",
    "http://localhost:3002/auth/callback",
    "http://localhost:3003/auth/callback",
]


class Casdoor:
    """極薄 Casdoor REST client(session cookie 認證)。"""

    def __init__(self, endpoint: str, dry_run: bool = False) -> None:
        self.base = endpoint.rstrip("/")
        self.http = httpx.Client(base_url=self.base, timeout=15)
        self.dry = dry_run

    def login(self, username: str, password: str) -> None:
        r = self.http.post("/api/login", json={
            "application": "app-built-in", "organization": "built-in",
            "username": username, "password": password,
            "autoSignin": True, "type": "login",
        })
        body = r.json()
        if r.status_code != 200 or body.get("status") != "ok":
            raise SystemExit(f"[bootstrap] Casdoor admin 登入失敗:{body}")
        print("[bootstrap] admin 登入 OK")

    def get(self, path: str, **params) -> dict | None:
        r = self.http.get(path, params=params)
        body = r.json()
        data = body.get("data") if isinstance(body, dict) else None
        return data or None

    def post(self, path: str, obj: dict, *, soft: bool = False, **params) -> bool:
        """soft=True:失敗不中斷(回 False + 警告)——如 email 撞唯一性的資料怪象。"""
        if self.dry:
            print(f"[bootstrap] (dry-run) POST {path} {obj.get('owner','')}/{obj.get('name','')}")
            return True
        r = self.http.post(path, params=params, json=obj)
        body = r.json()
        if body.get("status") != "ok":
            if soft:
                print(f"[bootstrap] ⚠ 跳過 {obj.get('owner','')}/{obj.get('name','')}:"
                      f"{body.get('msg')}", file=sys.stderr)
                return False
            raise SystemExit(f"[bootstrap] {path} 失敗:{body}")
        return True

    # ── 冪等 upsert ──────────────────────────────────────────────────────────

    def upsert_org(self, slug: str, display: str, *, tenant_id: str, plan: str | None) -> None:
        existing = self.get("/api/get-organization", id=f"admin/{slug}")
        obj = {
            "owner": "admin", "name": slug, "displayName": display or slug,
            "passwordType": "bcrypt",           # D4:bcrypt hash 原樣遷移
            "passwordOptions": [], "tags": [],
            "properties": {"tenant_id": tenant_id, "plan": plan or ""},
            "enableSoftDeletion": False, "isProfilePublic": False,
        }
        if existing:
            merged = existing | {"passwordType": "bcrypt",
                                 "properties": (existing.get("properties") or {})
                                 | obj["properties"]}
            self.post("/api/update-organization", merged, id=f"admin/{slug}")
            print(f"[bootstrap] org {slug} 已存在 → 更新 properties")
        else:
            self.post("/api/add-organization", obj)
            print(f"[bootstrap] org {slug} 建立(tenant={tenant_id[:8]}, plan={plan or '—'})")

    def upsert_role(self, org: str, role: str) -> None:
        if self.get("/api/get-role", id=f"{org}/{role}"):
            return
        self.post("/api/add-role", {
            "owner": org, "name": role, "displayName": role,
            "users": [], "roles": [], "isEnabled": True,
        })
        print(f"[bootstrap] role {org}/{role} 建立")

    def upsert_provider(self, name: str, ptype: str, client_id: str, client_secret: str) -> None:
        """第三方登入 provider(Google / Line)冪等 upsert(16.5.2)。"""
        existing = self.get("/api/get-provider", id=f"admin/{name}")
        obj = {
            "owner": "admin", "name": name, "displayName": f"{ptype} 登入",
            "category": "OAuth", "type": ptype,
            "clientId": client_id, "clientSecret": client_secret,
        }
        if existing:
            self.post("/api/update-provider",
                      existing | {"clientId": client_id, "clientSecret": client_secret},
                      id=f"admin/{name}")
            print(f"[bootstrap] provider {name}({ptype})已存在 → 更新 credentials")
        else:
            self.post("/api/add-provider", obj)
            print(f"[bootstrap] provider {name}({ptype})建立")

    def upsert_application(self, org: str, *, client_id: str, client_secret: str,
                           providers: list[str] | None = None) -> None:
        name = "smartlock-portal"
        existing = self.get("/api/get-application", id=f"admin/{name}")
        # 第三方 provider 掛載項(canSignUp=False:第三方帳號須先綁定/由審核流程開通,
        # 不允許純第三方自動開帳——技師仍走 KYC 註冊,第三方僅作登入方式)
        provider_items = [
            {"name": pn, "canSignIn": True, "canSignUp": False, "canUnlink": True,
             "prompted": False, "alertType": "None", "rule": "None", "provider": None}
            for pn in (providers or [])
        ]
        obj = {
            "owner": "admin", "name": name, "displayName": "SmartLock Portal",
            "organization": org, "clientId": client_id, "clientSecret": client_secret,
            "redirectUris": PORTAL_REDIRECT_URIS,
            "tokenFormat": "JWT", "expireInHours": 1, "refreshExpireInHours": 720,
            "enablePassword": True, "enableSignUp": False,
            "grantTypes": ["authorization_code", "refresh_token", "password"],
            "providers": provider_items,
        }
        if existing:
            # provider 掛載採「合併」:保留既有其它 provider,更新/追加本次 upsert 者
            merged_prov = [p for p in (existing.get("providers") or [])
                           if p.get("name") not in {i["name"] for i in provider_items}]
            merged_prov.extend(provider_items)
            self.post("/api/update-application",
                      existing | {"redirectUris": PORTAL_REDIRECT_URIS,
                                  "clientId": client_id, "clientSecret": client_secret,
                                  "providers": merged_prov},
                      id=f"admin/{name}")
            print(f"[bootstrap] application {name} 已存在 → 更新 redirect/credentials"
                  + (f"/providers({len(provider_items)})" if provider_items else ""))
        else:
            self.post("/api/add-application", obj)
            print(f"[bootstrap] application {name} 建立(client_id={client_id}"
                  + (f", providers={len(provider_items)}" if provider_items else "") + ")")

    def upsert_user(self, org: str, u: dict) -> bool:
        """u: {id, email, display_name, role, password_hash, is_active}。回是否新建。"""
        name = u["email"].split("@")[0] + "-" + u["id"][:8]  # org 內唯一
        existing = self.get("/api/get-user", id=f"{org}/{name}")
        props = {
            "smartlock_user_id": u["id"],       # D2:claims 映射的權威鍵
            "tenant_id": u["tenant_id"],
            "smartlock_role": u["role"],
        }
        if existing:
            self.post("/api/update-user",
                      existing | {"properties": (existing.get("properties") or {}) | props,
                                  "isForbidden": not u["is_active"]},
                      id=f"{org}/{name}")
            return False
        # soft:brand DB 允許同 email 多 role row(如測試帳號雙 row),Casdoor email
        # 唯一——撞到即跳過警告,由資料源收斂(一人一帳)後重跑補齊。
        return self.post("/api/add-user", {
            "owner": org, "name": name, "displayName": u["display_name"] or name,
            "email": u["email"], "password": u["password_hash"],
            "passwordType": "bcrypt",           # D4:hash 原樣導入,使用者無感
            "properties": props, "isForbidden": not u["is_active"],
            "signupApplication": "smartlock-portal",
        }, soft=True)

    def export_cert(self, out_path: str) -> None:
        cert = self.get("/api/get-cert", id="admin/cert-built-in")
        if not cert or not cert.get("certificate"):
            print("[bootstrap] ⚠ cert-built-in 取不到,略過匯出", file=sys.stderr)
            return
        if self.dry:
            print(f"[bootstrap] (dry-run) cert → {out_path}")
            return
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(cert["certificate"])
        print(f"[bootstrap] cert 公鑰已匯出 → {out_path}")
        print(f"[bootstrap]   api 端設定:CASDOOR_JWT_PUBLIC_KEY_FILE={out_path}")


def _resolve_tenant(brand_uri: str, platform_uri: str | None,
                    org_slug: str, fallback_tid: str) -> dict:
    """單一品牌 stack 的租戶解析(bootstrap 以 per-brand 執行)。

    ⚠ tenant_id 權威來源=品牌庫 saas.tenant——token claims 的 tenant_id 就是它;
    平台庫 tenant.id 是註冊表自身的 UUID(不同體系,絕不可寫進身分映射),
    平台庫只用 slug 反查 display/plan 補充。
    """
    tenant_id = fallback_tid
    try:
        with psycopg.connect(brand_uri) as conn, conn.cursor() as cur:
            cur.execute("SELECT id::text FROM saas.tenant ORDER BY created_at LIMIT 1")
            row = cur.fetchone()
            if row:
                tenant_id = row[0]
    except Exception as e:  # noqa: BLE001
        print(f"[bootstrap] ⚠ saas.tenant 不可讀({e})→ 用 --tenant-id", file=sys.stderr)

    display, plan = org_slug, None
    if platform_uri:
        try:
            with psycopg.connect(platform_uri) as conn, conn.cursor() as cur:
                cur.execute("SELECT company_name, plan FROM tenant WHERE slug = %s", (org_slug,))
                row = cur.fetchone()
                if row:
                    display, plan = row[0] or org_slug, row[1]
        except Exception as e:  # noqa: BLE001
            print(f"[bootstrap] ⚠ 平台庫不可達({e})→ 無 display/plan 補充", file=sys.stderr)

    return {"tenant_id": tenant_id, "slug": org_slug, "display": display, "plan": plan}


def _load_users(brand_uri: str, tenant_id: str) -> list[dict]:
    roles = ",".join(f"'{r}'" for r in CANON_ROLES)
    with psycopg.connect(brand_uri) as conn, conn.cursor() as cur:
        cur.execute(
            f"SELECT id::text, email, display_name, role, password_hash, is_active, tenant_id::text "
            f"FROM users WHERE tenant_id = %s AND role IN ({roles}) "
            f"AND password_hash LIKE '$2%%'",  # 排除 disabled placeholder hash
            (tenant_id,),
        )
        return [{"id": r[0], "email": r[1], "display_name": r[2], "role": r[3],
                 "password_hash": r[4], "is_active": r[5], "tenant_id": r[6]}
                for r in cur.fetchall()]


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Casdoor org/角色/使用者冪等同步")
    p.add_argument("--endpoint", default=os.getenv("CASDOOR_ENDPOINT", "http://localhost:8005"))
    p.add_argument("--admin-user", default="admin")
    p.add_argument("--admin-password", default=os.getenv("CASDOOR_ADMIN_PASSWORD", "123"))
    p.add_argument("--client-id", default=os.getenv("CASDOOR_CLIENT_ID", "smartlock-portal-client"))
    p.add_argument("--client-secret", default=os.getenv("CASDOOR_CLIENT_SECRET", "dev-secret-change-me"))
    p.add_argument("--org", default="locksmart", help="平台庫不可達時的 fallback org slug")
    p.add_argument("--tenant-id", default="00000000-0000-0000-0000-000000000001")
    p.add_argument("--cert-out", default="infra/casdoor/casdoor_cert.pem")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args(argv)

    brand_uri = os.getenv("POSTGRES_URI")
    if not brand_uri:
        raise SystemExit("[bootstrap] 需要 POSTGRES_URI(品牌庫,users 同步來源)")

    cd = Casdoor(args.endpoint, dry_run=args.dry_run)
    cd.login(args.admin_user, args.admin_password)

    t = _resolve_tenant(brand_uri, os.getenv("PLATFORM_POSTGRES_URI"),
                        args.org, args.tenant_id)
    print(f"[bootstrap] 租戶解析:org={t['slug']} tenant_id={t['tenant_id']}(品牌庫權威)")
    cd.upsert_org(t["slug"], t["display"], tenant_id=t["tenant_id"], plan=t["plan"])
    for role in CANON_ROLES:
        cd.upsert_role(t["slug"], role)
    users = _load_users(brand_uri, t["tenant_id"])
    created = sum(1 for u in users if cd.upsert_user(t["slug"], u))
    print(f"[bootstrap] org {t['slug']}:users 同步 {len(users)} 筆(新建 {created})")

    # 第三方登入 provider(16.5.2,opt-in:env 有憑證才建;未設=零行為變化)
    provider_names: list[str] = []
    third_party = [
        ("google-oauth", "Google",
         os.getenv("CASDOOR_GOOGLE_CLIENT_ID"), os.getenv("CASDOOR_GOOGLE_CLIENT_SECRET")),
        ("line-login", "Line",
         os.getenv("CASDOOR_LINE_CLIENT_ID"), os.getenv("CASDOOR_LINE_CLIENT_SECRET")),
    ]
    for pname, ptype, cid, secret in third_party:
        if cid and secret:
            cd.upsert_provider(pname, ptype, cid, secret)
            provider_names.append(pname)
        else:
            print(f"[bootstrap] provider {pname}({ptype})未設憑證 → 跳過"
                  f"(設 CASDOOR_{ptype.upper()}_CLIENT_ID/SECRET 啟用)")

    cd.upsert_application(t["slug"],
                          client_id=args.client_id, client_secret=args.client_secret,
                          providers=provider_names)
    cd.export_cert(args.cert_out)

    print(f"[bootstrap] 完成:org={t['slug']} new_users={created}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
