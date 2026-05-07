from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


NODE_ROOT = "root"
NODE_BUILDER = "builder"
NODE_FIXER = "fixer"
NODE_REBUILDER = "rebuilder"

EXPANSION_ACTIONS = ("fix", "rebuild", "drop")
EXPOSTULATION_KINDS = ("validated_module", "repair_pattern", "pitfall")


@dataclass(frozen=True)
class RunConfig:
    repo: Path
    task: str
    task_source: str
    guidelines: str
    guidelines_source: str
    base: str
    out_dir: Path
    run_id: str
    run_dir: Path
    max_nodes: int = 16
    max_depth: int = 3
    jobs: int = 2
    builder_fanout: int = 3
    fixer_fanout: int = 2
    rebuilder_fanout: int = 1
    agents: tuple[str, ...] = ("codex", "kimi")
    test_cmd: str | None = None
    model: str | None = None
    sandbox: str = "workspace-write"
    keep_worktrees: bool = True
    allow_network: bool = False
    agent_timeout_seconds: int = 3600
    agent_startup_timeout_seconds: int = 120
    agent_idle_timeout_seconds: int = 300
    kimi_idle_timeout_seconds: int | None = None

    def to_json(self) -> dict[str, Any]:
        return {
            "repo": str(self.repo),
            "task": self.task,
            "task_source": self.task_source,
            "guidelines": self.guidelines,
            "guidelines_source": self.guidelines_source,
            "base": self.base,
            "out_dir": str(self.out_dir),
            "run_id": self.run_id,
            "run_dir": str(self.run_dir),
            "max_nodes": self.max_nodes,
            "max_depth": self.max_depth,
            "jobs": self.jobs,
            "builder_fanout": self.builder_fanout,
            "fixer_fanout": self.fixer_fanout,
            "rebuilder_fanout": self.rebuilder_fanout,
            "agents": list(self.agents),
            "test_cmd": self.test_cmd,
            "model": self.model,
            "sandbox": self.sandbox,
            "keep_worktrees": self.keep_worktrees,
            "allow_network": self.allow_network,
            "agent_timeout_seconds": self.agent_timeout_seconds,
            "agent_startup_timeout_seconds": self.agent_startup_timeout_seconds,
            "agent_idle_timeout_seconds": self.agent_idle_timeout_seconds,
            "kimi_idle_timeout_seconds": self.kimi_idle_timeout_seconds,
        }

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> RunConfig:
        return cls(
            repo=Path(data["repo"]),
            task=str(data["task"]),
            task_source=str(data["task_source"]),
            guidelines=str(data["guidelines"]),
            guidelines_source=str(data["guidelines_source"]),
            base=str(data["base"]),
            out_dir=Path(data["out_dir"]),
            run_id=str(data["run_id"]),
            run_dir=Path(data["run_dir"]),
            max_nodes=int(data["max_nodes"]),
            max_depth=int(data["max_depth"]),
            jobs=int(data["jobs"]),
            builder_fanout=int(data["builder_fanout"]),
            fixer_fanout=int(data["fixer_fanout"]),
            rebuilder_fanout=int(data["rebuilder_fanout"]),
            agents=tuple(str(agent) for agent in data["agents"]),
            test_cmd=data.get("test_cmd"),
            model=data.get("model"),
            sandbox=str(data["sandbox"]),
            keep_worktrees=bool(data["keep_worktrees"]),
            allow_network=bool(data.get("allow_network", False)),
            agent_timeout_seconds=int(data["agent_timeout_seconds"]),
            agent_startup_timeout_seconds=int(data["agent_startup_timeout_seconds"]),
            agent_idle_timeout_seconds=int(data["agent_idle_timeout_seconds"]),
            kimi_idle_timeout_seconds=(
                None if data.get("kimi_idle_timeout_seconds") is None else int(data["kimi_idle_timeout_seconds"])
            ),
        )


@dataclass(frozen=True)
class Node:
    id: int
    parent_id: int | None
    depth: int
    kind: str
    status: str
    branch: str
    worktree: Path
    artifact_dir: Path
    variant: int = 1
    worker_agent: str = ""
    review_agent: str = ""
    assessment_agent: str = ""
    reasoning_effort: str | None = None
    worker_returncode: int | None = None
    review_returncode: int | None = None
    validation_status: str = "unknown"
    validation_returncode: int | None = None
    diff_files: int = 0
    diff_lines: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CommandResult:
    command: list[str] | str
    returncode: int
    log_path: Path
    final_message_path: Path
    timed_out: bool = False
    reason: str | None = None


@dataclass(frozen=True)
class DiffStats:
    files: int
    lines: int
    patch_path: Path
    stat_path: Path


@dataclass(frozen=True)
class ValidationResult:
    command: list[str] | str
    status: str
    returncode: int
    log_path: Path
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Expansion:
    parent: Node
    kind: str
    vote_count: int = 0


@dataclass(frozen=True)
class VoteDecision:
    voter_agent: str
    node_id: int
    action: str
    evidence: tuple[str, ...]
    raw_path: Path
