from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Callable

from .models import DiffStats, NODE_FIXER, Node, RunConfig
from .util import run_capture, write_text

RunCallable = Callable[..., subprocess.CompletedProcess[str]]


class GitWorktreeManager:
    def __init__(self, config: RunConfig, runner: RunCallable | None = None):
        self.config = config
        self.runner = runner or subprocess.run

    def ensure_repo_ready(self) -> None:
        if not self.config.repo.exists():
            raise RuntimeError(f"target repo does not exist: {self.config.repo}")
        run_capture(["git", "-C", str(self.config.repo), "rev-parse", "--git-dir"])
        run_capture(["git", "-C", str(self.config.repo), "rev-parse", "--verify", self.config.base])
        status = run_capture(["git", "-C", str(self.config.repo), "status", "--porcelain"]).stdout
        if status.strip():
            raise RuntimeError(f"target repo has uncommitted changes; clean it before running sleepcode:\n{status}")

    def branch_for_node(self, node_id: int) -> str:
        return f"sleepcode/{self.config.run_id}/node-{node_id:03d}"

    def worktree_for_node(self, node_id: int) -> Path:
        return self.config.run_dir / "worktrees" / f"node-{node_id:03d}"

    def create_worktree(self, node: Node, parent: Node | None) -> tuple[Path, str]:
        branch = self.branch_for_node(node.id)
        worktree = self.worktree_for_node(node.id)
        worktree.parent.mkdir(parents=True, exist_ok=True)
        self._run(["git", "-C", str(self.config.repo), "worktree", "add", "-b", branch, str(worktree), self.config.base])
        if node.kind == NODE_FIXER and parent is not None:
            patch_path = parent.artifact_dir / "diff.patch"
            if patch_path.exists() and patch_path.stat().st_size:
                self._run(["git", "apply", "--whitespace=nowarn", str(patch_path)], cwd=worktree)
        return worktree, branch

    def capture_diff(self, node: Node) -> DiffStats:
        node.artifact_dir.mkdir(parents=True, exist_ok=True)
        self._intent_to_add_untracked(node.worktree)
        patch_path = node.artifact_dir / "diff.patch"
        stat_path = node.artifact_dir / "diffstat.txt"
        patch = self._run(["git", "diff", "--binary", "HEAD"], cwd=node.worktree, capture_output=True).stdout
        stat = self._run(["git", "diff", "--stat", "HEAD"], cwd=node.worktree, capture_output=True).stdout
        write_text(patch_path, patch)
        write_text(stat_path, stat)
        return DiffStats(files=_count_diff_files(patch), lines=_count_diff_lines(patch), patch_path=patch_path, stat_path=stat_path)

    def cleanup_worktrees(self) -> None:
        root = self.config.run_dir / "worktrees"
        if not root.exists():
            return
        for path in sorted(root.glob("node-*")):
            self._run(["git", "-C", str(self.config.repo), "worktree", "remove", "--force", str(path)], check=False)

    def _intent_to_add_untracked(self, worktree: Path) -> None:
        result = self._run(["git", "ls-files", "--others", "--exclude-standard", "-z"], cwd=worktree, text=False, check=False, capture_output=True)
        if result.returncode != 0 or not result.stdout:
            return
        paths = [part.decode("utf-8", errors="replace") for part in result.stdout.split(b"\0") if part]
        paths = [path for path in paths if not _is_generated_path(path)]
        if paths:
            self._run(["git", "add", "-N", "--", *paths], cwd=worktree, check=False)

    def _run(self, args: list[str], *, cwd: Path | None = None, check: bool = True, text: bool = True, **kwargs):
        defaults = {"text": text}
        defaults.update(kwargs)
        if "stdout" not in defaults and "stderr" not in defaults and "capture_output" not in defaults:
            defaults["capture_output"] = True
        result = self.runner(args, cwd=cwd, check=False, **defaults)
        if check and result.returncode != 0:
            stdout = getattr(result, "stdout", "") or ""
            stderr = getattr(result, "stderr", "") or ""
            raise RuntimeError(f"command failed ({result.returncode}): {' '.join(args)}\n{stdout}\n{stderr}")
        return result


def _count_diff_files(patch: str) -> int:
    return sum(1 for line in patch.splitlines() if line.startswith("diff --git "))


def _count_diff_lines(patch: str) -> int:
    count = 0
    for line in patch.splitlines():
        if line.startswith(("+++", "---", "diff --git", "index ", "@@")):
            continue
        if line.startswith(("+", "-")):
            count += 1
    return count


def _is_generated_path(path: str) -> bool:
    parts = set(Path(path).parts)
    return "__pycache__" in parts or path.endswith((".pyc", ".pyo"))
