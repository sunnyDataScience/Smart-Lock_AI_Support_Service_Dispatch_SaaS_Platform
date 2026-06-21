#!/usr/bin/env python3
"""docs/ → docs_html/ 生成器。

把 docs/ 內所有 .md（521）用 pandoc 轉成統一深色主題 HTML（麵包屑 + 回目錄），
鏡像分類目錄結構；既有 .html 原樣複製。產一份單頁可搜尋總目錄 docs_html/index.html
（分類摺疊 + 每檔說明 + 佈告欄最近更新）。純 html 檔另產 .md 源放回 docs/。

用法：.venv/bin/python tools/gen_docs_html.py
"""
from __future__ import annotations

import html as _html
import re
import subprocess
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
OUT = ROOT / "docs_html"

# top-level docs dir → (類別中文名, 該類在做什麼, 排序)
CATEGORIES = {
    "_source":       ("📜 原始正典 Spec", "所有需求追溯的源頭規格（工單/ERP、AI 客服同步）", 0),
    "prd":           ("📦 產品/商業需求", "SOW 工作說明書、商業架構、PRD、藍圖快照", 1),
    "analysis":      ("📋 需求拆解 BR/FR", "Business Rules（BR）+ Functional Requirements（FR）+ 系統規格", 2),
    "architecture":  ("🏛️ 架構與決策 ADR", "ADR 決策紀錄、DDD 領域模型、C4 圖、API contract、NFR", 3),
    "governance":    ("⚖️ 治理與簽核", "freeze 簽核、stakeholders、法務 memo、ADR review", 4),
    "policy":        ("🔐 政策即程式", "OPA policy as code（rego）", 5),
    "qa":            ("🧪 測試策略 QA", "test plan、eval framework、自動化覆蓋率 map、測資策略", 6),
    "ops":           ("🚀 營運上線", "SLO、runbook、rollback、pipeline、release readiness", 7),
    "_ops":          ("🛠️ 營運籌備", "SLO baseline、UAT plan、codegen runbook、readiness", 8),
    "ui":            ("🎨 UI 設計規格", "web design spec prompt pipeline + style references", 9),
    "ux":            ("🧭 UX 流程/線框", "user flow、wireframes", 10),
    "3-process":     ("📐 流程 (tier-3)", "四階段測試計畫（Alpha/Beta/RC/GA）", 11),
    "4-exploration": ("🔬 探索/CIA (tier-4)", "CR-NNNN 變更影響分析、go-live 人工確認清單", 12),
    "5-views":       ("📊 自動視圖 (tier-5)", "測試覆蓋報告（程式生成，勿手改）", 13),
    "_audit":        ("🧾 CR 稽核軌跡", "每個 CR 的 WBS/進度/decision matrix/dashboard", 14),
    "html":          ("🖥️ HTML 報告", "渲染好的手冊/runbook/eval report", 15),
    "_index":        ("🗂️ 索引/追溯", "FR↔BR↔ADR traceability matrix（自動生成）", 16),
    "_archive":      ("📦 封存舊版", "blueprints（xlsx 藍圖）、legacy、extras", 17),
}
DEFAULT_CAT = ("📁 其他", "未分類文件", 98)

TEXT_WRAP_EXT = {".rego", ".py", ".sql", ".yaml", ".yml"}
BINARY_EXT = {".xlsx", ".png", ".pen", ".archived"}

CSS = """
*{box-sizing:border-box}body{font-family:-apple-system,"PingFang TC","Microsoft JhengHei",sans-serif;margin:0;background:#0f172a;color:#e2e8f0;line-height:1.7}
.wrap{max-width:960px;margin:0 auto;padding:24px 28px 80px}
.bc{font-size:12.5px;color:#94a3b8;margin-bottom:14px}.bc a{color:#7dd3fc;text-decoration:none}.bc a:hover{text-decoration:underline}
.doc h1{font-size:24px;border-bottom:1px solid #334155;padding-bottom:8px;margin-top:8px}
.doc h2{font-size:19px;margin-top:28px;border-left:4px solid #38bdf8;padding-left:10px}
.doc h3{font-size:16px;margin-top:20px;color:#cbd5e1}.doc h4{font-size:14px;color:#94a3b8}
.doc a{color:#7dd3fc}.doc code{background:#1e293b;padding:1px 5px;border-radius:4px;font-size:.88em;color:#7dd3fc}
.doc pre{background:#1e293b;border:1px solid #334155;border-radius:8px;padding:12px 14px;overflow:auto}.doc pre code{background:none;padding:0}
.doc table{border-collapse:collapse;width:100%;margin:12px 0;font-size:13.5px;background:#1e293b;border-radius:8px;overflow:hidden}
.doc th,.doc td{border:1px solid #334155;padding:7px 10px;text-align:left;vertical-align:top}.doc th{background:#0b1220}
.doc blockquote{border-left:4px solid #475569;margin:12px 0;padding:4px 14px;color:#cbd5e1;background:#172033}
.doc ul,.doc ol{padding-left:22px}.doc img{max-width:100%}
.meta{font-size:12px;color:#64748b;margin:6px 0 18px}
"""

INDEX_CSS = CSS + """
h1{font-size:26px;margin:0 0 2px}.sub{color:#94a3b8;font-size:13.5px;margin-bottom:18px}
.board{background:#172033;border:1px solid #1e40af;border-radius:12px;padding:14px 18px;margin:16px 0}
.board h2{border:none;padding:0;font-size:16px;margin:0 0 10px;color:#bfdbfe}
.board ul{margin:0;padding-left:0;list-style:none}.board li{padding:4px 0;border-bottom:1px solid #1e293b;font-size:13.5px;display:flex;gap:10px;align-items:baseline}
.board .d{color:#fbbf24;font-family:ui-monospace,monospace;font-size:12px;white-space:nowrap}
.board .c{color:#64748b;font-size:11.5px}
#q{width:100%;padding:11px 14px;border-radius:9px;border:1px solid #475569;background:#1e293b;color:#e2e8f0;font-size:14px;margin:8px 0 18px}
details{background:#1e293b;border:1px solid #334155;border-radius:10px;margin:10px 0;overflow:hidden}
summary{cursor:pointer;padding:13px 16px;font-size:15px;font-weight:600;list-style:none;display:flex;justify-content:space-between;align-items:center}
summary::-webkit-details-marker{display:none} summary:hover{background:#243044}
summary .cd{font-weight:400;font-size:12px;color:#94a3b8;margin-left:10px;flex:1}
summary .ct{background:#0b1220;color:#7dd3fc;border-radius:20px;padding:2px 10px;font-size:12px}
.flist{padding:4px 16px 14px}.frow{display:flex;gap:12px;padding:7px 0;border-bottom:1px solid #29374b;align-items:baseline}
.frow a{color:#e2e8f0;text-decoration:none;font-size:13.5px;font-weight:500;min-width:230px}.frow a:hover{color:#7dd3fc}
.frow .fd{color:#94a3b8;font-size:12.5px;flex:1}.frow .fdate{color:#475569;font-family:ui-monospace,monospace;font-size:11px;white-space:nowrap}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px;margin:14px 0}
.kcard{background:#1e293b;border:1px solid #334155;border-radius:10px;padding:12px}.kcard .n{font-size:24px;font-weight:700;color:#38bdf8}.kcard .l{font-size:12px;color:#94a3b8}
"""


def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def git_last_dates() -> dict[str, str]:
    """一次 git log 解析每個 docs 檔的最後 commit 日期（YYYY-MM-DD）。"""
    res = run(["git", "-C", str(ROOT), "log", "--pretty=format:C%cs", "--name-only", "--", "docs"])
    dates: dict[str, str] = {}
    cur = None
    for line in res.stdout.splitlines():
        if line.startswith("C") and len(line) == 11:
            cur = line[1:]
        elif line.strip() and cur:
            dates.setdefault(line.strip(), cur)
    return dates


def parse_frontmatter(text):
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end > 0:
            try:
                meta = yaml.safe_load(text[3:end]) or {}
                if isinstance(meta, dict):
                    return meta, text[end + 4:]
            except Exception:
                return {}, text
    return {}, text


def title_desc(meta, body, fname):
    title = meta.get("title")
    if not title:
        m = re.search(r"^#\s+(.+)$", body, re.M)
        title = m.group(1).strip() if m else fname
    desc = meta.get("description") or meta.get("hook") or meta.get("detail")
    if not desc:
        for ln in body.splitlines():
            s = ln.strip()
            if s and not s.startswith(("#", "---", "|", ">", "-", "*", "```", "<", "=", "+")):
                desc = s
                break
    title = re.sub(r"[#*`\[\]]", "", str(title)).strip()[:90]
    desc = re.sub(r"[#*`]", "", str(desc or "")).strip()
    if len(desc) > 120:
        desc = desc[:118] + "…"
    return title, desc


def page(title, body_html, breadcrumb, depth):
    up = "../" * depth
    return f"""<!DOCTYPE html><html lang="zh-Hant"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{_html.escape(title)}</title>
<style>{CSS}</style></head><body><div class="wrap">
<div class="bc"><a href="{up}index.html">🏠 文件總目錄</a> ／ {breadcrumb}</div>
<div class="doc">{body_html}</div></div></body></html>"""


def main():
    # 清空重建（OUT 全為產物）→ 來源 docs 移檔/刪檔後不留孤兒 html
    import shutil
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    dates = git_last_dates()
    records = []  # (cat_key, rel_str, out_rel, title, desc, date)

    md_files = sorted(DOCS.rglob("*.md"))
    html_files = sorted(DOCS.rglob("*.html"))
    other_files = sorted(p for p in DOCS.rglob("*")
                         if p.is_file() and p.suffix.lower() in (TEXT_WRAP_EXT | BINARY_EXT))

    # 1) markdown → html
    for src in md_files:
        rel = src.relative_to(DOCS)
        cat_key = rel.parts[0]
        out = OUT / rel.with_suffix(".html")
        out.parent.mkdir(parents=True, exist_ok=True)
        text = src.read_text(encoding="utf-8", errors="replace")
        meta, bodymd = parse_frontmatter(text)
        title, desc = title_desc(meta, bodymd, src.stem)
        r = run(["pandoc", "-f", "gfm", "-t", "html5"], input=bodymd)
        body_html = r.stdout or "<p>(空)</p>"
        depth = len(rel.parts) - 1 + 1  # files sit under OUT/<rel dirs>; +1 because index at OUT root
        depth = len(rel.parents) - 1
        bc = " ／ ".join(_html.escape(p) for p in rel.parts)
        out.write_text(page(title, body_html, bc, depth), encoding="utf-8")
        records.append((cat_key, str(rel), str(out.relative_to(OUT)), title, desc,
                        dates.get(f"docs/{rel}", "")))

    # 2) 既有 html → 原樣複製（已自帶樣式）
    for src in html_files:
        rel = src.relative_to(DOCS)
        out = OUT / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        raw = src.read_text(encoding="utf-8", errors="replace")
        out.write_text(raw, encoding="utf-8")
        m = re.search(r"<title>(.*?)</title>", raw, re.I | re.S)
        title = (m.group(1).strip() if m else src.stem)[:90]
        records.append((rel.parts[0], str(rel), str(out.relative_to(OUT)), title,
                        "（既有 HTML 報告，原樣保留）", dates.get(f"docs/{rel}", "")))
        # 純 html（無 .md 源）→ 產 markdown 放回 docs/
        if not src.with_suffix(".md").exists():
            md = run(["pandoc", "-f", "html", "-t", "gfm"], input=raw)
            src.with_suffix(".md").write_text(
                f"<!-- 由 {rel} 自動轉出的 markdown 源（gen_docs_html.py）-->\n\n" + (md.stdout or ""),
                encoding="utf-8")

    # 3) 文字型非 md（rego/py/sql/yaml）→ <pre> 包裝；二進位 → 只登錄連回原檔
    for src in other_files:
        rel = src.relative_to(DOCS)
        cat_key = rel.parts[0]
        if src.suffix.lower() in TEXT_WRAP_EXT:
            out = OUT / rel.with_suffix(src.suffix + ".html")
            out.parent.mkdir(parents=True, exist_ok=True)
            content = _html.escape(src.read_text(encoding="utf-8", errors="replace"))
            depth = len(rel.parents) - 1
            bc = " ／ ".join(_html.escape(p) for p in rel.parts)
            out.write_text(page(src.name, f"<h1>{_html.escape(src.name)}</h1><pre><code>{content}</code></pre>", bc, depth),
                           encoding="utf-8")
            records.append((cat_key, str(rel), str(out.relative_to(OUT)), src.name,
                            f"原始 {src.suffix[1:]} 檔（程式碼/設定）", dates.get(f"docs/{rel}", "")))
        else:
            records.append((cat_key, str(rel), f"../docs/{rel}", src.name,
                            f"二進位檔（{src.suffix[1:]}），連回原始 docs/", dates.get(f"docs/{rel}", "")))

    build_index(records, dates)
    print(f"完成：{len(md_files)} md + {len(html_files)} html + {len(other_files)} 其他 → docs_html/")
    print(f"總登錄 {len(records)} 筆")


def build_index(records, dates):
    # 佈告欄：最近更新 15 筆（有日期者）
    dated = sorted([r for r in records if r[5]], key=lambda r: r[5], reverse=True)[:15]
    board = "".join(
        f'<li><span class="d">{r[5]}</span><a href="{_html.escape(r[2])}" style="color:#e2e8f0;text-decoration:none;flex:1">{_html.escape(r[3])}</a>'
        f'<span class="c">{_html.escape(CATEGORIES.get(r[0], DEFAULT_CAT)[0])}</span></li>'
        for r in dated)

    # 分類分組
    by_cat: dict[str, list] = {}
    for r in records:
        by_cat.setdefault(r[0], []).append(r)
    ordered = sorted(by_cat.keys(), key=lambda k: CATEGORIES.get(k, DEFAULT_CAT)[2])

    sections = []
    for k in ordered:
        name, what, _ = CATEGORIES.get(k, DEFAULT_CAT)
        rows = sorted(by_cat[k], key=lambda r: r[1])
        frows = "".join(
            f'<div class="frow" data-s="{_html.escape((r[3]+" "+r[4]+" "+r[1]).lower())}">'
            f'<a href="{_html.escape(r[2])}">{_html.escape(r[3])}</a>'
            f'<span class="fd">{_html.escape(r[4])}</span>'
            f'<span class="fdate">{r[5]}</span></div>'
            for r in rows)
        sections.append(
            f'<details><summary><span>{_html.escape(name)}<span class="cd">{_html.escape(what)}</span></span>'
            f'<span class="ct">{len(rows)}</span></summary><div class="flist">{frows}</div></details>')

    total = len(records)
    n_md = sum(1 for r in records if r[2].endswith(".html") and not r[2].startswith("../"))
    last = dated[0][5] if dated else "—"
    html_out = f"""<!DOCTYPE html><html lang="zh-Hant"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>文件總目錄 — 智慧鎖 SaaS</title>
<style>{INDEX_CSS}</style></head><body><div class="wrap">
<h1>📚 智慧鎖 AI 派工 SaaS — 文件總目錄</h1>
<div class="sub">docs/ 全文件 HTML 版索引 · 共 {total} 份 · 最後更新 {last} · 點分類展開 · 上方搜尋框可即時過濾</div>
<div class="cards">
  <div class="kcard"><div class="n">{total}</div><div class="l">總文件數</div></div>
  <div class="kcard"><div class="n">{len(ordered)}</div><div class="l">分類</div></div>
  <div class="kcard"><div class="n">{n_md}</div><div class="l">HTML 文件頁</div></div>
</div>
<div class="board"><h2>📌 佈告欄 — 最近更新的文件</h2><ul>{board}</ul></div>
<input id="q" placeholder="🔍 輸入關鍵字即時過濾文件（標題／說明／路徑）…" oninput="flt(this.value)">
{''.join(sections)}
</div>
<script>
function flt(v){{v=v.trim().toLowerCase();
 document.querySelectorAll('details').forEach(d=>{{let any=false;
  d.querySelectorAll('.frow').forEach(r=>{{const hit=!v||r.dataset.s.includes(v);r.style.display=hit?'':'none';if(hit)any=true;}});
  d.style.display=any?'':'none';if(v)d.open=any;}});}}
</script></body></html>"""
    (OUT / "index.html").write_text(html_out, encoding="utf-8")


if __name__ == "__main__":
    main()
