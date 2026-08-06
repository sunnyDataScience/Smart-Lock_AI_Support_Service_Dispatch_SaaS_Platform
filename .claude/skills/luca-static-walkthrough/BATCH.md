# Batching

How a walkthrough of 100+ cases actually converges. These rules came out of a batch of 130.

## 1. Template case first

Pick one case that is **representative, not easy** — it should exercise a state change, touch more than one layer, and have at least one criterion you expect to fail.

Walk it. Show it to the user. Change the schema now, while the cost is one document.

Keep it in the output and label it as the template in the index. Later documents are read against it.

## 2. Group by journey, then by prefix

Two grouping passes, in this order:

1. **By user journey / feature area** — cases that share a flow share context. Walking `SC-04 報價確認到工單成立` as a batch means one read of the quote service answers eight cases.
2. **By ID prefix** — for whatever has no journey. Group `TC-A11Y-*`, `TC-PERF-*`, `TC-COMPLIANCE-*` and walk each group together; they share a code region and a judgement style.

Batch size: what fits one coherent reading of a subsystem. In practice 6–15 cases.

## 3. Never write the same case twice

A case that belongs to three journeys still gets **one** document.

When a later batch reaches an already-walked case, do not re-walk it. Cite it in that batch's index table:

```markdown
已於前批走查、本批沿用：[TC-CS-AI-09](TC-CS-AI-09.md)（一致）、[TC-PERF-01](TC-PERF-01.md)（無法靜態判定）。
```

Label the batch header with both counts so the arithmetic stays checkable:

```markdown
### SC-02（故障報修到問題卡成立，12 支，本批新走查 9 支）
```

Without this rule a 130-case list produces roughly 160 documents, and the tally silently double-counts.

## 4. Keep a progress ledger

At the bottom of the index, an ordered list of batches. Strike through what is done.

```markdown
## 執行順序

1. ~~樣板 TC-WO-01~~（完成）
2. ~~SC-01（13 支）~~（完成）
3. SC-02（12 支，新走查 9 支）
4. 末批：無旅程歸屬者按前綴併為 A–F 六組（58 支）
```

This is what makes the work resumable across sessions and across people. Update it in the same commit as the batch it describes — a ledger updated later is a ledger nobody trusts.

## 5. Pin the baseline per batch, not per project

Long walkthroughs outlive their baseline commit. That is fine, and pretending otherwise is worse.

Record the baseline in the index at batch granularity, and in **every** document at document granularity:

```markdown
- 走查基準 commit：SC-01～SC-05 為 `c8687f5d`；SC-06～SC-09 為 `17aa40c5`；末批為 `2cfeca92`
  （各文件結果表標明自身基準）
```

When a batch's baseline moves, say so. Never retro-edit an earlier document to match a newer commit — its evidence was collected against the old one.

## 6. Recompute the tally from the documents

At the end of every batch, regenerate the index statistics by reading the verdict rows of the documents. Do not increment counters by hand.

The verdict row format is fixed precisely so this is a mechanical operation:

```bash
grep -h '^| \*\*判定\*\* |' *.md | sed 's/.*\*\*\(.*\)\*\*.*/\1/' | sort | uniq -c
```

If the total does not equal the document count, something was double-written or a document is malformed. Find it before continuing.

## 7. Parallel batches are fine; parallel schemas are not

Independent batches can be walked concurrently — they touch different code regions and different documents.

What must not diverge is the schema. Every parallel worker reads [DOC-SCHEMA.md](DOC-SCHEMA.md) and uses the canonical section names. In the batch this method came from, the final 58 documents were walked in six parallel groups and every one of them renamed its body sections — same skeleton, different labels, one document set that reads like two.

If you dispatch subagents for parallel batches, give each one the schema file explicitly and require the canonical names in its completion criteria. **Subagents walking a batch must not re-invoke this skill.**
