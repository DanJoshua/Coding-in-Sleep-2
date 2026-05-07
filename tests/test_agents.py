from __future__ import annotations

import unittest

from sleepcode.agents import AgentRunner

from tests.helpers import TempDirTestCase


class AgentCommandTests(TempDirTestCase, unittest.TestCase):
    def test_codex_exec_command_uses_headless_flags_and_reasoning(self) -> None:
        runner = AgentRunner(model="gpt-test")
        final_path = self.root / "final.md"

        command = runner.build_command(
            agent="codex",
            role="builder",
            worktree=self.root,
            final_message_path=final_path,
            sandbox="workspace-write",
            reasoning_effort="xhigh",
            extra_context_dirs=(self.root / "context",),
        )

        self.assertEqual(command[:3], ["codex", "exec", "--json"])
        self.assertIn("--ephemeral", command)
        self.assertIn("--ignore-user-config", command)
        self.assertIn("--add-dir", command)
        self.assertIn(str(self.root / "context"), command)
        self.assertIn("--output-last-message", command)
        self.assertIn(str(final_path), command)
        self.assertIn('model_reasoning_effort="xhigh"', command)
        self.assertEqual(command[-1], "-")

    def test_kimi_print_command_uses_work_dir_and_plan_mode(self) -> None:
        runner = AgentRunner(model="kimi-test")

        command = runner.build_command(
            agent="kimi",
            role="reviewer",
            worktree=self.root,
            final_message_path=self.root / "final.md",
            sandbox="read-only",
            plan_mode=True,
            extra_context_dirs=(self.root / "context",),
        )

        self.assertEqual(command[:3], ["kimi", "--work-dir", str(self.root)])
        self.assertIn("--add-dir", command)
        self.assertIn(str(self.root / "context"), command)
        self.assertIn("--print", command)
        self.assertIn("--output-format=stream-json", command)
        self.assertIn("--plan", command)
        self.assertIn("kimi-test", command)

    def test_codex_command_includes_network_flag_when_allowed(self) -> None:
        runner = AgentRunner(model="gpt-test", allow_network=True)
        final_path = self.root / "final.md"

        command = runner.build_command(
            agent="codex",
            role="builder",
            worktree=self.root,
            final_message_path=final_path,
            sandbox="workspace-write",
        )

        self.assertIn("-c", command)
        self.assertIn("sandbox_workspace_write.network_access=true", command)

    def test_codex_command_omits_network_flag_by_default(self) -> None:
        runner = AgentRunner(model="gpt-test")
        final_path = self.root / "final.md"

        command = runner.build_command(
            agent="codex",
            role="builder",
            worktree=self.root,
            final_message_path=final_path,
            sandbox="workspace-write",
        )

        self.assertNotIn("sandbox_workspace_write.network_access=true", command)


if __name__ == "__main__":
    unittest.main()
