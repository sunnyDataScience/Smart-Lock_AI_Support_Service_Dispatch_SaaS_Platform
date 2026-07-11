#!/usr/bin/env python3
"""smartlock-docs/ → docs_html/enterprise/ 檢視快取產生器（tier-5 view）。

定位（2026-07-11 業主裁決，接續 2026-07-08「正典無 HTML 鏡像」決議）：
  - 正典＝ smartlock-docs/ 純 .md；本產出是「一次性生成、不入 git 的檢視快取」，
    docs_html/ 已列 .gitignore——兩者不一致時一律以 .md 為準。
  - 每頁頁首都印生成時間與 cache 警語；要新版就重跑本腳本，不要手改輸出。

用法（於專案根目錄）：
  uv run python scripts/dev/gen_enterprise_view.py
需求：pandoc（brew install pandoc）。
"""
from __future__ import annotations

import datetime
import re
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "smartlock-docs"
OUT = ROOT / "docs_html" / "enterprise"

GENERATED_AT = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

CSS = """
:root { --ink:#1f2328; --muted:#59636e; --line:#d1d9e0; --bg:#ffffff; --accent:#0969da; }
* { box-sizing:border-box; }
body { margin:0; background:var(--bg); color:var(--ink); line-height:1.75;
  font-family:-apple-system,"PingFang TC","Microsoft JhengHei","Noto Sans TC",sans-serif; }
.wrap { max-width:960px; margin:0 auto; padding:24px 32px 64px; }
.banner { background:#fff8e6; border:1px solid #e8d8a0; border-radius:6px;
  padding:10px 16px; font-size:13px; color:#6b5b1e; margin-bottom:24px; }
.banner code { background:#f3ecd2; padding:1px 5px; border-radius:3px; }
.crumb { font-size:13px; margin-bottom:8px; }
.crumb a { color:var(--accent); text-decoration:none; }
h1,h2,h3 { line-height:1.4; }
h1 { border-bottom:2px solid var(--ink); padding-bottom:8px; }
h2 { border-bottom:1px solid var(--line); padding-bottom:4px; margin-top:36px; }
table { border-collapse:collapse; width:100%; margin:12px 0; font-size:14px; display:block; overflow-x:auto; }
th,td { border:1px solid var(--line); padding:7px 11px; text-align:left; vertical-align:top; }
th { background:#f6f8fa; }
code { background:#f6f8fa; padding:1px 5px; border-radius:3px; font-size:0.9em; }
pre { background:#f6f8fa; border:1px solid var(--line); border-radius:6px;
  padding:12px 16px; overflow-x:auto; font-size:13px; line-height:1.55; }
pre code { background:none; padding:0; }
blockquote { border-left:3px solid var(--line); margin-left:0; padding-left:16px; color:var(--muted); }
.mermaid { background:#fff; border:1px solid var(--line); border-radius:6px;
  padding:12px; margin:12px 0; text-align:center; overflow-x:auto; }
a { color:var(--accent); }
.idx-group { margin-bottom:28px; }
.idx-group li { margin:4px 0; }
.idx-desc { color:var(--muted); font-size:13px; margin-left:8px; }
"""

MERMAID_CDN = (
    '<script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>\n'
    '<script>mermaid.initialize({startOnLoad:true,theme:"neutral"});</script>'
)


def banner(rel_src: str) -> str:
    return (
        '<div class="banner">⚠ 本頁為自動生成的檢視快取（tier-5 view）。'
        f"正典＝<code>{rel_src}</code>，兩者不一致時以 .md 為準。"
        f"生成時間：{GENERATED_AT}；重生：<code>uv run python scripts/dev/gen_enterprise_view.py</code></div>"
    )


def strip_frontmatter(text: str) -> tuple[str, str | None]:
    """去 YAML frontmatter；回傳 (內文, frontmatter title)。"""
    title = None
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            fm = text[3:end]
            m = re.search(r'^title:\s*["\']?(.+?)["\']?\s*$', fm, re.M)
            if m:
                title = m.group(1)
            text = text[end + 4:]
    return text, title


def doc_title(text: str, fm_title: str | None, fallback: str) -> str:
    if fm_title:
        return fm_title
    m = re.search(r"^#\s+(.+)$", text, re.M)
    return m.group(1).strip() if m else fallback


def preprocess_mermaid(text: str) -> str:
    return re.sub(
        r"```mermaid\n(.*?)```",
        lambda m: f'<div class="mermaid">\n{m.group(1)}</div>',
        text,
        flags=re.S,
    )


def md_to_html_body(md_text: str) -> str:
    return subprocess.run(
        ["pandoc", "-f", "gfm", "-t", "html5", "--wrap=none"],
        input=md_text, capture_output=True, text=True, check=True,
    ).stdout


def rewrite_md_links(html_text: str) -> str:
    """站內相對連結 .md → .html（外部 http 連結不動）。"""
    return re.sub(
        r'href="(?!https?://)([^"#]+)\.md(#[^"]*)?"',
        lambda m: f'href="{m.group(1)}.html{m.group(2) or ""}"',
        html_text,
    )


def page(title: str, body: str, rel_src: str, depth: int) -> str:
    home = "../" * depth + "index.html"
    return f"""<!DOCTYPE html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>{CSS}</style>
</head>
<body><div class="wrap">
<div class="crumb"><a href="{home}">← 回總目錄</a></div>
{banner(rel_src)}
{body}
</div>
{MERMAID_CDN}
</body></html>"""


def render(src: Path, out: Path, depth: int) -> str:
    """轉一份 .md；回傳文件標題（給 index 用）。"""
    raw = src.read_text(encoding="utf-8")
    text, fm_title = strip_frontmatter(raw)
    title = doc_title(text, fm_title, src.stem)
    body = rewrite_md_links(md_to_html_body(preprocess_mermaid(text)))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page(title, body, str(src.relative_to(ROOT)), depth), encoding="utf-8")
    return title


def main() -> int:
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)

    groups: dict[str, list[tuple[str, str]]] = {"enterprise": [], "adr": [], "other": []}

    for src in sorted((SRC / "enterprise").glob("*.md")):
        title = render(src, OUT / f"{src.stem}.html", depth=2)
        groups["enterprise"].append((f"{src.stem}.html", title))

    for src in sorted((SRC / "enterprise" / "14_ADR").glob("*.md")):
        title = render(src, OUT / "14_ADR" / f"{src.stem}.html", depth=3)
        groups["adr"].append((f"14_ADR/{src.stem}.html", title))

    readme = SRC / "README.md"
    if readme.exists():
        title = render(readme, OUT / "README.html", depth=2)
        groups["other"].append(("README.html", f"{title}（smartlock-docs 導覽）"))

    api_spec = SRC / "enterprise" / "16_API_Spec.yaml"
    if api_spec.exists():
        shutil.copy2(api_spec, OUT / "16_API_Spec.yaml")
        groups["other"].append(("16_API_Spec.yaml", "16_API_Spec.yaml（機讀原檔；runtime SSOT＝api/openapi.yaml）"))

    def li(items: list[tuple[str, str]]) -> str:
        return "\n".join(f'<li><a href="{href}">{t}</a></li>' for href, t in items)

    index_body = f"""<h1>Smart Lock 企業文件 — 檢視快取</h1>
<div class="idx-group"><h2>導覽</h2><ul>{li(groups["other"])}</ul></div>
<div class="idx-group"><h2>企業正典 00–27（{len(groups["enterprise"])} 份）</h2><ul>{li(groups["enterprise"])}</ul></div>
<div class="idx-group"><h2>ADR 決策記錄（{len(groups["adr"])} 份）</h2><ul>{li(groups["adr"])}</ul></div>"""
    (OUT / "index.html").write_text(
        page("Smart Lock 企業文件檢視快取", index_body, "smartlock-docs/", 2).replace(
            '<div class="crumb"><a href="../../index.html">← 回總目錄</a></div>', ""
        ),
        encoding="utf-8",
    )

    total = len(groups["enterprise"]) + len(groups["adr"]) + len(groups["other"])
    print(f"✓ 生成 {total} 頁 → {OUT.relative_to(ROOT)}/index.html（{GENERATED_AT}）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
