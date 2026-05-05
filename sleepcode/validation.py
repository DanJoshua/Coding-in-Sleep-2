from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Callable

from .models import ValidationResult
from .util import write_json, write_text

RunCallable = Callable[..., subprocess.CompletedProcess[str]]

PYTHON_SMOKE = r"""
import os
import pathlib
import py_compile
import sys
import tempfile

skip = {'.git', '.hg', '.svn', '.venv', 'venv', 'env', '__pycache__', 'node_modules'}
checked = 0
failed = 0
with tempfile.TemporaryDirectory(prefix='sleepcode-pycompile-') as tmp:
    cfile = os.path.join(tmp, 'out.pyc')
    for path in sorted(pathlib.Path('.').rglob('*.py')):
        if any(part in skip for part in path.parts):
            continue
        checked += 1
        try:
            py_compile.compile(str(path), cfile=cfile, doraise=True)
        except Exception as exc:
            failed += 1
            print(f'{path}: {exc}', file=sys.stderr)
print(f'checked {checked} Python files')
sys.exit(1 if failed else 0)
""".strip()


class Validator:
    def __init__(self, explicit_command: str | None = None, runner: RunCallable | None = None):
        self.explicit_command = explicit_command
        self.runner = runner or subprocess.run

    def run(self, worktree: Path, artifact_dir: Path) -> ValidationResult:
        artifact_dir.mkdir(parents=True, exist_ok=True)
        log_path = artifact_dir / "validation.log"
        command, shell, kind = self._detect(worktree)
        write_text(artifact_dir / "validation_command.txt", command if isinstance(command, str) else " ".join(command))
        env = os.environ.copy()
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        with log_path.open("w", encoding="utf-8") as log:
            result = self.runner(command, cwd=worktree, shell=shell, text=True, stdout=log, stderr=subprocess.STDOUT, check=False, env=env)
        returncode = int(result.returncode)
        if kind in {"explicit", "candidate_tests"}:
            status = "pass" if returncode == 0 else "fail"
        elif kind == "smoke":
            status = "smoke" if returncode == 0 else "fail"
        else:
            status = "unknown"
        metadata = {"kind": kind}
        validation = ValidationResult(command=command, status=status, returncode=returncode, log_path=log_path, metadata=metadata)
        write_json(
            artifact_dir / "validation.json",
            {
                "command": command,
                "status": status,
                "returncode": returncode,
                "metadata": metadata,
                "log_path": str(log_path),
            },
        )
        return validation

    def _detect(self, worktree: Path) -> tuple[list[str] | str, bool, str]:
        if self.explicit_command:
            return self.explicit_command, True, "explicit"
        candidate_tests = worktree / ".sleepcode" / "tests"
        if candidate_tests.is_dir() and any(candidate_tests.rglob("test*.py")):
            return [sys.executable, "-m", "unittest", "discover", "-s", ".sleepcode/tests"], False, "candidate_tests"
        if self._has_python(worktree):
            return [sys.executable, "-c", PYTHON_SMOKE], False, "smoke"
        return [sys.executable, "-c", "print('no validation available')"], False, "none"

    @staticmethod
    def _has_python(worktree: Path) -> bool:
        if (worktree / "pyproject.toml").exists() or (worktree / "setup.py").exists():
            return True
        for path in worktree.rglob("*.py"):
            if ".git" not in path.parts:
                return True
        return False
