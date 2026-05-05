from __future__ import annotations

import subprocess
import unittest

from sleepcode.git import GitWorktreeManager
from sleepcode.models import Node
from sleepcode.util import write_text

from tests.helpers import TempDirTestCase, make_config


class GitWorktreeTests(TempDirTestCase, unittest.TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.repo = self.root / "repo"
        self.repo.mkdir()
        subprocess.run(["git", "-C", str(self.repo), "init"], check=True, text=True, capture_output=True)
        subprocess.run(["git", "-C", str(self.repo), "config", "user.email", "test@example.com"], check=True)
        subprocess.run(["git", "-C", str(self.repo), "config", "user.name", "Test"], check=True)
        write_text(self.repo / "app.py", "value = 1\n")
        subprocess.run(["git", "-C", str(self.repo), "add", "app.py"], check=True)
        subprocess.run(["git", "-C", str(self.repo), "commit", "-m", "initial"], check=True, text=True, capture_output=True)

    def test_fixer_applies_parent_patch_but_rebuilder_starts_from_base(self) -> None:
        config = make_config(self.root, repo=self.repo)
        manager = GitWorktreeManager(config)
        manager.ensure_repo_ready()
        root_node = Node(
            id=1,
            parent_id=None,
            depth=0,
            kind="root",
            status="complete",
            branch="HEAD",
            worktree=self.repo,
            artifact_dir=config.run_dir / "nodes" / "node-001",
        )
        builder = Node(
            id=2,
            parent_id=1,
            depth=1,
            kind="builder",
            status="prepared",
            branch="",
            worktree=config.run_dir / "worktrees" / "node-002",
            artifact_dir=config.run_dir / "nodes" / "node-002",
        )
        builder_worktree, _ = manager.create_worktree(builder, root_node)
        builder = Node(**{**builder.__dict__, "worktree": builder_worktree})
        write_text(builder_worktree / "app.py", "value = 2\n")
        manager.capture_diff(builder)

        fixer = Node(
            id=3,
            parent_id=2,
            depth=2,
            kind="fixer",
            status="prepared",
            branch="",
            worktree=config.run_dir / "worktrees" / "node-003",
            artifact_dir=config.run_dir / "nodes" / "node-003",
        )
        rebuilder = Node(
            id=4,
            parent_id=2,
            depth=2,
            kind="rebuilder",
            status="prepared",
            branch="",
            worktree=config.run_dir / "worktrees" / "node-004",
            artifact_dir=config.run_dir / "nodes" / "node-004",
        )

        fixer_worktree, _ = manager.create_worktree(fixer, builder)
        rebuilder_worktree, _ = manager.create_worktree(rebuilder, builder)

        self.assertEqual((fixer_worktree / "app.py").read_text(encoding="utf-8"), "value = 2\n")
        self.assertEqual((rebuilder_worktree / "app.py").read_text(encoding="utf-8"), "value = 1\n")


if __name__ == "__main__":
    unittest.main()
