from __future__ import annotations

import unittest

from sleepcode.scheduler import Scheduler
from sleepcode.store import SearchStore

from tests.helpers import FakeAgents, FakeGit, FakeValidator, TempDirTestCase, make_config


class SchedulerTests(TempDirTestCase, unittest.TestCase):
    def test_jobs_do_not_limit_builder_fanout_budget(self) -> None:
        config = make_config(self.root, max_nodes=4, max_depth=1, jobs=1, builder_fanout=3)
        store = SearchStore(config.run_dir / "sleepcode.sqlite3")
        scheduler = Scheduler(
            config,
            store=store,
            git=FakeGit(config),
            agents=FakeAgents(),
            validator=FakeValidator(),
        )

        scheduler.run()

        nodes = store.list_nodes()
        self.assertEqual([node.kind for node in nodes], ["root", "builder", "builder", "builder"])
        self.assertEqual(scheduler.stop_reason, "max nodes reached")

    def test_votes_create_fixer_and_rebuilder_children(self) -> None:
        config = make_config(
            self.root,
            max_nodes=5,
            max_depth=2,
            jobs=2,
            builder_fanout=2,
            fixer_fanout=1,
            rebuilder_fanout=1,
        )
        store = SearchStore(config.run_dir / "sleepcode.sqlite3")
        fake_agents = FakeAgents(vote_actions={2: "fix", 3: "rebuild"})
        scheduler = Scheduler(
            config,
            store=store,
            git=FakeGit(config),
            agents=fake_agents,
            validator=FakeValidator(),
        )

        scheduler.run()

        nodes = store.list_nodes()
        self.assertEqual([node.kind for node in nodes], ["root", "builder", "builder", "fixer", "rebuilder"])
        self.assertEqual(store.count_children(2, "fixer"), 1)
        self.assertEqual(store.count_children(3, "rebuilder"), 1)
        self.assertTrue(store.list_vote_decisions())

    def test_review_agent_differs_from_worker_when_possible(self) -> None:
        config = make_config(self.root, max_nodes=3, max_depth=1, builder_fanout=2, jobs=2)
        store = SearchStore(config.run_dir / "sleepcode.sqlite3")

        Scheduler(
            config,
            store=store,
            git=FakeGit(config),
            agents=FakeAgents(),
            validator=FakeValidator(),
        ).run()

        builders = store.list_nodes()[1:]
        self.assertEqual([node.worker_agent for node in builders], ["codex", "codex"])
        self.assertEqual([node.review_agent for node in builders], ["kimi", "kimi"])
        self.assertEqual([node.reasoning_effort for node in builders], ["xhigh", "high"])

    def test_agent_runs_receive_role_context_directories(self) -> None:
        config = make_config(self.root, max_nodes=2, max_depth=1, builder_fanout=1, jobs=1)
        store = SearchStore(config.run_dir / "sleepcode.sqlite3")
        fake_agents = FakeAgents()

        Scheduler(
            config,
            store=store,
            git=FakeGit(config),
            agents=fake_agents,
            validator=FakeValidator(),
        ).run()

        node_dir = config.run_dir / "nodes" / "node-002"
        self.assertEqual((node_dir / "context" / "assessment" / "task.md").read_text(encoding="utf-8"), config.task)
        self.assertEqual(
            (node_dir / "context" / "assessment" / "guidelines.md").read_text(encoding="utf-8"),
            config.guidelines,
        )
        self.assertTrue((node_dir / "context" / "worker" / "work_brief.md").exists())
        self.assertTrue((node_dir / "context" / "reviewer" / "worker_report.md").exists())
        self.assertTrue((node_dir / "context" / "reviewer" / "expostulation.md").exists())
        self.assertTrue((node_dir / "context" / "expostulator" / "review_report.md").exists())
        self.assertTrue((node_dir / "context" / "expostulator" / "diffstat.txt").exists())
        self.assertTrue((config.run_dir / "final" / "context" / "final_report" / "node_summaries.md").exists())
        self.assertTrue((config.run_dir / "final" / "context" / "final_report" / "expostulation.md").exists())
        self.assertTrue(all(call["extra_context_dirs"] for call in fake_agents.calls))

    def test_review_is_followed_by_read_only_expostulation(self) -> None:
        config = make_config(self.root, max_nodes=2, max_depth=1, builder_fanout=1, jobs=1)
        store = SearchStore(config.run_dir / "sleepcode.sqlite3")
        fake_agents = FakeAgents()

        Scheduler(
            config,
            store=store,
            git=FakeGit(config),
            agents=fake_agents,
            validator=FakeValidator(),
        ).run()

        roles = [str(call["role"]) for call in fake_agents.calls]
        self.assertLess(roles.index("reviewer"), roles.index("expostulator"))
        expostulator_call = next(call for call in fake_agents.calls if call["role"] == "expostulator")
        self.assertEqual(expostulator_call["agent"], "kimi")
        self.assertEqual(expostulator_call["sandbox"], "read-only")
        self.assertTrue(expostulator_call["plan_mode"])
        self.assertIn("sleepcode expostulation workflow", str(expostulator_call["prompt"]))
        self.assertNotIn("$sleepcode-expostulate", str(expostulator_call["prompt"]))

    def test_expostulation_accepts_validated_module_only_after_passed_validation(self) -> None:
        entry = {
            "kind": "validated_module",
            "title": "App value update",
            "claim": "The app value update is validated for the requested behavior.",
            "affected_files": ["app.py"],
            "evidence_paths": ["validation.json", "review_report.md"],
            "reuse_guidance": "Reuse the direct assignment pattern for this simple value update.",
        }
        config = make_config(self.root, max_nodes=2, max_depth=1, builder_fanout=1, jobs=1)
        store = SearchStore(config.run_dir / "sleepcode.sqlite3")

        Scheduler(
            config,
            store=store,
            git=FakeGit(config),
            agents=FakeAgents(expostulation_entries=[entry]),
            validator=FakeValidator(status="fail", returncode=1),
        ).run()

        self.assertEqual(store.list_expostulation_entries(), [])
        blackboard = (config.run_dir / "expostulation.md").read_text(encoding="utf-8")
        self.assertIn("No high-confidence entries yet.", blackboard)

    def test_expostulation_renders_accepted_entries(self) -> None:
        entry = {
            "kind": "repair_pattern",
            "title": "Keep validation inputs explicit",
            "claim": "The worker fixed the issue by passing validation inputs explicitly.",
            "affected_files": ["app.py"],
            "evidence_paths": ["worker_report.md", "review_report.md"],
            "reuse_guidance": "Prefer explicit validation inputs when repairing similar failures.",
        }
        config = make_config(self.root, max_nodes=2, max_depth=1, builder_fanout=1, jobs=1)
        store = SearchStore(config.run_dir / "sleepcode.sqlite3")

        Scheduler(
            config,
            store=store,
            git=FakeGit(config),
            agents=FakeAgents(expostulation_entries=[entry]),
            validator=FakeValidator(),
        ).run()

        entries = store.list_expostulation_entries()
        self.assertEqual(entries[0]["kind"], "repair_pattern")
        blackboard = (config.run_dir / "expostulation.md").read_text(encoding="utf-8")
        self.assertIn("Keep validation inputs explicit", blackboard)
        self.assertIn("Source node: `2`", blackboard)


if __name__ == "__main__":
    unittest.main()
