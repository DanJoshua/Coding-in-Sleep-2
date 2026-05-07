from __future__ import annotations

import unittest

from sleepcode.cli import build_parser, config_from_args, load_resume_config, main, parse_agents
from sleepcode.store import SearchStore
from sleepcode.util import write_text

from tests.helpers import TempDirTestCase, make_config


class CliTests(TempDirTestCase, unittest.TestCase):
    def test_run_config_defaults(self) -> None:
        write_text(self.root / "task.md", "Task\n")
        write_text(self.root / "guideline.md", "Guideline\n")
        parser = build_parser()
        args = parser.parse_args(
            [
                "run",
                "--repo",
                str(self.root / "repo"),
                "--task-file",
                str(self.root / "task.md"),
                "--guidelines-file",
                str(self.root / "guideline.md"),
            ]
        )

        config = config_from_args(args, cwd=self.root)

        self.assertEqual(config.agents, ("codex", "kimi"))
        self.assertEqual(config.builder_fanout, 3)
        self.assertEqual(config.fixer_fanout, 2)
        self.assertEqual(config.rebuilder_fanout, 1)
        self.assertEqual(config.jobs, 2)
        self.assertEqual(config.max_nodes, 16)
        self.assertTrue(config.keep_worktrees)
        self.assertFalse(config.allow_network)
        self.assertTrue(config.run_dir.exists())

    def test_day_mode_reduces_max_nodes_to_8(self) -> None:
        write_text(self.root / "task.md", "Task\n")
        write_text(self.root / "guideline.md", "Guideline\n")
        parser = build_parser()
        args = parser.parse_args(
            [
                "run",
                "--repo",
                str(self.root / "repo"),
                "--task-file",
                str(self.root / "task.md"),
                "--guidelines-file",
                str(self.root / "guideline.md"),
                "--day-mode",
            ]
        )

        config = config_from_args(args, cwd=self.root)

        self.assertEqual(config.max_nodes, 8)

    def test_explicit_max_nodes_honored_with_day_mode(self) -> None:
        write_text(self.root / "task.md", "Task\n")
        write_text(self.root / "guideline.md", "Guideline\n")
        parser = build_parser()
        args = parser.parse_args(
            [
                "run",
                "--repo",
                str(self.root / "repo"),
                "--task-file",
                str(self.root / "task.md"),
                "--guidelines-file",
                str(self.root / "guideline.md"),
                "--day-mode",
                "--max-nodes",
                "16",
            ]
        )

        config = config_from_args(args, cwd=self.root)

        self.assertEqual(config.max_nodes, 16)

    def test_run_config_allows_network_when_flag_set(self) -> None:
        write_text(self.root / "task.md", "Task\n")
        write_text(self.root / "guideline.md", "Guideline\n")
        parser = build_parser()
        args = parser.parse_args(
            [
                "run",
                "--repo",
                str(self.root / "repo"),
                "--task-file",
                str(self.root / "task.md"),
                "--guidelines-file",
                str(self.root / "guideline.md"),
                "--allow-network",
            ]
        )

        config = config_from_args(args, cwd=self.root)

        self.assertTrue(config.allow_network)

    def test_parse_agents_rejects_unknown_agent(self) -> None:
        with self.assertRaises(SystemExit):
            parse_agents("codex,unknown")

    def test_resume_config_loads_from_sqlite(self) -> None:
        config = make_config(self.root)
        store = SearchStore(config.run_dir / "sleepcode.sqlite3")
        store.save_config(config.to_json())

        loaded = load_resume_config(config.run_dir, cwd=self.root)

        self.assertEqual(loaded.run_dir, config.run_dir)
        self.assertEqual(loaded.agents, config.agents)

    def test_install_skills_installs_review_and_expostulate_for_codex_and_kimi(self) -> None:
        codex_dir = self.root / "codex-skills"
        kimi_dir = self.root / "kimi-skills"

        result = main(["install-skills", "--codex-dir", str(codex_dir), "--kimi-dir", str(kimi_dir)])

        self.assertEqual(result, 0)
        for target_dir in (codex_dir, kimi_dir):
            self.assertTrue((target_dir / "sleepcode-review" / "SKILL.md").exists())
            self.assertTrue((target_dir / "sleepcode-expostulate" / "SKILL.md").exists())


if __name__ == "__main__":
    unittest.main()
