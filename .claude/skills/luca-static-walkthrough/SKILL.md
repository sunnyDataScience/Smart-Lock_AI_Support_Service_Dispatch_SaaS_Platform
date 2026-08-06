---
name: luca-static-walkthrough
description: 靜態走查 — 不啟動任何服務，逐條把驗收條件比對到原始碼，每案產出一份帶 `檔案:行號` 證據與四值判定的文件，最後匯成可統計的索引。用於驗收前盤點實作缺口、接手陌生系統時建立事實基線，或規格與程式碼疑似漂移時。
disable-model-invocation: true
---

<!-- 繁中摘要：本技能把「靜態走查」流程固定下來。走查＝只讀原始碼、不跑服務，逐條驗證驗收條件，產出證據文件。核心紀律是四值判定（含「無法靜態判定」）、零命中即證據、並陳不裁定、只產證據不改東西。 -->

# Static Walkthrough

Verify acceptance criteria against source code **without running the system**. Produce one evidence document per case, then an index that can be tallied.

A walkthrough is an **observation**, not a repair. See "Report boundary" — it is the rule that makes the output trustworthy.

## What you produce

| Artifact | Path | Purpose |
|---|---|---|
| Per-case document | `<output-dir>/<CASE-ID>.md` | Evidence and verdict for one criterion set |
| Index | `<output-dir>/README.md` | Verdict tally, per-batch tables, one-sentence fact per case |

Structure of both files: [DOC-SCHEMA.md](DOC-SCHEMA.md). Batching, dedup and the progress ledger: [BATCH.md](BATCH.md).

## Step 0 — Normalize the input (mandatory, may fail)

The input can be anything enumerable: test cases, acceptance criteria, spec clauses, SLA terms, a PRD section.

Convert it into a **criteria list**: each entry has an ID and one or more decision criteria that are *individually checkable against code*.

**If you cannot produce that list, stop and ask the user.** Do not proceed with prose-style requirements. A walkthrough driven by prose degrades into reading code and writing impressions — it produces confident text with no verifiable claims.

Record the source of the criteria verbatim in each document. Never paraphrase the criteria you are judging against.

## Step 1 — Template case first (mandatory)

Walk **one** case end to end. Show it to the user. Get confirmation on the format before doing any others.

This is the only way to avoid discovering at case 40 that the schema is wrong. The template case stays in the output as a reference; mark it as such in the index.

## Step 2 — Batch the rest

Follow [BATCH.md](BATCH.md). The rules that matter most: group by user journey or feature area, and **never produce two documents for the same case ID** — later batches cite the existing document instead.

## Step 3 — Build the index

Follow the index format in [DOC-SCHEMA.md](DOC-SCHEMA.md). Tally verdicts from the actual documents, not from memory.

## Evidence discipline

These four rules are the substance of the method. Everything else is formatting.

### 1. Four verdicts, including "cannot determine"

`一致` / `不一致` / `部分實作` / `無法靜態判定`

`無法靜態判定` is for criteria that are runtime measurements (p95 latency, error rates, load behaviour) or that need data you do not have. **Use it.** A method that forces a verdict on everything produces confident garbage on the cases it cannot see.

### 2. Zero hits is evidence

When a criterion names an identifier — a field, an event name, an error code, an endpoint — search for it and report the result as a fact:

```
`technician.assignment_accepted` 在 api/web/SQL/agent 全數零命中；實際發出的是 `work_order.accepted`
```

State **what you searched and where**. A zero-hit result across a stated scope is the strongest evidence a static walkthrough can produce, and it is usually what turns a verdict into `不一致`.

### 3. Present both sides; do not adjudicate

When the spec, the schema, the API definition and the code disagree, write down what each one says, cite each with `檔案:行號`, and stop:

> 此處僅並陳兩者，不裁定何者應修正。

You are establishing facts. Deciding which artifact is wrong is a separate decision with different stakeholders. Adjudicating inside a walkthrough hides the disagreement behind your judgement.

### 4. Separate static evidence from execution evidence

You may run existing tests if they run offline, and cite their output. When you do, state **which criterion the execution evidence supports** and which criteria rest on source reading alone. A reader must be able to tell the two apart.

Two things must never be recorded as product defects:

- **Environment friction** — missing local tooling, platform limitations, unapplied schema. Record these in a separate section explicitly labelled as non-defects.
- **Flaky tests** — record the observed run-to-run difference, then apply rule 3 and do not adjudicate.

## Report boundary

While walking through:

- **Do not** modify the code under walkthrough
- **Do not** modify the specs, docs or canonical documents you are comparing against
- **Do not** open change requests or fix "obvious" small defects

Every document pins the commit it was walked at. If the code moves while you walk it, the evidence no longer corresponds to any version, and the whole batch becomes unciteable.

The deliverable is the list of `不一致` cases in the index. That list is the **input** to whatever change process the project uses — it is not the change itself.

## Completion criteria

- [ ] Every case in the criteria list has a verdict, or is explicitly listed as deferred with a reason
- [ ] Every document states its walkthrough commit
- [ ] Every verdict of `不一致` names the specific identifier or behaviour that differs
- [ ] The index tally is computed from the documents and matches their count
- [ ] No file outside `<output-dir>` was modified
