---
name: sleepcode-expostulate
description: Curate high-confidence reusable implementation knowledge for sleepcode runs. Use when a dedicated expostulator agent must read a node's worker report, review report, validation result, diff evidence, and current blackboard to propose validated modules, repair patterns, or pitfalls for later agents.
---

# Sleepcode Expostulate

## Purpose

Curate reusable implementation knowledge for the run blackboard. Expostulation is not a review, vote, audit log, or speculation surface. It should preserve only evidence-backed knowledge that later agents can safely reuse.

## Workflow

1. Read `manifest.md` first.
2. Read `task.md`, `guidelines.md`, `expostulation.md`, `worker_report.md`, `review_report.md`, `validation.json`, and `diffstat.txt` when present.
3. Inspect changed code only when compact artifacts point to a concrete reusable candidate or unresolved ambiguity.
4. Emit no entry unless the evidence is strong, specific, and reusable beyond the current report.

## Entry Rules

Use only these kinds:

- `validated_module`: Code that appears to implement a useful function well. Emit only when validation passed and the review does not contradict the claim.
- `repair_pattern`: A concrete fix pattern that corrected or is likely to correct a repeated implementation pitfall.
- `pitfall`: A concrete failure mode or avoidance rule grounded in observed evidence.

Do not expostulate when unsure. An empty `entries` list is a successful result.

Reject:

- vague lessons, motivational advice, or restatements of the task
- entries based only on file names, keyword matches, token overlap, or log volume
- entries without concrete affected files and evidence paths
- entries that conflict with `task.md`, `guidelines.md`, validation, or review findings

## Output

Return only a fenced JSON object in this exact shape:

```json
{"entries":[{"kind":"validated_module|repair_pattern|pitfall","title":"short reusable title","claim":"one evidence-backed claim","affected_files":["path"],"evidence_paths":["path"],"reuse_guidance":"how later agents should use or avoid this"}]}
```

If there are no high-confidence entries, return:

```json
{"entries":[]}
```

Do not edit files, commit, stash, branch, merge, or push.
