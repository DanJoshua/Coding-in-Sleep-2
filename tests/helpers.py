from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from types import SimpleNamespace

from sleepcode.models import DiffStats, Node, RunConfig
from sleepcode.util import write_text


def make_config(root: Path, **overrides) -> RunConfig:
    repo = overrides.pop("repo", root / "repo")
    run_dir = overrides.pop("run_dir", root / "runs" / "run")
    config = RunConfig(
        repo=repo,
        task="Implement the task.\n",
        task_source=str(root / "task.md"),
        guidelines="Keep it simple.\n",
        guidelines_source=str(root / "guideline.md"),
        base="HEAD",
        out_dir=root / "runs",
        run_id="run",
        run_dir=run_dir,
        **overrides,
    )
    return config


class FakeGit:
    def __init__(self, config: RunConfig):
        self.config = config
        self.created: list[tuple[int, str, int | None]] = []

    def ensure_repo_ready(self) -> None:
        self.config.repo.mkdir(parents=True, exist_ok=True)

    def create_worktree(self, node: Node, parent: Node | None) -> tuple[Path, str]:
        worktree = self.config.run_dir / "worktrees" / f"node-{node.id:03d}"
        worktree.mkdir(parents=True, exist_ok=True)
        write_text(worktree / "app.py", "value = 1\n")
        self.created.append((node.id, node.kind, None if parent is None else parent.id))
        return worktree, f"branch-{node.id}"

    def capture_diff(self, node: Node) -> DiffStats:
        patch_path = node.artifact_dir / "diff.patch"
        stat_path = node.artifact_dir / "diffstat.txt"
        write_text(patch_path, "diff --git a/app.py b/app.py\n+value = 2\n")
        write_text(stat_path, " app.py | 1 +\n")
        return DiffStats(files=1, lines=1, patch_path=patch_path, stat_path=stat_path)

    def cleanup_worktrees(self) -> None:
        shutil.rmtree(self.config.run_dir / "worktrees", ignore_errors=True)


class FakeValidator:
    def __init__(self, status: str = "pass", returncode: int = 0):
        self.status = status
        self.returncode = returncode

    def run(self, worktree: Path, artifact_dir: Path):
        log_path = artifact_dir / "validation.log"
        write_text(log_path, "ok\n")
        write_text(
            artifact_dir / "validation.json",
            json.dumps({"status": self.status, "returncode": self.returncode, "metadata": {"kind": "fake"}}),
        )
        return SimpleNamespace(
            command=["fake-validation"],
            status=self.status,
            returncode=self.returncode,
            log_path=log_path,
            metadata={"kind": "fake"},
        )


class FakeAgents:
    def __init__(
        self,
        vote_actions: dict[int, str] | None = None,
        expostulation_entries: list[dict[str, object]] | None = None,
    ):
        self.vote_actions = vote_actions or {}
        self.expostulation_entries = expostulation_entries or []
        self.calls: list[dict[str, object]] = []

    def run(
        self,
        *,
        agent: str,
        role: str,
        worktree: Path,
        prompt: str,
        artifact_dir: Path,
        final_filename: str,
        sandbox: str,
        reasoning_effort: str | None = None,
        plan_mode: bool = False,
        extra_context_dirs: tuple[Path, ...] = (),
    ):
        artifact_dir.mkdir(parents=True, exist_ok=True)
        final_path = artifact_dir / final_filename
        log_path = artifact_dir / f"{role}.{agent}.log"
        self.calls.append(
            {
                "agent": agent,
                "role": role,
                "sandbox": sandbox,
                "reasoning_effort": reasoning_effort,
                "plan_mode": plan_mode,
                "extra_context_dirs": extra_context_dirs,
                "prompt": prompt,
            }
        )
        if role == "voter":
            decisions = [
                {"node_id": node_id, "action": action, "evidence": [f"node {node_id} evidence"]}
                for node_id, action in sorted(self.vote_actions.items())
            ]
            write_text(final_path, json.dumps({"decisions": decisions}))
        elif role == "final_report":
            write_text(final_path, "# final\n\nRecommended node: 2\n")
        elif role == "assessment":
            write_text(final_path, "Task reading\nBrief.\n")
        elif role == "reviewer":
            write_text(
                final_path,
                "Verdict\nready\n\n"
                "Suggested next action: drop\n\n"
                '```json\n{"suggested_next_action":"drop","findings":[]}\n```\n',
            )
        elif role == "expostulator":
            write_text(final_path, json.dumps({"entries": self.expostulation_entries}))
        else:
            write_text(final_path, "Summary\nChanged app.py.\n\nSuggested next action\nfix\n")
            write_text(worktree / "app.py", "value = 2\n")
        write_text(log_path, "log\n")
        return SimpleNamespace(
            command=[agent, role],
            returncode=0,
            log_path=log_path,
            final_message_path=final_path,
            timed_out=False,
            reason=None,
        )


class TempDirTestCase:
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()


def run_git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", "-C", str(repo), *args], text=True, capture_output=True, check=True)
