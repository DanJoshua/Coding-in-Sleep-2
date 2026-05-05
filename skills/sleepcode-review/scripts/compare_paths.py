#!/usr/bin/env python3
"""Compare two local filesystems paths and emit a stable summary."""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import os
from pathlib import Path
from typing import Iterable

DEFAULT_EXCLUDES = (
    ".git",
    ".venv",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "dist",
    "build",
    "target",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare two files or directory trees and summarize differences."
    )
    parser.add_argument("path_a", help="First path to compare")
    parser.add_argument("path_b", help="Second path to compare")
    parser.add_argument(
        "--exclude",
        action="append",
        default=[],
        metavar="PATTERN",
        help="Extra glob-style pattern to ignore; may be passed multiple times",
    )
    parser.add_argument(
        "--format",
        choices=("json", "text"),
        default="json",
        help="Output format",
    )
    parser.add_argument(
        "--max-files",
        type=int,
        default=200,
        help="Maximum number of differing paths to include in each list",
    )
    return parser.parse_args()


def should_exclude(relative_path: str, patterns: Iterable[str]) -> bool:
    parts = relative_path.split("/")
    for pattern in patterns:
        if any(fnmatch.fnmatch(part, pattern) for part in parts):
            return True
        if fnmatch.fnmatch(relative_path, pattern):
            return True
    return False


def file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def collect_entries(root: Path, excludes: Iterable[str]) -> dict[str, dict[str, object]]:
    if root.is_file():
        return {
            ".": {
                "kind": "file",
                "digest": file_digest(root),
                "size": root.stat().st_size,
            }
        }

    entries: dict[str, dict[str, object]] = {}
    for current_root, dirnames, filenames in os.walk(root, topdown=True):
        current_root_path = Path(current_root)
        relative_root = current_root_path.relative_to(root).as_posix()
        if relative_root != "." and should_exclude(relative_root, excludes):
            dirnames[:] = []
            continue

        kept_dirs: list[str] = []
        for dirname in sorted(dirnames):
            dir_relative = (current_root_path / dirname).relative_to(root).as_posix()
            if should_exclude(dir_relative, excludes):
                continue
            entries[dir_relative] = {"kind": "dir"}
            kept_dirs.append(dirname)
        dirnames[:] = kept_dirs

        for filename in sorted(filenames):
            file_path = current_root_path / filename
            file_relative = file_path.relative_to(root).as_posix()
            if should_exclude(file_relative, excludes):
                continue
            entries[file_relative] = {
                "kind": "file",
                "digest": file_digest(file_path),
                "size": file_path.stat().st_size,
            }
    return entries


def summarize(
    path_a: Path,
    path_b: Path,
    excludes: list[str],
    max_files: int,
) -> dict[str, object]:
    if not path_a.exists():
        raise FileNotFoundError(f"path_a does not exist: {path_a}")
    if not path_b.exists():
        raise FileNotFoundError(f"path_b does not exist: {path_b}")

    if path_a.is_dir() != path_b.is_dir():
        return {
            "path_a": str(path_a),
            "path_b": str(path_b),
            "type_mismatch": True,
            "path_a_kind": "dir" if path_a.is_dir() else "file",
            "path_b_kind": "dir" if path_b.is_dir() else "file",
        }

    patterns = list(DEFAULT_EXCLUDES) + excludes
    entries_a = collect_entries(path_a, patterns)
    entries_b = collect_entries(path_b, patterns)

    keys_a = set(entries_a)
    keys_b = set(entries_b)
    only_a = sorted(keys_a - keys_b)
    only_b = sorted(keys_b - keys_a)

    changed: list[str] = []
    same_count = 0
    for key in sorted(keys_a & keys_b):
        left = entries_a[key]
        right = entries_b[key]
        if left["kind"] != right["kind"]:
            changed.append(key)
        elif left["kind"] == "file":
            if left["digest"] != right["digest"]:
                changed.append(key)
            else:
                same_count += 1
        else:
            same_count += 1

    return {
        "path_a": str(path_a),
        "path_b": str(path_b),
        "type_mismatch": False,
        "excluded_patterns": patterns,
        "summary": {
            "only_in_a": len(only_a),
            "only_in_b": len(only_b),
            "changed": len(changed),
            "same": same_count,
        },
        "only_in_a": only_a[:max_files],
        "only_in_b": only_b[:max_files],
        "changed": changed[:max_files],
        "truncated": {
            "only_in_a": len(only_a) > max_files,
            "only_in_b": len(only_b) > max_files,
            "changed": len(changed) > max_files,
        },
    }


def render_text(result: dict[str, object]) -> str:
    lines = [
        f"path_a: {result['path_a']}",
        f"path_b: {result['path_b']}",
    ]
    if result.get("type_mismatch"):
        lines.append(
            f"type mismatch: {result['path_a_kind']} vs {result['path_b_kind']}"
        )
        return "\n".join(lines)

    summary = result["summary"]
    lines.append(
        "summary: "
        f"only_in_a={summary['only_in_a']}, "
        f"only_in_b={summary['only_in_b']}, "
        f"changed={summary['changed']}, "
        f"same={summary['same']}"
    )

    for key in ("only_in_a", "only_in_b", "changed"):
        values = result[key]
        lines.append(f"{key}:")
        if values:
            lines.extend(f"  - {value}" for value in values)
        else:
            lines.append("  - <none>")
        if result["truncated"][key]:
            lines.append("  - ... truncated ...")
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    result = summarize(
        Path(args.path_a).resolve(),
        Path(args.path_b).resolve(),
        args.exclude,
        args.max_files,
    )

    if args.format == "text":
        print(render_text(result))
    else:
        print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
