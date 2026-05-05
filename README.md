# sleepcode

`sleepcode` orchestrates bounded non-interactive coding-agent sessions over
isolated git worktrees. It receives a task and guidelines file, grows a small
search tree of builder, fixer, and rebuilder candidates, then writes a final
report for human inspection.

It is meant for an overnight or background run: multiple fresh agent sessions,
connected by lean reports instead of one long conversation.

```bash
sleepcode run --repo /path/to/repo --task-file /path/to/task.md --guidelines-file /path/to/guideline.md
sleepcode resume --run-dir runs/<run-id>
```

The original target repository is assumed to have no tests. Candidate agents may
add tests under `.sleepcode/tests/`; sleepcode runs those tests when present.

## Basic Usage

The target repository must be a clean git repo before a run starts.

Paths passed to `--repo`, `--task-file`, `--guidelines-file`, and `--out` are
resolved relative to the shell directory where you run `sleepcode`, unless they
are absolute paths. The task and guidelines files do not need to live inside the
target repository.

For example, if this workspace contains `OmegaWiki/`, `task.md`, and
`guideline-for-cs.md`, run from the workspace root:

```bash
cd /home/woden/CS2

sleepcode run \
  --repo OmegaWiki \
  --task-file task.md \
  --guidelines-file guideline-for-cs.md
```

The same command with absolute paths:

```bash
sleepcode run \
  --repo /home/woden/CS2/OmegaWiki \
  --task-file /home/woden/CS2/task.md \
  --guidelines-file /home/woden/CS2/guideline-for-cs.md
```

Artifacts are written under `runs/<run-id>/` by default. The most useful files
are:

- `final_report.md`: morning report and recommended node.
- `final_report.json`: structured run summary.
- `sleepcode.sqlite3`: durable orchestration state and checkpoints.
- `nodes/node-NNN/`: prompts, reports, diffs, validation logs, and raw agent logs.
- `worktrees/node-NNN/`: candidate repositories for inspection.

Resume a run with:

```bash
sleepcode resume --run-dir runs/20260504-170000
```

Resume does not continue old agent conversations. It starts fresh bounded
sessions from saved reports and checkpoints.

## Choosing Search Parameters

The defaults are intentionally modest:

```bash
--max-nodes 8
--max-depth 3
--jobs 2
--builder-fanout 3
--fixer-fanout 2
--rebuilder-fanout 1
```

`--max-nodes` is the total budget, including the root node. With the default
`8`, sleepcode can create root plus up to seven candidate nodes.

`--builder-fanout` controls how many independent first attempts are seeded from
the untouched base. Increase it when the task has several plausible designs.
Decrease it for small, localized tasks.

`--fixer-fanout` is per parent node. It limits how many minimal repair attempts a
candidate can receive across the whole run.

`--rebuilder-fanout` is also per parent node. It limits how many fresh rebuilds
can be attempted from a candidate's intent and reports, starting again from the
base instead of patching the parent worktree.

`--max-depth` limits how far the tree can go below root. Builders are depth 1.
Fixers and rebuilders are deeper children. Use a low depth for simple changes;
use a higher depth when you expect several rounds of review and repair.

`--jobs` is concurrency only. It does not reduce the total budget or fanout. For
example, `--jobs 1 --builder-fanout 3` still allows three builders; they just run
one at a time.

Builder seeding happens before deeper expansion when possible. After that,
agent voting decides whether each candidate should be fixed, rebuilt, or dropped.

## Suggested Profiles

Small, cheap run:

```bash
cd /home/woden/CS2

sleepcode run \
  --repo OmegaWiki \
  --task-file task.md \
  --guidelines-file guideline-for-cs.md \
  --max-nodes 4 \
  --max-depth 2 \
  --builder-fanout 2 \
  --fixer-fanout 1 \
  --rebuilder-fanout 0 \
  --jobs 1
```

Default overnight run:

```bash
cd /home/woden/CS2

sleepcode run \
  --repo OmegaWiki \
  --task-file task.md \
  --guidelines-file guideline-for-cs.md
```

Broader design search:

```bash
cd /home/woden/CS2

sleepcode run \
  --repo OmegaWiki \
  --task-file task.md \
  --guidelines-file guideline-for-cs.md \
  --max-nodes 12 \
  --builder-fanout 4 \
  --fixer-fanout 2 \
  --rebuilder-fanout 2 \
  --jobs 3
```

Codex-only run:

```bash
cd /home/woden/CS2

sleepcode run \
  --repo OmegaWiki \
  --task-file task.md \
  --guidelines-file guideline-for-cs.md \
  --agents codex
```

## Agents

The default is:

```bash
--agents codex,kimi
```

Worker nodes are weighted toward Codex: Codex xhigh, Codex high, Kimi, then
repeat. Review tries to use a different agent from the worker when possible.
Voting uses multiple agent views and requires concrete evidence for `fix`,
`rebuild`, or `drop`.

Use `--agents codex` for a faster or simpler run. Use `--agents kimi` only when
you specifically want Kimi to handle all roles.

`--model` passes a model override to supported agents.

## Validation

By default, sleepcode assumes the original target repo has no tests.

Validation order:

1. If `--test-cmd` is supplied, run that command.
2. Else, if a candidate created `.sleepcode/tests/test*.py`, run:
   `python -m unittest discover -s .sleepcode/tests`
3. Else, for Python repos, run a compile-only smoke check and report it as
   `smoke`, not a full pass.
4. Else, report validation as `unknown`.

Use `--test-cmd` when the target repo has a known reliable command:

```bash
cd /home/woden/CS2

sleepcode run \
  --repo OmegaWiki \
  --task-file task.md \
  --guidelines-file guideline-for-cs.md \
  --test-cmd "python -m pytest"
```

## After The Run

Sleepcode does not merge, commit, or push anything. It leaves candidate changes
in separate worktrees and writes patches under the run artifacts. A human still
chooses what to accept.

Start with the final report:

```bash
less runs/20260504-170000/final_report.md
```

Find the recommended node, for example `node-008`, then inspect its artifacts:

```bash
less runs/20260504-170000/nodes/node-008/worker_report.md
less runs/20260504-170000/nodes/node-008/review_report.md
less runs/20260504-170000/nodes/node-008/validation.log
git -C runs/20260504-170000/worktrees/node-008 diff HEAD
```

Apply the patch to the real target repo only after inspection. Use a fresh branch
based on the same base ref that sleepcode used:

```bash
cd /home/woden/CS2/OmegaWiki
git switch -c accept-sleepcode-node-008

git apply --check /home/woden/CS2/runs/20260504-170000/nodes/node-008/diff.patch
git apply --index /home/woden/CS2/runs/20260504-170000/nodes/node-008/diff.patch
```

`git apply --check` verifies that the patch can apply cleanly. `git apply
--index` applies it and stages the result. If you prefer to review unstaged
changes first, use `git apply` instead of `git apply --index`.

If the target repository moved on after sleepcode started, a patch may fail
because the context no longer matches. In that case, try a three-way apply:

```bash
git apply --3way /home/woden/CS2/runs/20260504-170000/nodes/node-008/diff.patch
```

Then resolve any conflicts as ordinary git conflicts.

After applying, run the target repo checks yourself:

```bash
git diff --cached
python3 tools/discover.py from-venue --venue neurips --year 2024 --wiki-root wiki --limit 3 --markdown
```

If the candidate patch includes `.sleepcode/tests/`, decide whether to keep those
tests, move their useful assertions into the target repo's normal test structure,
or drop them before committing. They are candidate validation scaffolding, not an
automatic merge requirement.

When satisfied:

```bash
git status
git commit -m "Add venue/year discovery"
```

When you no longer need the run artifacts, remove them manually. If you started
the run with `--cleanup-worktrees`, sleepcode removes candidate worktrees at the
end, but the reports and node artifacts remain.

## Timeouts And Worktrees

Agent timeout defaults:

```bash
--agent-timeout 3600
--agent-startup-timeout 120
--agent-idle-timeout 300
--kimi-idle-timeout 0
```

`--agent-timeout` is the maximum wall-clock time for one agent turn.
`--agent-startup-timeout` kills a turn that produces no initial output.
`--agent-idle-timeout` kills Codex turns after no output.
`--kimi-idle-timeout 0` disables Kimi idle timeout because Kimi may run
sub-agents silently for a long time.

Candidate worktrees are kept by default:

```bash
--keep-worktrees
```

Use `--cleanup-worktrees` when you only want reports and artifacts. Keeping
worktrees is usually better while the tool is young, because it lets you inspect
the recommended candidate directly.
