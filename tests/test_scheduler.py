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
        self.assertTrue((config.run_dir / "final" / "context" / "final_report" / "node_summaries.md").exists())
        self.assertTrue(all(call["extra_context_dirs"] for call in fake_agents.calls))


if __name__ == "__main__":
    unittest.main()
