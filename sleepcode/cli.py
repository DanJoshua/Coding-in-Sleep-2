from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

from .agents import CODEX_REASONING_EFFORTS, SUPPORTED_AGENTS
from .models import RunConfig
from .scheduler import Scheduler
from .store import SearchStore
from .util import ensure_unique_dir, make_run_id, read_json


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="sleepcode")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run = subparsers.add_parser("run", help="run one sleepcode search")
    run.add_argument("--repo", required=True, type=Path, help="target git repository")
    run.add_argument("--task-file", required=True, type=Path, help="task markdown file")
    run.add_argument("--guidelines-file", required=True, type=Path, help="guidelines markdown file")
    run.add_argument("--base", default="HEAD")
    run.add_argument("--out", default=Path("runs"), type=Path)
    run.add_argument("--max-nodes", default=8, type=int)
    run.add_argument("--max-depth", default=3, type=int)
    run.add_argument("--jobs", default=2, type=int)
    run.add_argument("--builder-fanout", default=3, type=int)
    run.add_argument("--fixer-fanout", default=2, type=int)
    run.add_argument("--rebuilder-fanout", default=1, type=int)
    run.add_argument("--agents", default="codex,kimi", help="comma-separated agents: codex,kimi")
    run.add_argument("--test-cmd")
    run.add_argument("--model")
    run.add_argument(
        "--sandbox",
        default="workspace-write",
        choices=("read-only", "workspace-write", "danger-full-access"),
    )
    worktree_group = run.add_mutually_exclusive_group()
    worktree_group.add_argument("--keep-worktrees", action="store_true", default=True)
    worktree_group.add_argument("--cleanup-worktrees", action="store_false", dest="keep_worktrees")
    run.add_argument("--agent-timeout", default=3600, type=int, dest="agent_timeout")
    run.add_argument("--agent-startup-timeout", default=120, type=int, dest="agent_startup_timeout")
    run.add_argument("--agent-idle-timeout", default=300, type=int, dest="agent_idle_timeout")
    run.add_argument("--kimi-idle-timeout", default=0, type=int)

    resume = subparsers.add_parser("resume", help="resume a run from checkpoints")
    resume.add_argument("--run-dir", required=True, type=Path)

    install = subparsers.add_parser("install-skills", help="install sleepcode skills into agent skill directories")
    install.add_argument("--codex-dir", default=Path.home() / ".codex" / "skills", type=Path)
    install.add_argument("--kimi-dir", default=Path.home() / ".kimi" / "skills", type=Path)
    return parser


def config_from_args(args: argparse.Namespace, cwd: Path | None = None) -> RunConfig:
    cwd = (cwd or Path.cwd()).resolve()
    repo = _resolve(args.repo, cwd)
    task_file = _resolve(args.task_file, cwd)
    guidelines_file = _resolve(args.guidelines_file, cwd)
    task = task_file.read_text(encoding="utf-8").strip()
    guidelines = guidelines_file.read_text(encoding="utf-8").strip()
    if not task:
        raise SystemExit("task file is empty")
    if not guidelines:
        raise SystemExit("guidelines file is empty")
    _validate_positive(args.max_nodes, "--max-nodes", minimum=2)
    _validate_positive(args.max_depth, "--max-depth", minimum=1)
    _validate_positive(args.jobs, "--jobs", minimum=1)
    _validate_positive(args.builder_fanout, "--builder-fanout", minimum=1)
    _validate_positive(args.fixer_fanout, "--fixer-fanout", minimum=0)
    _validate_positive(args.rebuilder_fanout, "--rebuilder-fanout", minimum=0)
    _validate_positive(args.agent_timeout, "--agent-timeout", minimum=1)
    _validate_positive(args.agent_startup_timeout, "--agent-startup-timeout", minimum=1)
    _validate_positive(args.agent_idle_timeout, "--agent-idle-timeout", minimum=1)
    _validate_positive(args.kimi_idle_timeout, "--kimi-idle-timeout", minimum=0)
    agents = parse_agents(args.agents)
    out_dir = _resolve(args.out, cwd)
    run_dir = ensure_unique_dir(out_dir / make_run_id())
    return RunConfig(
        repo=repo,
        task=task + "\n",
        task_source=str(task_file),
        guidelines=guidelines + "\n",
        guidelines_source=str(guidelines_file),
        base=args.base,
        out_dir=out_dir,
        run_id=run_dir.name,
        run_dir=run_dir,
        max_nodes=args.max_nodes,
        max_depth=args.max_depth,
        jobs=args.jobs,
        builder_fanout=args.builder_fanout,
        fixer_fanout=args.fixer_fanout,
        rebuilder_fanout=args.rebuilder_fanout,
        agents=agents,
        test_cmd=args.test_cmd,
        model=args.model,
        sandbox=args.sandbox,
        keep_worktrees=args.keep_worktrees,
        agent_timeout_seconds=args.agent_timeout,
        agent_startup_timeout_seconds=args.agent_startup_timeout,
        agent_idle_timeout_seconds=args.agent_idle_timeout,
        kimi_idle_timeout_seconds=None if args.kimi_idle_timeout == 0 else args.kimi_idle_timeout,
    )


def parse_agents(value: str) -> tuple[str, ...]:
    agents = tuple(part.strip().lower() for part in value.split(",") if part.strip())
    if not agents:
        raise SystemExit("--agents must name at least one agent")
    invalid = [agent for agent in agents if agent not in SUPPORTED_AGENTS]
    if invalid:
        raise SystemExit(f"--agents contains unsupported agent(s): {', '.join(invalid)}")
    return agents


def load_resume_config(run_dir: Path, cwd: Path | None = None) -> RunConfig:
    cwd = (cwd or Path.cwd()).resolve()
    run_dir = _resolve(run_dir, cwd)
    store = SearchStore(run_dir / "sleepcode.sqlite3")
    try:
        data = store.load_config()
    except KeyError:
        data = read_json(run_dir / "config.json")
    return RunConfig.from_json(data)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "run":
        config = config_from_args(args)
        report = Scheduler(config).run()
        print(report)
        return 0
    if args.command == "resume":
        config = load_resume_config(args.run_dir)
        report = Scheduler(config).run(resume=True)
        print(report)
        return 0
    if args.command == "install-skills":
        return _install_skills(args)
    parser.error("unknown command")
    return 2


def _install_skills(args: argparse.Namespace) -> int:
    skill_name = "sleepcode-review"
    source = Path(__file__).parent.parent / "skills" / skill_name
    if not source.exists():
        print(f"error: skill source not found: {source}", file=sys.stderr)
        return 1

    codex_dir = Path(args.codex_dir)
    kimi_dir = Path(args.kimi_dir)
    installed = False

    for target_dir in (codex_dir, kimi_dir):
        target = target_dir / skill_name
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(source, target)
        print(f"Installed {skill_name} -> {target}")
        installed = True

    if not installed:
        print("error: no skill directories were installed", file=sys.stderr)
        return 1
    return 0


def _resolve(path: Path, cwd: Path) -> Path:
    path = path.expanduser()
    return path.resolve() if path.is_absolute() else (cwd / path).resolve()


def _validate_positive(value: int, option: str, *, minimum: int) -> None:
    if value < minimum:
        raise SystemExit(f"{option} must be at least {minimum}")


__all__ = ["CODEX_REASONING_EFFORTS", "build_parser", "config_from_args", "load_resume_config", "main", "parse_agents"]
