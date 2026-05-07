from __future__ import annotations

import unittest
from dataclasses import replace
from pathlib import Path

from sleepcode.models import NODE_BUILDER, Node
from sleepcode.prompts import assessment_prompt, candidate_context, expostulation_prompt, review_prompt, vote_prompt, worker_prompt

from tests.helpers import TempDirTestCase, make_config


def make_node(root: Path, *, kind: str = NODE_BUILDER) -> Node:
    return Node(
        id=2,
        parent_id=1,
        depth=1,
        kind=kind,
        status="prepared",
        branch="branch-2",
        worktree=root / "worktree",
        artifact_dir=root / "artifacts",
    )


class PromptContextTests(TempDirTestCase, unittest.TestCase):
    def test_role_prompts_point_to_context_files_without_pasting_run_inputs(self) -> None:
        config = replace(
            make_config(self.root),
            task="SECRET TASK BODY\n",
            guidelines="SECRET GUIDELINES BODY\n",
        )
        node = make_node(self.root)
        context_dir = self.root / "context"

        prompts = [
            assessment_prompt(config, node, None, context_dir),
            worker_prompt(config, node, None, context_dir),
            review_prompt(config, node, context_dir, agent="codex"),
            expostulation_prompt(config, node, context_dir, agent="codex"),
            vote_prompt(config, context_dir),
        ]

        for prompt in prompts:
            self.assertIn(str(context_dir / "manifest.md"), prompt)
            self.assertIn(str(context_dir / "task.md"), prompt)
            self.assertIn(str(context_dir / "guidelines.md"), prompt)
            self.assertNotIn("SECRET TASK BODY", prompt)
            self.assertNotIn("SECRET GUIDELINES BODY", prompt)

    def test_candidate_context_keeps_vote_evidence_outside_prompt_template(self) -> None:
        context = candidate_context(
            [
                {
                    "id": 2,
                    "kind": "builder",
                    "depth": 1,
                    "parent_id": 1,
                    "diff_files": 1,
                    "diff_lines": 7,
                    "validation_status": "smoke",
                    "validation_returncode": 0,
                    "worker_returncode": 0,
                    "review_returncode": 0,
                    "remaining_fixer_slots": 1,
                    "remaining_rebuilder_slots": 1,
                    "worker_report": "Worker evidence.",
                    "review_report": "Review evidence.",
                }
            ]
        )

        prompt = vote_prompt(make_config(self.root), self.root / "context")

        self.assertIn("Worker evidence.", context)
        self.assertIn("Review evidence.", context)
        self.assertNotIn("Worker evidence.", prompt)
        self.assertIn("candidates.md", prompt)

    def test_review_prompt_triggers_codex_skill(self) -> None:
        config = make_config(self.root)
        node = make_node(self.root)
        context_dir = self.root / "context"
        prompt = review_prompt(config, node, context_dir, agent="codex")
        self.assertIn("$sleepcode-review", prompt)

    def test_review_prompt_triggers_kimi_skill(self) -> None:
        config = make_config(self.root)
        node = make_node(self.root)
        context_dir = self.root / "context"
        prompt = review_prompt(config, node, context_dir, agent="kimi")
        self.assertIn("sleepcode review", prompt)
        self.assertNotIn("$sleepcode-review", prompt)

    def test_expostulation_prompt_uses_agent_specific_skill_trigger(self) -> None:
        config = make_config(self.root)
        node = make_node(self.root)
        context_dir = self.root / "context"

        codex_prompt = expostulation_prompt(config, node, context_dir, agent="codex")
        kimi_prompt = expostulation_prompt(config, node, context_dir, agent="kimi")

        self.assertIn("$sleepcode-expostulate", codex_prompt)
        self.assertIn("sleepcode expostulation workflow", kimi_prompt)
        self.assertNotIn("$sleepcode-expostulate", kimi_prompt)
        self.assertIn('"entries"', codex_prompt)
        self.assertIn("Do not expostulate when unsure", codex_prompt)


if __name__ == "__main__":
    unittest.main()
