from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .models import RunConfig
from .store import SearchStore
from .util import read_text, truncate, write_json, write_text


def extract_json_object(text: str) -> dict[str, Any] | None:
    stripped = text.strip()
    if stripped.startswith("```"):
        chunks = stripped.split("```")
        for chunk in chunks:
            chunk = chunk.strip()
            if chunk.startswith("json"):
                chunk = chunk[4:].strip()
            if chunk.startswith("{") and chunk.endswith("}"):
                try:
                    return json.loads(chunk)
                except json.JSONDecodeError:
                    continue
    if stripped.startswith("{") and stripped.endswith("}"):
        try:
            return json.loads(stripped)
        except json.JSONDecodeError:
            return None
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(stripped[start : end + 1])
        except json.JSONDecodeError:
            return None
    return None


def summarize_nodes_for_final_report(store: SearchStore) -> str:
    blocks: list[str] = []
    for node in store.list_nodes():
        if node.kind == "root":
            continue
        blocks.append(
            f"""Node {node.id} ({node.kind}, status {node.status}, depth {node.depth})
Parent: {node.parent_id}
Diff: {node.diff_files} files / {node.diff_lines} lines
Validation: {node.validation_status} ({node.validation_returncode})
Worker: {node.worker_agent} ({node.worker_returncode})
Reviewer: {node.review_agent} ({node.review_returncode})

Worker report:
```text
{truncate(read_text(node.artifact_dir / "worker_report.md"), 6000)}
```

Review report:
```text
{truncate(read_text(node.artifact_dir / "review_report.md"), 6000)}
```
"""
        )
    return "\n\n".join(blocks) or "No candidate nodes completed."


def render_expostulation_markdown(entries: list[dict[str, Any]]) -> str:
    lines = [
        "# Expostulation Blackboard",
        "",
        "Shared per-run implementation evidence. `task.md` and `guidelines.md` remain authoritative.",
        "",
    ]
    if not entries:
        lines.append("No high-confidence entries yet.")
        return "\n".join(lines).rstrip() + "\n"

    for entry in entries:
        lines.extend(
            [
                f"## {entry['title']}",
                "",
                f"- Kind: `{entry['kind']}`",
                f"- Source node: `{entry['source_node_id']}`",
                f"- Claim: {entry['claim']}",
                f"- Reuse guidance: {entry['reuse_guidance']}",
                f"- Affected files: {_format_inline_list(entry.get('affected_files', []))}",
                f"- Evidence paths: {_format_inline_list(entry.get('evidence_paths', []))}",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def write_report_json(config: RunConfig, store: SearchStore, stop_reason: str, report_path: Path) -> None:
    write_json(
        config.run_dir / "final_report.json",
        {
            "run_id": config.run_id,
            "repo": str(config.repo),
            "base": config.base,
            "task_source": config.task_source,
            "guidelines_source": config.guidelines_source,
            "stop_reason": stop_reason,
            "final_report": str(report_path),
            "nodes": [
                {
                    "id": node.id,
                    "parent_id": node.parent_id,
                    "depth": node.depth,
                    "kind": node.kind,
                    "status": node.status,
                    "branch": node.branch,
                    "worktree": str(node.worktree),
                    "artifact_dir": str(node.artifact_dir),
                    "variant": node.variant,
                    "worker_agent": node.worker_agent,
                    "review_agent": node.review_agent,
                    "assessment_agent": node.assessment_agent,
                    "reasoning_effort": node.reasoning_effort,
                    "worker_returncode": node.worker_returncode,
                    "review_returncode": node.review_returncode,
                    "validation_status": node.validation_status,
                    "validation_returncode": node.validation_returncode,
                    "diff_files": node.diff_files,
                    "diff_lines": node.diff_lines,
                    "metadata": node.metadata,
                }
                for node in store.list_nodes()
            ],
            "expostulation": store.list_expostulation_entries(),
            "role_runs": store.list_role_runs(),
            "checkpoints": store.list_checkpoints(),
            "vote_decisions": store.list_vote_decisions(),
        },
    )


def write_fallback_final_report(config: RunConfig, store: SearchStore, stop_reason: str) -> Path:
    report_path = config.run_dir / "final_report.md"
    candidates = [node for node in store.list_nodes() if node.kind != "root" and node.status == "complete"]
    preferred = sorted(
        candidates,
        key=lambda node: (
            node.validation_status != "pass",
            node.validation_status != "smoke",
            node.review_returncode not in (None, 0),
            node.diff_lines == 0,
            node.depth,
            node.id,
        ),
    )
    best = preferred[0] if preferred else None
    lines = [f"# sleepcode final report: {config.run_id}", "", f"Stop reason: `{stop_reason}`", ""]
    if best is None:
        lines.append("No completed candidate node is available for recommendation.")
    else:
        lines.append(f"Recommended node: `{best.id}`")
        lines.append("")
        lines.append(
            f"Node `{best.id}` is preferred by fallback mechanical ordering: validation `{best.validation_status}`, "
            f"review returncode `{best.review_returncode}`, diff `{best.diff_files}` files / `{best.diff_lines}` lines."
        )
        lines.append("")
        lines.append("Worker report:")
        lines.append("")
        lines.append("```text")
        lines.append(truncate(read_text(best.artifact_dir / "worker_report.md"), 4000).rstrip())
        lines.append("```")
        lines.append("")
        lines.append("Review report:")
        lines.append("")
        lines.append("```text")
        lines.append(truncate(read_text(best.artifact_dir / "review_report.md"), 4000).rstrip())
        lines.append("```")
    write_text(report_path, "\n".join(lines).rstrip() + "\n")
    return report_path


def _format_inline_list(values: object) -> str:
    if not isinstance(values, list) or not values:
        return "-"
    return ", ".join(f"`{value}`" for value in values)
