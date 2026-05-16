from __future__ import annotations

from dataclasses import dataclass
from collections import deque
from enum import StrEnum
import os
from pathlib import Path
import subprocess
import sys
from typing import Sequence, TextIO


class FailurePolicy(StrEnum):
    STOP = "stop"
    CONTINUE = "continue"


@dataclass(frozen=True)
class CommandPhase:
    id: str
    display_name: str
    command: Sequence[str]
    diagnostic_label: str
    streaming: bool = False
    failure_policy: FailurePolicy = FailurePolicy.STOP


@dataclass(frozen=True)
class ConfirmationGate:
    id: str
    display_name: str
    prompt: str
    required_input: str


@dataclass(frozen=True)
class OperatorWorkflowPlan:
    id: str
    steps: Sequence[CommandPhase | ConfirmationGate]


@dataclass(frozen=True)
class PhaseResult:
    step_id: str
    status: str
    command: list[str]
    return_code: int
    stdout: str
    stderr: str
    tail: str
    failure_detail: str


@dataclass(frozen=True)
class GateResult:
    step_id: str
    status: str


@dataclass(frozen=True)
class WorkflowResult:
    success: bool
    return_code: int
    phase_results: list[PhaseResult]
    gate_results: list[GateResult]


class OperatorWorkflowRunner:
    def __init__(
        self,
        cwd: Path,
        input: TextIO | None = None,
        output: TextIO | None = None,
        auto_confirm: bool = False,
        tail_lines: int = 200,
    ):
        self.cwd = cwd
        self.input = input or sys.stdin
        self.output = output or sys.stdout
        self.auto_confirm = auto_confirm
        self.tail_lines = tail_lines

    def run(self, plan: OperatorWorkflowPlan) -> WorkflowResult:
        phase_results = []
        gate_results = []
        first_failure_code = 0
        for step in plan.steps:
            if isinstance(step, ConfirmationGate):
                gate_result = self._run_gate(step)
                gate_results.append(gate_result)
                if gate_result.status == "denied":
                    return WorkflowResult(False, 1, phase_results, gate_results)
                continue

            result = self._run_phase(step)
            phase_results.append(result)
            if result.status == "failed":
                if first_failure_code == 0:
                    first_failure_code = result.return_code or 1
                if step.failure_policy == FailurePolicy.STOP:
                    return WorkflowResult(False, first_failure_code, phase_results, gate_results)
        return WorkflowResult(first_failure_code == 0, first_failure_code, phase_results, gate_results)

    def _run_gate(self, gate: ConfirmationGate) -> GateResult:
        if self.auto_confirm:
            return GateResult(step_id=gate.id, status="auto-confirmed")
        print(gate.prompt, end="", file=self.output, flush=True)
        response = self.input.readline().rstrip("\n")
        status = "confirmed" if response == gate.required_input else "denied"
        return GateResult(step_id=gate.id, status=status)

    def _run_phase(self, phase: CommandPhase) -> PhaseResult:
        command = list(phase.command)
        if phase.streaming:
            return self._run_streaming_phase(phase, command)
        try:
            completed = subprocess.run(
                command,
                cwd=self.cwd,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
        except OSError as error:
            return PhaseResult(
                step_id=phase.id,
                status="failed",
                command=command,
                return_code=1,
                stdout="",
                stderr=str(error),
                tail="",
                failure_detail=str(error),
            )

        failed = completed.returncode != 0
        return PhaseResult(
            step_id=phase.id,
            status="failed" if failed else "passed",
            command=command,
            return_code=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
            tail="",
            failure_detail=phase_detail(completed.stderr, completed.stdout, completed.returncode) if failed else "",
        )

    def _run_streaming_phase(self, phase: CommandPhase, command: list[str]) -> PhaseResult:
        try:
            process = subprocess.Popen(
                command,
                cwd=self.cwd,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                bufsize=1,
            )
        except OSError as error:
            return PhaseResult(
                step_id=phase.id,
                status="failed",
                command=command,
                return_code=1,
                stdout="",
                stderr=str(error),
                tail="",
                failure_detail=str(error),
            )

        tail = deque(maxlen=self.tail_lines)
        pending = ""
        at_line_start = True
        assert process.stdout is not None
        try:
            while True:
                chunk = os.read(process.stdout.fileno(), 4096)
                if not chunk:
                    break
                text = chunk.decode(errors="replace")
                for piece in text.splitlines(True):
                    if at_line_start:
                        print(f"[{phase.id}] ", end="", file=self.output, flush=True)
                    print(piece, end="", file=self.output, flush=True)
                    at_line_start = piece.endswith("\n")
                pending += text
                while "\n" in pending:
                    line, pending = pending.split("\n", 1)
                    tail.append(line + "\n")
            return_code = process.wait()
        finally:
            process.stdout.close()
        if pending:
            tail.append(pending)
        tail_text = "".join(tail)
        failed = return_code != 0
        return PhaseResult(
            step_id=phase.id,
            status="failed" if failed else "passed",
            command=command,
            return_code=return_code,
            stdout="",
            stderr="",
            tail=tail_text,
            failure_detail=streaming_phase_detail(tail_text, "", return_code) if failed else "",
        )


def phase_detail(stderr: str, stdout: str, return_code: int) -> str:
    return (stderr or stdout).strip() or f"exit {return_code}"


def streaming_phase_detail(tail: str, stderr: str, return_code: int) -> str:
    return (tail or stderr).strip() or f"exit {return_code}"
