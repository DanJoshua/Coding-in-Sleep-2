---
name: sleepcode-review
description: Review a sleepcode candidate worktree for commit readiness. Use when evaluating uncommitted changes produced by a sleepcode worker agent. Triggers: sleepcode review, review worktree, assess changes, check readiness, node review.
---

# Sleepcode Review

## Overview

Evaluate a sleepcode candidate worktree without committing, reverting, or disturbing changes. Gather evidence from diffs, targeted validation, and baseline comparison, then return a findings-first readiness report with a machine-parseable JSON block.

## Workflow

### 1. Establish baseline

The baseline is HEAD. Confirm it with:

```bash
git rev-parse HEAD
```

### 2. Gather structural evidence

Run these non-destructive commands in the worktree:

```bash
git status --short
git diff --stat HEAD --
git diff --name-status HEAD --
git log --oneline --decorate -n 5
```

Inspect repo entry points to choose targeted checks: `pyproject.toml`, `package.json`, `Cargo.toml`, `go.mod`, `Makefile`, `justfile`, CI configs, and existing test folders.

Prefer targeted checks that cover the changed files first. Expand to broader suites when the diff is cross-cutting, touches shared infrastructure, or when a targeted failure suggests systemic risk. If no automated tests exist, run the narrowest meaningful lint, build, or validation command and state the resulting coverage gap.

### 3. Map changes to validation scope

- Which files changed and by how much?
- What validation ran? What passed? What failed? What was skipped?
- Are there untested areas that materially affect the verdict?

### 4. Assess regression risk

Read the changed code and compare old vs new behavior, not just filenames.
Look for:

- Interface drift
- Missing call-site updates
- Configuration mismatches
- Stale docs
- Weakened tests
- Risky assumptions or over-engineering

Treat missing validation as a risk signal, not proof of correctness.

### 5. Deliver verdict and machine output

First, write the human-readable report with these exact headings:

1. **Verdict**: One of `ready`, `ready with caveats`, or `not ready`.
2. **Actionable findings**: Ordered by severity. For each finding include:
   - severity: `high`, `medium`, or `low`
   - summary: one concrete sentence
   - file: affected path
   - line: approximate line number or `-` if unknown
3. **Rationale**: Why the verdict was chosen.
4. **Suggested next action**: One of `fix`, `rebuild`, or `drop`.

Then, end with a fenced JSON object exactly in this shape (no extra fields):

```json
{"suggested_next_action":"fix|rebuild|drop","findings":[{"severity":"high|medium|low","summary":"...","file":"...","line":1}]}
```

If no findings exist, use `"findings": []`.

## Constraints

- Do not commit, amend, stash, or revert.
- Do not assume HEAD is the only possible baseline unless the context says so.
- Prefer targeted checks over expensive full-suite runs.
- Keep the report evidence-based and findings-first.
