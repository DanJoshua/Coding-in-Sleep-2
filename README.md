# 🌙 sleepcode

<p align="center">
  <b>Tree-search orchestration for bounded non-interactive coding-agent sessions.</b>
</p>

<p align="center">
  Let agents code while you sleep. Wake up to a curated report.
</p>

<p align="center">
  <a href="README.zh-CN.md">🇨🇳 简体中文</a>
  ·
  <a href="#-features">Features</a>
  ·
  <a href="#-quick-start">Quick Start</a>
  ·
  <a href="#-usage">Usage</a>
  ·
  <a href="#-architecture">Architecture</a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.11%2B-blue?logo=python&logoColor=white" alt="Python 3.11+">
  <img src="https://img.shields.io/badge/license-MIT-green" alt="License">
</p>

---

## ✨ Features

- 🌲 **Tree Search** — Grows a search tree of builders, fixers, and rebuilders to explore multiple solution paths in parallel.
- 🔒 **Isolated Worktrees** — Every candidate runs in its own isolated Git worktree; your original repo stays untouched.
- 🤖 **Multi-Agent** — Orchestrates Codex, Kimi, and more. Workers, reviewers, and voters can be different agents.
- 📝 **Rich Reports** — Produces a final human-readable report plus structured JSON and per-node artifacts.
- ⏱️ **Overnight Friendly** — Designed for background runs. Start it, go to sleep, inspect results in the morning.
- 🧪 **Pluggable Validation** — Supports custom test commands, auto-discovered unit tests, or compile-only smoke checks.

## 🚀 Quick Start

```bash
# Install
pip install -e .

# Run
sleepcode run \
  --repo /path/to/repo \
  --task-file /path/to/task.md \
  --guidelines-file /path/to/guideline.md

# Resume a previous run
sleepcode resume --run-dir runs/<run-id>
```

Artifacts are written under `runs/<run-id>/` by default. Start with:

```bash
less runs/<run-id>/final_report.md
```

## 📖 Usage

### Basic Usage

The target repository must be a clean Git repo before a run starts.

Paths passed to `--repo`, `--task-file`, `--guidelines-file`, and `--out` are resolved relative to your shell directory unless absolute.

**Example (relative paths):**

```bash
cd /home/woden/CS2

sleepcode run \
  --repo OmegaWiki \
  --task-file task.md \
  --guidelines-file guideline-for-cs.md
```

**Same command with absolute paths:**

```bash
sleepcode run \
  --repo /home/woden/CS2/OmegaWiki \
  --task-file /home/woden/CS2/task.md \
  --guidelines-file /home/woden/CS2/guideline-for-cs.md
```

### Artifacts

| File / Directory | Description |
| :--- | :--- |
| `final_report.md` | Human-readable morning report with the recommended node |
| `final_report.json` | Structured run summary |
| `expostulation.md` | Shared per-run reusable implementation evidence |
| `sleepcode.sqlite3` | Durable orchestration state and checkpoints |
| `nodes/node-NNN/` | Prompts, reports, diffs, validation logs, raw agent logs |
| `worktrees/node-NNN/` | Candidate repositories for direct inspection |

### Search Parameters

The defaults are intentionally modest for an overnight run:

```bash
--max-nodes 8
--max-depth 3
--jobs 2
--builder-fanout 3
--fixer-fanout 2
--rebuilder-fanout 1
```

| Parameter | Description |
| :--- | :--- |
| `--max-nodes` | Total budget, including root. Default `8` means root + up to 7 candidates. |
| `--builder-fanout` | Independent first attempts seeded from the untouched base. Increase for tasks with several plausible designs. |
| `--fixer-fanout` | Per-parent repair attempts. Limits how many fixes a candidate can receive. |
| `--rebuilder-fanout` | Per-parent fresh rebuilds. Starts again from base using a candidate's intent and reports. |
| `--max-depth` | Tree depth below root. Builders are depth 1; fixers and rebuilders go deeper. |
| `--jobs` | Concurrency only. Does not reduce total budget or fanout. |

### Suggested Profiles

**Small, cheap run:**

```bash
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

**Default overnight run:**

```bash
sleepcode run \
  --repo OmegaWiki \
  --task-file task.md \
  --guidelines-file guideline-for-cs.md
```

**Broader design search:**

```bash
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

**Codex-only run:**

```bash
sleepcode run \
  --repo OmegaWiki \
  --task-file task.md \
  --guidelines-file guideline-for-cs.md \
  --agents codex
```

## 🤖 Agents

Default: `--agents codex,kimi`

- **Workers** are weighted toward Codex: `Codex xhigh → Codex high → Kimi → repeat`.
- **Review** tries to use a different agent from the worker when possible.
- **Voting** uses multiple agent views and requires concrete evidence for `fix`, `rebuild`, or `drop`.

| Flag | Description |
| :--- | :--- |
| `--agents codex` | Faster or simpler run |
| `--agents kimi` | Kimi handles all roles |
| `--model <name>` | Model override for supported agents |

## 🧪 Validation

By default, sleepcode assumes the target repo has no tests.

Validation order:

1. If `--test-cmd` is supplied, run that command.
2. Else, if a candidate created `.sleepcode/tests/test*.py`, run:
   ```bash
   python -m unittest discover -s .sleepcode/tests
   ```
3. Else, for Python repos, run a compile-only smoke check (reported as `smoke`, not a full pass).
4. Else, report validation as `unknown`.

**Custom test command:**

```bash
sleepcode run \
  --repo OmegaWiki \
  --task-file task.md \
  --guidelines-file guideline-for-cs.md \
  --test-cmd "python -m pytest"
```

## 📋 After The Run

Sleepcode does **not** merge, commit, or push. It leaves candidate changes in separate worktrees and writes patches under the run artifacts. A human still chooses what to accept.

### Inspect the recommended candidate

```bash
# Start with the final report
less runs/<run-id>/final_report.md

# Inspect the recommended node, e.g. node-008
less runs/<run-id>/nodes/node-008/worker_report.md
less runs/<run-id>/nodes/node-008/review_report.md
less runs/<run-id>/nodes/node-008/validation.log
git -C runs/<run-id>/worktrees/node-008 diff HEAD
```

### Apply the patch

Use a fresh branch based on the same base ref that sleepcode used:

```bash
cd /path/to/target-repo
git switch -c accept-sleepcode-node-008

# Verify the patch applies cleanly
git apply --check runs/<run-id>/nodes/node-008/diff.patch

# Apply and stage
git apply --index runs/<run-id>/nodes/node-008/diff.patch
```

If the target repo moved on after sleepcode started, try a three-way apply:

```bash
git apply --3way runs/<run-id>/nodes/node-008/diff.patch
```

Then resolve conflicts as ordinary Git conflicts and run your own checks.

### Cleanup

```bash
# Remove run artifacts when no longer needed
rm -rf runs/<run-id>
```

If you started the run with `--cleanup-worktrees`, sleepcode removes candidate worktrees at the end, but reports and node artifacts remain.

## ⚙️ Timeouts & Worktrees

| Flag | Default | Description |
| :--- | :--- | :--- |
| `--agent-timeout` | `3600` | Max wall-clock time for one agent turn (seconds) |
| `--agent-startup-timeout` | `120` | Kill a turn that produces no initial output |
| `--agent-idle-timeout` | `300` | Kill Codex turns after no output |
| `--kimi-idle-timeout` | `0` | Disable Kimi idle timeout (Kimi may run sub-agents silently) |

Candidate worktrees are kept by default (`--keep-worktrees`). Use `--cleanup-worktrees` when you only want reports and artifacts.

## 🏗️ Architecture

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Task &    │────▶│   Root      │────▶│  Builders   │
│ Guidelines  │     │   Node      │     │  (depth 1)  │
└─────────────┘     └─────────────┘     └──────┬──────┘
                                               │
                    ┌──────────────────────────┼──────────┐
                    ▼                          ▼          ▼
              ┌─────────┐               ┌──────────┐ ┌──────────┐
              │ Fixers  │               │ Rebuild  │ │  Vote /  │
              │(repair) │               │(restart) │ │  Drop    │
              └─────────┘               └──────────┘ └──────────┘
                    │
                    ▼
            ┌───────────────┐
            │ Final Report  │
            │ (human-ready) │
            └───────────────┘
```

The scheduler expands builder seeds first, then uses agent voting to decide whether each candidate should be fixed, rebuilt, or dropped.

## 📄 License

MIT
