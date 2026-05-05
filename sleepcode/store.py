from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path
from typing import Any

from .models import Node
from .util import now_iso


class SearchStore:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.RLock()
        self._init_schema()

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def _init_schema(self) -> None:
        with self._lock:
            self._conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS run_config (
                    id INTEGER PRIMARY KEY CHECK(id = 1),
                    config_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS nodes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    parent_id INTEGER,
                    depth INTEGER NOT NULL,
                    kind TEXT NOT NULL,
                    status TEXT NOT NULL,
                    branch TEXT NOT NULL DEFAULT '',
                    worktree TEXT NOT NULL DEFAULT '',
                    artifact_dir TEXT NOT NULL DEFAULT '',
                    variant INTEGER NOT NULL DEFAULT 1,
                    worker_agent TEXT NOT NULL DEFAULT '',
                    review_agent TEXT NOT NULL DEFAULT '',
                    assessment_agent TEXT NOT NULL DEFAULT '',
                    reasoning_effort TEXT,
                    worker_returncode INTEGER,
                    review_returncode INTEGER,
                    validation_status TEXT NOT NULL DEFAULT 'unknown',
                    validation_returncode INTEGER,
                    diff_files INTEGER NOT NULL DEFAULT 0,
                    diff_lines INTEGER NOT NULL DEFAULT 0,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(parent_id) REFERENCES nodes(id)
                );

                CREATE TABLE IF NOT EXISTS role_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    node_id INTEGER,
                    role TEXT NOT NULL,
                    agent TEXT NOT NULL,
                    command TEXT NOT NULL,
                    returncode INTEGER,
                    log_path TEXT NOT NULL,
                    final_message_path TEXT NOT NULL DEFAULT '',
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    started_at TEXT NOT NULL,
                    finished_at TEXT,
                    FOREIGN KEY(node_id) REFERENCES nodes(id)
                );

                CREATE TABLE IF NOT EXISTS checkpoints (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    node_id INTEGER,
                    stage TEXT NOT NULL,
                    status TEXT NOT NULL,
                    artifact_path TEXT NOT NULL DEFAULT '',
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(node_id) REFERENCES nodes(id)
                );

                CREATE TABLE IF NOT EXISTS vote_rounds (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    status TEXT NOT NULL,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    completed_at TEXT
                );

                CREATE TABLE IF NOT EXISTS vote_decisions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    round_id INTEGER NOT NULL,
                    voter_agent TEXT NOT NULL,
                    node_id INTEGER NOT NULL,
                    action TEXT NOT NULL,
                    evidence_json TEXT NOT NULL DEFAULT '[]',
                    raw_path TEXT NOT NULL DEFAULT '',
                    valid INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(round_id) REFERENCES vote_rounds(id),
                    FOREIGN KEY(node_id) REFERENCES nodes(id)
                );
                """
            )
            self._conn.commit()

    def save_config(self, config_json: dict[str, Any]) -> None:
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO run_config (id, config_json, updated_at)
                VALUES (1, ?, ?)
                ON CONFLICT(id) DO UPDATE SET config_json = excluded.config_json, updated_at = excluded.updated_at
                """,
                (json.dumps(config_json, sort_keys=True), now_iso()),
            )
            self._conn.commit()

    def load_config(self) -> dict[str, Any]:
        with self._lock:
            row = self._conn.execute("SELECT config_json FROM run_config WHERE id = 1").fetchone()
        if row is None:
            raise KeyError("run config not found")
        return json.loads(row["config_json"])

    def create_node(
        self,
        *,
        parent_id: int | None,
        depth: int,
        kind: str,
        status: str,
        branch: str = "",
        worktree: Path | str = "",
        artifact_dir: Path | str = "",
        variant: int = 1,
        worker_agent: str = "",
        review_agent: str = "",
        assessment_agent: str = "",
        reasoning_effort: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Node:
        timestamp = now_iso()
        with self._lock:
            cursor = self._conn.execute(
                """
                INSERT INTO nodes (
                    parent_id, depth, kind, status, branch, worktree, artifact_dir, variant,
                    worker_agent, review_agent, assessment_agent, reasoning_effort, metadata_json,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    parent_id,
                    depth,
                    kind,
                    status,
                    branch,
                    str(worktree),
                    str(artifact_dir),
                    variant,
                    worker_agent,
                    review_agent,
                    assessment_agent,
                    reasoning_effort,
                    json.dumps(metadata or {}, sort_keys=True),
                    timestamp,
                    timestamp,
                ),
            )
            self._conn.commit()
            return self.get_node(int(cursor.lastrowid))

    def update_node(self, node_id: int, **fields: Any) -> Node:
        if not fields:
            return self.get_node(node_id)
        allowed = {
            "status",
            "branch",
            "worktree",
            "artifact_dir",
            "variant",
            "worker_agent",
            "review_agent",
            "assessment_agent",
            "reasoning_effort",
            "worker_returncode",
            "review_returncode",
            "validation_status",
            "validation_returncode",
            "diff_files",
            "diff_lines",
            "metadata",
        }
        unknown = sorted(set(fields) - allowed)
        if unknown:
            raise KeyError(f"unknown node fields: {unknown}")
        mapped: dict[str, Any] = {}
        for key, value in fields.items():
            if key == "metadata":
                mapped["metadata_json"] = json.dumps(value, sort_keys=True)
            elif key in {"worktree", "artifact_dir"}:
                mapped[key] = str(value)
            else:
                mapped[key] = value
        mapped["updated_at"] = now_iso()
        assignments = ", ".join(f"{key} = ?" for key in mapped)
        values = list(mapped.values()) + [node_id]
        with self._lock:
            self._conn.execute(f"UPDATE nodes SET {assignments} WHERE id = ?", values)
            self._conn.commit()
        return self.get_node(node_id)

    def get_node(self, node_id: int) -> Node:
        with self._lock:
            row = self._conn.execute("SELECT * FROM nodes WHERE id = ?", (node_id,)).fetchone()
        if row is None:
            raise KeyError(f"node not found: {node_id}")
        return self._node_from_row(row)

    def root_node(self) -> Node | None:
        with self._lock:
            row = self._conn.execute("SELECT * FROM nodes WHERE kind = 'root' ORDER BY id LIMIT 1").fetchone()
        return None if row is None else self._node_from_row(row)

    def list_nodes(self) -> list[Node]:
        with self._lock:
            rows = self._conn.execute("SELECT * FROM nodes ORDER BY id").fetchall()
        return [self._node_from_row(row) for row in rows]

    def complete_candidates(self) -> list[Node]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM nodes WHERE kind != 'root' AND status = 'complete' ORDER BY id"
            ).fetchall()
        return [self._node_from_row(row) for row in rows]

    def count_nodes(self) -> int:
        with self._lock:
            row = self._conn.execute("SELECT COUNT(*) AS count FROM nodes").fetchone()
        return int(row["count"])

    def count_children(self, parent_id: int, kind: str | None = None) -> int:
        if kind is None:
            query = "SELECT COUNT(*) AS count FROM nodes WHERE parent_id = ?"
            params: tuple[Any, ...] = (parent_id,)
        else:
            query = "SELECT COUNT(*) AS count FROM nodes WHERE parent_id = ? AND kind = ?"
            params = (parent_id, kind)
        with self._lock:
            row = self._conn.execute(query, params).fetchone()
        return int(row["count"])

    def mark_incomplete_abandoned(self) -> None:
        complete_statuses = {"complete", "abandoned_on_resume"}
        with self._lock:
            rows = self._conn.execute("SELECT id, status FROM nodes WHERE kind != 'root'").fetchall()
            for row in rows:
                if row["status"] not in complete_statuses:
                    self._conn.execute(
                        "UPDATE nodes SET status = ?, updated_at = ? WHERE id = ?",
                        ("abandoned_on_resume", now_iso(), int(row["id"])),
                    )
            self._conn.commit()

    def create_role_run(
        self,
        *,
        node_id: int | None,
        role: str,
        agent: str,
        command: str,
        log_path: Path,
        final_message_path: Path,
        metadata: dict[str, Any] | None = None,
    ) -> int:
        with self._lock:
            cursor = self._conn.execute(
                """
                INSERT INTO role_runs (
                    node_id, role, agent, command, log_path, final_message_path, metadata_json, started_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    node_id,
                    role,
                    agent,
                    command,
                    str(log_path),
                    str(final_message_path),
                    json.dumps(metadata or {}, sort_keys=True),
                    now_iso(),
                ),
            )
            self._conn.commit()
            return int(cursor.lastrowid)

    def finish_role_run(self, run_id: int, returncode: int, metadata: dict[str, Any] | None = None) -> None:
        with self._lock:
            self._conn.execute(
                """
                UPDATE role_runs
                SET returncode = ?, finished_at = ?, metadata_json = ?
                WHERE id = ?
                """,
                (returncode, now_iso(), json.dumps(metadata or {}, sort_keys=True), run_id),
            )
            self._conn.commit()

    def list_role_runs(self) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute("SELECT * FROM role_runs ORDER BY id").fetchall()
        return [dict(row) | {"metadata": json.loads(row["metadata_json"] or "{}")} for row in rows]

    def checkpoint(
        self,
        *,
        node_id: int | None,
        stage: str,
        status: str,
        artifact_path: Path | str = "",
        metadata: dict[str, Any] | None = None,
    ) -> None:
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO checkpoints (node_id, stage, status, artifact_path, metadata_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (node_id, stage, status, str(artifact_path), json.dumps(metadata or {}, sort_keys=True), now_iso()),
            )
            self._conn.commit()

    def list_checkpoints(self) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute("SELECT * FROM checkpoints ORDER BY id").fetchall()
        return [dict(row) | {"metadata": json.loads(row["metadata_json"] or "{}")} for row in rows]

    def create_vote_round(self, metadata: dict[str, Any] | None = None) -> int:
        with self._lock:
            cursor = self._conn.execute(
                "INSERT INTO vote_rounds (status, metadata_json, created_at) VALUES (?, ?, ?)",
                ("running", json.dumps(metadata or {}, sort_keys=True), now_iso()),
            )
            self._conn.commit()
            return int(cursor.lastrowid)

    def finish_vote_round(self, round_id: int, status: str = "complete") -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE vote_rounds SET status = ?, completed_at = ? WHERE id = ?",
                (status, now_iso(), round_id),
            )
            self._conn.commit()

    def add_vote_decision(
        self,
        *,
        round_id: int,
        voter_agent: str,
        node_id: int,
        action: str,
        evidence: list[str],
        raw_path: Path,
        valid: bool = True,
    ) -> None:
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO vote_decisions (
                    round_id, voter_agent, node_id, action, evidence_json, raw_path, valid, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    round_id,
                    voter_agent,
                    node_id,
                    action,
                    json.dumps(evidence, sort_keys=True),
                    str(raw_path),
                    int(valid),
                    now_iso(),
                ),
            )
            self._conn.commit()

    def list_vote_decisions(self, round_id: int | None = None) -> list[dict[str, Any]]:
        if round_id is None:
            query = "SELECT * FROM vote_decisions ORDER BY id"
            params: tuple[Any, ...] = ()
        else:
            query = "SELECT * FROM vote_decisions WHERE round_id = ? ORDER BY id"
            params = (round_id,)
        with self._lock:
            rows = self._conn.execute(query, params).fetchall()
        return [
            dict(row) | {"evidence": json.loads(row["evidence_json"] or "[]"), "valid": bool(row["valid"])}
            for row in rows
        ]

    def _node_from_row(self, row: sqlite3.Row) -> Node:
        return Node(
            id=int(row["id"]),
            parent_id=None if row["parent_id"] is None else int(row["parent_id"]),
            depth=int(row["depth"]),
            kind=row["kind"],
            status=row["status"],
            branch=row["branch"],
            worktree=Path(row["worktree"]) if row["worktree"] else Path(),
            artifact_dir=Path(row["artifact_dir"]) if row["artifact_dir"] else Path(),
            variant=int(row["variant"]),
            worker_agent=row["worker_agent"],
            review_agent=row["review_agent"],
            assessment_agent=row["assessment_agent"],
            reasoning_effort=row["reasoning_effort"],
            worker_returncode=row["worker_returncode"],
            review_returncode=row["review_returncode"],
            validation_status=row["validation_status"],
            validation_returncode=row["validation_returncode"],
            diff_files=int(row["diff_files"]),
            diff_lines=int(row["diff_lines"]),
            metadata=json.loads(row["metadata_json"] or "{}"),
        )
