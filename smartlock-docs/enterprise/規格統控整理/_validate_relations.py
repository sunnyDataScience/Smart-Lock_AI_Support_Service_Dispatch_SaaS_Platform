#!/usr/bin/env python3
"""Validate the SC/RQ/TC relation tables against the upstream canon.

    V2  every edge endpoint resolves to an existing node (no dangling reference)
    V3  no duplicate edge for a declared (src, dst) pair
    V4  edge attribute values fall inside their declared domain
    V6  the truth source contains no derived columns
    V8  nodes with no edge at all (bidirectional orphans)      -> finding
    V9  declared SC x RQ vs derived RQ -> SC mismatch           -> finding
    V10 P0 requirements missing failure/recovery coverage       -> finding
    V11 SC with no primary persona, or persona embodied by no SC -> finding
    V12 primary: true 只能標在 role: essential 的邊上            -> error
    V13 同一條需求最多一條 primary: true                          -> error
    V14 FR 在拆解樹上判不出 parent（無唯一 essential／無 primary／非 global） -> finding

Errors block generation. Findings do not block, but are always printed and
carried into 規格統控規劃書 ② 缺口清單 -- a gap that blocks generation just gets
filled with fake data, which is worse than the gap.

Usage:
    python3 _validate_relations.py            # report
    python3 _validate_relations.py --strict   # exit 1 on findings too
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field

import _canon as C


@dataclass
class Finding:
    rule: str       # V8 / V9 / V10 ...
    subject: str    # the node the gap is about -- becomes the row key downstream
    message: str
    owner: str      # who can close it. A gap with no owner never closes.


@dataclass
class Report:
    errors: list[str] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)

    def error(self, msg: str) -> None:
        self.errors.append(msg)

    def finding(self, rule: str, subject: str, message: str, owner: str) -> None:
        self.findings.append(Finding(rule, subject, message, owner))

    def by_rule(self, rule: str) -> list[Finding]:
        return [f for f in self.findings if f.rule == rule]


# --------------------------------------------------------------------------

def check_sc_rq(rep: Report, scenarios: dict, reqs: dict, rel: C.Relations) -> dict:
    """V2/V3/V4/V6/V8 over the SC x RQ table. Returns sc -> {requirement}."""
    if not rel.sc_rq:
        rep.error("sc_requires_rq.yaml: 沒有任何邊，脊椎不存在")
        return {}

    by_sc: dict[str, set] = {}
    seen: set[tuple[str, str]] = set()
    covered: set[str] = set()

    for i, e in enumerate(rel.sc_rq, 1):
        loc = f"sc_requires_rq.yaml:edge#{i}"
        sc, rq, role = e.get("scenario"), e.get("requirement"), e.get("role")

        for stray in C.DERIVED_KEYS & set(e):
            rep.error(f"{loc} 出現推導欄 `{stray}`（V6：推導欄不得手寫）")
        if sc not in scenarios:
            rep.error(f"{loc} scenario `{sc}` 不存在於 28_Scenarios.md（V2）")
        if rq not in reqs:
            rep.error(f"{loc} requirement `{rq}` 不存在於 04_SRS/05_NFR（V2）")
        if role not in C.ROLE_DOMAIN:
            rep.error(f"{loc} role `{role}` 不在值域 {sorted(C.ROLE_DOMAIN)}（V4）")
        if not str(e.get("note") or "").strip():
            rep.error(f"{loc} 缺 note——說不出憑什麼成立的邊不該存在")
        if (sc, rq) in seen:
            rep.error(f"{loc} 重複的邊 ({sc}, {rq})（V3）")
        seen.add((sc, rq))

        by_sc.setdefault(sc, set()).add(rq)
        covered.add(rq)

    for sc in scenarios:
        if sc not in by_sc:
            rep.finding("V8", sc, "旅程存在但沒說需要什麼需求", "SA")
        elif not rel.reqs_of(sc, "essential"):
            rep.finding("V8", sc, "沒有任何 essential 需求（關鍵路徑未定義）", "SA")

    for rq, title in reqs.items():
        if rq in covered or rel.global_matches(rq):
            continue
        rep.finding("V8", rq,
                    f"沒有任何旅程需要它，也沒宣告 scope: global（{title[:28]}）", "SA")

    return by_sc


def check_rq_tc(rep: Report, reqs: dict, rel: C.Relations) -> None:
    """V2/V3/V4 over the RQ x TC table."""
    if not rel.rq_tc:
        rep.finding("V2", "rq_verified_by_tc.yaml", "關聯表不存在，覆蓋缺口無法計算", "QA")
        return

    seen: set[tuple[str, str]] = set()
    for i, e in enumerate(rel.rq_tc, 1):
        loc = f"rq_verified_by_tc.yaml:edge#{i}"
        rq, tc, kind = e.get("requirement"), e.get("case"), e.get("kind")
        if rq not in reqs:
            rep.error(f"{loc} requirement `{rq}` 不存在（V2）")
        if kind not in C.KIND_DOMAIN:
            rep.error(f"{loc} kind `{kind}` 不在值域 {sorted(C.KIND_DOMAIN)}（V4）")
        if (rq, tc) in seen:
            rep.error(f"{loc} 重複的邊 ({rq}, {tc})（V3）")
        seen.add((rq, tc))

    for d in rel.tc_dangling:
        rep.finding("V2", d["requirement"],
                    f"指定了不存在的案例 {d['designated_case']}（命名慣例偽裝成關聯）", "QA")
    for u in rel.rq_unresolved:
        rep.finding("V7", u["requirement"],
                    f"只有測試設計、還沒有具體案例（{str(u.get('note', ''))[:40]}）", "QA")


def check_coverage(rep: Report, scenarios: dict, by_sc: dict, rel: C.Relations) -> None:
    """V9 and V10 -- the two rules the whole apparatus exists to compute.

    V9 is the difference between two answers to the same question:

        declared   SC x RQ            this journey *should* verify that requirement
        derived    RQ x TC o TC x SC  this journey *actually* runs a case for it

    A requirement declared essential to a journey whose acceptance script runs no
    case for it is the single most under-reported state in spec governance -- and
    in a table with one 「對應場景」 column it can never surface at all.
    """
    if not rel.sc_tc:
        rep.finding("V9", "sc_verified_by_tc.yaml", "驗收腳本關聯表不存在，V9 無法計算", "QA")
        return

    for i, s in enumerate(rel.sc_tc, 1):
        if s.get("scenario") not in scenarios:
            rep.error(f"sc_verified_by_tc.yaml:script#{i} scenario `{s.get('scenario')}` 不存在（V2）")

    for n in rel.sc_no_script:
        rep.finding("V9", n["scenario"],
                    f"（{n.get('priority', '?')}）完全沒有驗收腳本——{n.get('note', '')}", "QA")

    for sc in sorted(by_sc):
        script = rel.script_cases(sc)
        if not script:
            continue
        for rq in sorted(by_sc[sc]):
            covering = set(rel.cases_of(rq))
            if covering and not (covering & script):
                rep.finding("V9", f"{sc} × {rq}",
                            f"宣告需要但驗收腳本沒跑到任何驗證它的案例（{sorted(covering)[:3]}）",
                            "QA")

    p0 = {rq for sc, meta in scenarios.items() if meta["priority"] == "P0"
          for rq in by_sc.get(sc, set())}
    for rq in sorted(p0):
        kinds = rel.kinds_of(rq)
        if not kinds:
            rep.finding("V10", rq, "P0 旅程需要，但完全沒有測試案例", "QA")
        elif not kinds & {"failure", "recovery"}:
            rep.finding("V10", rq, f"P0 旅程需要，但只有 {sorted(kinds)}，缺 failure/recovery", "QA")


def check_sc_persona(rep: Report, scenarios: dict, personas: dict, rel: C.Relations) -> None:
    """V2/V3/V4/V11 over the SC x Persona table -- the 'who' end of the graph.

    V11 finds the two ways this edge rots: a journey nobody is declared to live
    through (no primary persona -> the BDD `As a` has no subject), and a persona
    that appears in no journey (a card that reads well but carries no weight).
    """
    if not rel.sc_per:
        rep.finding("V11", "sc_embodies_persona.yaml",
                    "Persona 關聯表不存在，追溯鏈「誰」那一端未閉合", "BA")
        return

    seen: set[tuple[str, str]] = set()
    embodied: set[str] = set()
    for i, e in enumerate(rel.sc_per, 1):
        loc = f"sc_embodies_persona.yaml:edge#{i}"
        sc, per, role = e.get("scenario"), e.get("persona"), e.get("role")
        for stray in C.DERIVED_KEYS & set(e):
            rep.error(f"{loc} 出現推導欄 `{stray}`（V6）")
        if sc not in scenarios:
            rep.error(f"{loc} scenario `{sc}` 不存在於 28_Scenarios.md（V2）")
        if per not in personas:
            rep.error(f"{loc} persona `{per}` 不存在於 06_UX §3（V2）")
        if role not in C.PERSONA_ROLE_DOMAIN:
            rep.error(f"{loc} role `{role}` 不在值域 {sorted(C.PERSONA_ROLE_DOMAIN)}（V4）")
        if not str(e.get("note") or "").strip():
            rep.error(f"{loc} 缺 note——說不出這條旅程憑什麼由這個 Persona 感知")
        if (sc, per) in seen:
            rep.error(f"{loc} 重複的邊 ({sc}, {per})（V3）")
        seen.add((sc, per))
        embodied.add(per)

    for sc in scenarios:
        if not rel.personas_of(sc):
            rep.finding("V11", sc, "旅程沒有任何 Persona（誰在走這段旅程？）", "BA")
        elif not rel.personas_of(sc, "primary"):
            rep.finding("V11", sc, "旅程只有 secondary Persona，缺主要感知者", "BA")

    for per, name in personas.items():
        if per not in embodied:
            rep.finding("V11", per, f"Persona 未被任何旅程體現（裝飾性節點：{name[:20]}）", "BA")


def check_primary_axis(rep: Report, reqs: dict, rel: C.Relations) -> None:
    """V12/V13/V14 —— 拆解樹上的 parent 判不判得出來。

    追溯是 M:N（一條需求可以同時服務多條旅程），拆解樹上的 parent 卻只能有一個。
    `primary` 這個可選欄只解決這個載體落差，它不是第四條追溯邊——所以兩個邊界必須守住：
    只能標在關鍵路徑（essential）的邊上（V12），且一條需求只能有一個（V13）。
    兩者都是 error：一個標錯位置或標了兩次的宣告，等於把 parent 交給讀取順序決定。

    V14 是這條軸的缺口面：機器推不出、人也還沒宣告的 FR，在拆解樹上會落進「沒有 parent」
    那一組。列為 finding 而非 error，理由同 V8——擋下生成只會逼人隨手挑一條旅程填平，
    而掛錯旅程的需求比沒掛的更難發現：它在畫面上長得跟正確答案一模一樣。
    """
    declared: dict[str, list[str]] = {}
    for i, e in enumerate(rel.sc_rq, 1):
        if "primary" not in e:
            continue
        loc = f"sc_requires_rq.yaml:edge#{i}"
        value, sc, rq, role = e.get("primary"), e.get("scenario"), e.get("requirement"), e.get("role")
        if not isinstance(value, bool):
            # 寫成 "true" 或直接寫 SC 代號都會被判定邏輯靜默忽略，
            # 結果是「明明宣告了卻還躺在 V14 清單裡」——那種錯沒有人查得出來。
            rep.error(f"{loc} primary `{value}` 不是布林值（V12：值域只有 true / false）")
            continue
        if value is False:
            continue
        if role != "essential":
            rep.error(f"{loc} primary: true 標在 role `{role}` 的邊上"
                      f"（V12：parent 只能是這條需求的關鍵路徑，supporting 撐不起拆解樹）")
            continue
        if not str(rq).startswith("FR-"):
            # NFR 一律掛地板 Feature，不看 SC 邊（規格 §3.4）。標了不會生效，
            # 而一個永遠不生效的宣告會讓人以為問題已經解決。
            rep.error(f"{loc} primary: true 標在 `{rq}` 上（V12：NFR 不掛旅程，一律走地板 Feature）")
            continue
        declared.setdefault(rq, []).append(sc)

    for rq, scs in sorted(declared.items()):
        if len(scs) > 1:
            rep.error(f"sc_requires_rq.yaml {rq} 有 {len(scs)} 條 primary: true（{'、'.join(scs)}）"
                      f"（V13：parent 是單值，宣告兩個等於沒宣告）")

    global_ids = C.global_requirements()
    for rq in sorted(reqs):
        if not rq.startswith("FR-"):
            continue
        if C.primary_scenario(rq) or rq in global_ids:
            continue
        # 一律 .get()：缺欄的邊由 V2 報成 error，不該在這裡先 KeyError 炸掉整份報告。
        mine = [e for e in rel.sc_rq if e.get("requirement") == rq]
        essential = sorted({str(e.get("scenario")) for e in mine if e.get("role") == "essential"})
        supporting = sorted({str(e.get("scenario")) for e in mine if e.get("role") == "supporting"})
        if essential:
            detail = (f"{len(essential)} 條 essential 邊（{'、'.join(essential)}）分不出主旅程，"
                      f"請於其中一條標 primary: true")
        else:
            detail = (f"沒有任何 essential 邊（只有 supporting：{'、'.join(supporting) or '無'}），"
                      f"要先把某一條升為 essential 才能標 primary，或改宣告 global")
        rep.finding("V14", rq, f"拆解樹上會沒有 parent——{detail}", "BA")


# --------------------------------------------------------------------------

def run() -> tuple[Report, dict]:
    """Validate and return (report, counters). Importable -- no printing."""
    rep = Report()
    scenarios = {s.sc_id: {"name": s.name, "priority": s.priority} for s in C.load_scenarios()}
    reqs = {r.req_id: r.name for r in C.load_requirements()}
    reqs.update({n.req_id: n.name for n in C.load_nfrs()})
    personas = {p.per_id: p.name for p in C.load_personas()}
    rel = C.load_relations()

    if not scenarios:
        rep.error("28_Scenarios.md 解析不到任何 SC（§1 清單表格式改了？）")
    if not reqs:
        rep.error("04_SRS/05_NFR 解析不到任何 RQ")
    if not personas:
        rep.error("06_UX §3 解析不到任何 Persona（PER-* 格式改了？）")

    by_sc = check_sc_rq(rep, scenarios, reqs, rel)
    check_rq_tc(rep, reqs, rel)
    check_coverage(rep, scenarios, by_sc, rel)
    check_sc_persona(rep, scenarios, personas, rel)
    check_primary_axis(rep, reqs, rel)

    counters = {
        "sc": len(scenarios),
        "persona": len(personas),
        "fr": sum(1 for r in reqs if r.startswith("FR-")),
        "nfr": sum(1 for r in reqs if r.startswith("NFR-")),
        "sc_per": len(rel.sc_per),
        "sc_rq": len(rel.sc_rq),
        "rq_tc": len(rel.rq_tc),
        "sc_tc": sum(len(s.get("cases") or []) for s in rel.sc_tc),
        "rq_covered_by_sc": len({e["requirement"] for e in rel.sc_rq}),
        "rq_covered_by_tc": len({e["requirement"] for e in rel.rq_tc}),
        "rq_total": len(reqs),
        # 拆解軸的健康度。追溯覆蓋率再高，FR 掛不進樹一樣看不出旅程進度。
        "fr_with_parent": sum(1 for r in reqs if C.primary_scenario(r)),
        "fr_on_floor": len({r for r in reqs if r.startswith("FR-")} & C.global_requirements()),
    }
    return rep, counters


def main() -> int:
    rep, n = run()
    print("節點：")
    print(f"  SC {n['sc']}  Persona {n['persona']}  FR {n['fr']}  NFR {n['nfr']}")
    print("邊：")
    print(f"  SC x Persona {n['sc_per']:>4} 條")
    print(f"  SC x RQ  {n['sc_rq']:>4} 條（涵蓋 {n['rq_covered_by_sc']}/{n['rq_total']} 條需求）")
    print(f"  RQ x TC  {n['rq_tc']:>4} 條（涵蓋 {n['rq_covered_by_tc']}/{n['rq_total']} 條需求）")
    print(f"  SC x TC  {n['sc_tc']:>4} 條")
    print("拆解軸（parent）：")
    print(f"  FR 掛得上旅程 {n['fr_with_parent']}/{n['fr']} 條"
          f"（另 {n['fr_on_floor']} 條宣告 global 走地板；其餘見 V14）")

    if rep.errors:
        print(f"\nERROR ({len(rep.errors)}) —— 擋下生成")
        for m in rep.errors:
            print(f"  x {m}")
    if rep.findings:
        print(f"\nFINDING ({len(rep.findings)}) —— 不擋生成，但必須進規劃書 ② 缺口清單")
        for f in rep.findings:
            print(f"  ! {f.rule} {f.subject} {f.message}")
    if not rep.errors and not rep.findings:
        print("\n全部通過。")

    if rep.errors:
        return 1
    if rep.findings and "--strict" in sys.argv:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
