from __future__ import annotations

import json
import os
import selectors
import signal
import subprocess
import time
from pathlib import Path

from .models import CommandResult
from .util import command_display, read_text, write_text

SUPPORTED_AGENTS = ("codex", "kimi")
CODEX_REASONING_EFFORTS = ("low", "medium", "high", "xhigh")


class AgentRunner:
    def __init__(
        self,
        *,
        model: str | None = None,
        sandbox: str = "workspace-write",
        timeout_seconds: int = 3600,
        startup_timeout_seconds: int = 120,
        idle_timeout_seconds: int = 300,
        kimi_idle_timeout_seconds: int | None = None,
    ):
        self.model = model
        self.sandbox = sandbox
        self.timeout_seconds = timeout_seconds
        self.startup_timeout_seconds = startup_timeout_seconds
        self.idle_timeout_seconds = idle_timeout_seconds
        self.kimi_idle_timeout_seconds = kimi_idle_timeout_seconds

    def build_command(
        self,
        *,
        agent: str,
        role: str,
        worktree: Path,
        final_message_path: Path,
        sandbox: str,
        reasoning_effort: str | None = None,
        plan_mode: bool = False,
        extra_context_dirs: tuple[Path, ...] = (),
    ) -> list[str]:
        agent = normalize_agent(agent)
        if agent == "kimi":
            command = ["kimi", "--work-dir", str(worktree)]
            for context_dir in extra_context_dirs:
                command.extend(["--add-dir", str(context_dir)])
            if self.model:
                command.extend(["--model", self.model])
            command.extend(["--print", "--output-format=stream-json"])
            if plan_mode:
                command.append("--plan")
            return command

        command = [
            "codex",
            "exec",
            "--json",
            "--cd",
            str(worktree),
            "--sandbox",
            sandbox,
            "--ephemeral",
            "--ignore-user-config",
            "--output-last-message",
            str(final_message_path),
        ]
        for context_dir in extra_context_dirs:
            command.extend(["--add-dir", str(context_dir)])
        for feature in ("apps", "plugins", "browser_use", "computer_use", "image_generation", "tool_search", "tool_suggest"):
            command.extend(["--disable", feature])
        if reasoning_effort:
            command.extend(["-c", f'model_reasoning_effort="{reasoning_effort}"'])
        if self.model:
            command.extend(["--model", self.model])
        command.append("-")
        return command

    def run(
        self,
        *,
        agent: str,
        role: str,
        worktree: Path,
        prompt: str,
        artifact_dir: Path,
        final_filename: str,
        sandbox: str,
        reasoning_effort: str | None = None,
        plan_mode: bool = False,
        extra_context_dirs: tuple[Path, ...] = (),
    ) -> CommandResult:
        agent = normalize_agent(agent)
        artifact_dir.mkdir(parents=True, exist_ok=True)
        prompt_path = artifact_dir / f"{role}_prompt.md"
        log_path = artifact_dir / self._log_name(role, agent)
        final_path = artifact_dir / final_filename
        write_text(prompt_path, prompt)
        command = self.build_command(
            agent=agent,
            role=role,
            worktree=worktree,
            final_message_path=final_path,
            sandbox=sandbox,
            reasoning_effort=reasoning_effort,
            plan_mode=plan_mode,
            extra_context_dirs=extra_context_dirs,
        )
        returncode, timed_out, reason = self._run_process(
            command,
            prompt,
            cwd=worktree,
            log_path=log_path,
            idle_timeout_seconds=self._idle_timeout_for(agent),
        )

        if agent == "kimi":
            final = _kimi_final_message_from_log(read_text(log_path))
            if final is not None:
                write_text(final_path, final.rstrip() + "\n")
        if not final_path.exists():
            write_text(final_path, "")
        return CommandResult(
            command=command,
            returncode=returncode,
            log_path=log_path,
            final_message_path=final_path,
            timed_out=timed_out,
            reason=reason,
        )

    def _run_process(
        self,
        command: list[str],
        prompt: str,
        *,
        cwd: Path,
        log_path: Path,
        idle_timeout_seconds: int | None,
    ) -> tuple[int, bool, str | None]:
        process = subprocess.Popen(
            command,
            cwd=cwd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            env=self._clean_env(),
            start_new_session=True,
        )
        started = time.monotonic()
        last_output = started
        saw_output = False
        reason: str | None = None
        selector = selectors.DefaultSelector()
        assert process.stdout is not None
        os.set_blocking(process.stdout.fileno(), False)
        selector.register(process.stdout, selectors.EVENT_READ)
        try:
            assert process.stdin is not None
            process.stdin.write(prompt.encode("utf-8"))
            process.stdin.close()
            with log_path.open("wb") as log:
                while True:
                    for key, _ in selector.select(timeout=0.25):
                        try:
                            chunk = os.read(key.fileobj.fileno(), 65536)
                        except BlockingIOError:
                            continue
                        if chunk:
                            saw_output = True
                            last_output = time.monotonic()
                            log.write(chunk)
                            log.flush()
                    if process.poll() is not None:
                        self._drain(process, log)
                        return int(process.returncode), False, None
                    now = time.monotonic()
                    if now - started > self.timeout_seconds:
                        reason = "timeout"
                    elif not saw_output and now - started > self.startup_timeout_seconds:
                        reason = "startup_timeout"
                    elif saw_output and idle_timeout_seconds is not None and now - last_output > idle_timeout_seconds:
                        reason = "idle_timeout"
                    if reason:
                        log.write(("\n" + json.dumps({"type": "sleepcode.timeout", "reason": reason}) + "\n").encode("utf-8"))
                        log.flush()
                        self._terminate(process)
                        self._drain(process, log)
                        return int(process.returncode or 124), True, reason
        finally:
            try:
                selector.unregister(process.stdout)
            except Exception:
                pass
            selector.close()
            if process.stdout is not None:
                process.stdout.close()

    def _idle_timeout_for(self, agent: str) -> int | None:
        if agent == "kimi":
            return self.kimi_idle_timeout_seconds
        return self.idle_timeout_seconds

    @staticmethod
    def _drain(process: subprocess.Popen[bytes], log) -> None:
        if process.stdout is None:
            return
        while True:
            try:
                chunk = os.read(process.stdout.fileno(), 65536)
            except (BlockingIOError, ValueError):
                return
            if not chunk:
                return
            log.write(chunk)
            log.flush()

    @staticmethod
    def _terminate(process: subprocess.Popen[bytes]) -> None:
        if process.poll() is not None:
            return
        try:
            os.killpg(process.pid, signal.SIGTERM)
            process.wait(timeout=5)
        except ProcessLookupError:
            return
        except subprocess.TimeoutExpired:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                return
            process.wait(timeout=5)

    @staticmethod
    def _log_name(role: str, agent: str) -> str:
        if agent == "codex":
            return f"{role}.codex.jsonl"
        return f"{role}.{agent}.jsonl"

    @staticmethod
    def _clean_env() -> dict[str, str]:
        env = os.environ.copy()
        for key in list(env):
            if key == "CODEX_THREAD_ID" or key.startswith("__CODEX_SNAPSHOT_"):
                env.pop(key, None)
        env.setdefault("NO_COLOR", "1")
        return env


def normalize_agent(agent: str) -> str:
    normalized = agent.strip().lower()
    if normalized not in SUPPORTED_AGENTS:
        allowed = ", ".join(SUPPORTED_AGENTS)
        raise ValueError(f"unsupported agent {agent!r}; supported agents: {allowed}")
    return normalized


def display_command(command: list[str] | str) -> str:
    return command_display(command)


def _kimi_final_message_from_log(text: str) -> str | None:
    final: str | None = None
    plain_lines: list[str] = []
    for line in text.splitlines():
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            plain_lines.append(line)
            continue
        if not isinstance(event, dict):
            continue
        if event.get("role") != "assistant":
            continue
        content = _content_to_text(event.get("content"))
        if content.strip():
            final = content
    if final is not None:
        return final
    return "\n".join(plain_lines).strip() or None


def _content_to_text(content: object) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, dict):
        text = content.get("text")
        return text if isinstance(text, str) else ""
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                text = item.get("text")
                if isinstance(text, str):
                    parts.append(text)
        return "\n".join(parts)
    return ""
