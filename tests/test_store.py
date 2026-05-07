from __future__ import annotations

import unittest

from sleepcode.store import SearchStore

from tests.helpers import TempDirTestCase, make_config


class StoreTests(TempDirTestCase, unittest.TestCase):
    def test_persists_nodes_checkpoints_and_votes(self) -> None:
        config = make_config(self.root)
        store = SearchStore(config.run_dir / "sleepcode.sqlite3")
        store.save_config(config.to_json())
        root = store.create_node(
            parent_id=None,
            depth=0,
            kind="root",
            status="complete",
            worktree=config.repo,
            artifact_dir=config.run_dir / "nodes" / "node-001",
        )
        child = store.create_node(parent_id=root.id, depth=1, kind="builder", status="running")
        store.checkpoint(node_id=child.id, stage="worker", status="complete", artifact_path="worker_report.md")
        round_id = store.create_vote_round({"candidate_ids": [child.id]})
        store.add_vote_decision(
            round_id=round_id,
            voter_agent="codex",
            node_id=child.id,
            action="fix",
            evidence=["validation failed"],
            raw_path=config.run_dir / "votes" / "vote.json",
        )
        store.finish_vote_round(round_id)
        store.close()

        reopened = SearchStore(config.run_dir / "sleepcode.sqlite3")

        self.assertEqual(reopened.load_config()["run_id"], "run")
        self.assertEqual(reopened.count_nodes(), 2)
        self.assertEqual(reopened.count_children(root.id, "builder"), 1)
        self.assertEqual(reopened.list_checkpoints()[0]["stage"], "worker")
        self.assertEqual(reopened.list_vote_decisions()[0]["action"], "fix")
        self.assertEqual(reopened.list_vote_decisions()[0]["evidence"], ["validation failed"])

    def test_persists_expostulation_entries(self) -> None:
        config = make_config(self.root)
        store = SearchStore(config.run_dir / "sleepcode.sqlite3")
        root = store.create_node(parent_id=None, depth=0, kind="root", status="complete")
        child = store.create_node(parent_id=root.id, depth=1, kind="builder", status="complete")

        store.add_expostulation_entry(
            kind="pitfall",
            title="Avoid stale generated fixtures",
            claim="Generated fixtures can hide stale behavior unless regenerated with the worker change.",
            source_node_id=child.id,
            affected_files=["tests/test_app.py"],
            evidence_paths=[str(config.run_dir / "nodes" / "node-002" / "review_report.md")],
            reuse_guidance="Regenerate fixtures before trusting validation that depends on them.",
            raw_path=config.run_dir / "nodes" / "node-002" / "expostulation.json",
        )
        store.close()

        reopened = SearchStore(config.run_dir / "sleepcode.sqlite3")
        entries = reopened.list_expostulation_entries()

        self.assertEqual(entries[0]["kind"], "pitfall")
        self.assertEqual(entries[0]["source_node_id"], child.id)
        self.assertEqual(entries[0]["affected_files"], ["tests/test_app.py"])
        self.assertEqual(
            entries[0]["evidence_paths"],
            [str(config.run_dir / "nodes" / "node-002" / "review_report.md")],
        )

    def test_resume_marks_incomplete_nodes_abandoned(self) -> None:
        config = make_config(self.root)
        store = SearchStore(config.run_dir / "sleepcode.sqlite3")
        root = store.create_node(parent_id=None, depth=0, kind="root", status="complete")
        running = store.create_node(parent_id=root.id, depth=1, kind="builder", status="running_worker")

        store.mark_incomplete_abandoned()

        self.assertEqual(store.get_node(running.id).status, "abandoned_on_resume")


if __name__ == "__main__":
    unittest.main()
