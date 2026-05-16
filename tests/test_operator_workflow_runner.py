import io
import stat
import tempfile
import unittest
from pathlib import Path

from fortress_workflows import (
    CommandPhase,
    ConfirmationGate,
    FailurePolicy,
    OperatorWorkflowPlan,
    OperatorWorkflowRunner,
)


class OperatorWorkflowRunnerTests(unittest.TestCase):
    def test_runs_command_phases_in_plan_order_and_returns_structured_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            calls_log = root / "calls.log"
            first = self._script(root, "first", calls_log)
            second = self._script(root, "second", calls_log)
            plan = OperatorWorkflowPlan(
                id="demo",
                steps=[
                    CommandPhase(
                        id="first",
                        display_name="First",
                        command=[str(first)],
                        diagnostic_label="first phase",
                    ),
                    CommandPhase(
                        id="second",
                        display_name="Second",
                        command=[str(second)],
                        diagnostic_label="second phase",
                    ),
                ],
            )

            result = OperatorWorkflowRunner(cwd=root, output=io.StringIO()).run(plan)

            self.assertTrue(result.success)
            self.assertEqual(0, result.return_code)
            self.assertEqual(["first", "second"], calls_log.read_text().splitlines())
            self.assertEqual(["first", "second"], [phase.step_id for phase in result.phase_results])
            self.assertEqual(["passed", "passed"], [phase.status for phase in result.phase_results])
            self.assertEqual([str(first)], result.phase_results[0].command)

    def test_stops_immediately_when_a_phase_with_stop_policy_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            calls_log = root / "calls.log"
            first = self._script(root, "first", calls_log, body="echo broken >&2\nexit 42\n")
            second = self._script(root, "second", calls_log)
            plan = OperatorWorkflowPlan(
                id="demo",
                steps=[
                    CommandPhase(
                        id="first",
                        display_name="First",
                        command=[str(first)],
                        diagnostic_label="first phase",
                    ),
                    CommandPhase(
                        id="second",
                        display_name="Second",
                        command=[str(second)],
                        diagnostic_label="second phase",
                    ),
                ],
            )

            result = OperatorWorkflowRunner(cwd=root, output=io.StringIO()).run(plan)

            self.assertFalse(result.success)
            self.assertEqual(42, result.return_code)
            self.assertEqual(["first"], calls_log.read_text().splitlines())
            self.assertEqual(["first"], [phase.step_id for phase in result.phase_results])
            failed = result.phase_results[0]
            self.assertEqual("failed", failed.status)
            self.assertEqual(42, failed.return_code)
            self.assertEqual("broken", failed.failure_detail)

    def test_continues_after_a_phase_with_continue_policy_fails_and_returns_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            calls_log = root / "calls.log"
            first = self._script(root, "first", calls_log, body="echo warning >&2\nexit 3\n")
            second = self._script(root, "second", calls_log)
            plan = OperatorWorkflowPlan(
                id="demo",
                steps=[
                    CommandPhase(
                        id="first",
                        display_name="First",
                        command=[str(first)],
                        diagnostic_label="first phase",
                        failure_policy=FailurePolicy.CONTINUE,
                    ),
                    CommandPhase(
                        id="second",
                        display_name="Second",
                        command=[str(second)],
                        diagnostic_label="second phase",
                    ),
                ],
            )

            result = OperatorWorkflowRunner(cwd=root, output=io.StringIO()).run(plan)

            self.assertFalse(result.success)
            self.assertEqual(3, result.return_code)
            self.assertEqual(["first", "second"], calls_log.read_text().splitlines())
            self.assertEqual(["failed", "passed"], [phase.status for phase in result.phase_results])

    def test_confirmation_gate_denial_stops_before_later_phases(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            calls_log = root / "calls.log"
            later = self._script(root, "later", calls_log)
            plan = OperatorWorkflowPlan(
                id="demo",
                steps=[
                    ConfirmationGate(
                        id="apply",
                        display_name="Apply",
                        prompt="Type 'apply demo' to continue: ",
                        required_input="apply demo",
                    ),
                    CommandPhase(
                        id="later",
                        display_name="Later",
                        command=[str(later)],
                        diagnostic_label="later phase",
                    ),
                ],
            )

            output = io.StringIO()
            result = OperatorWorkflowRunner(cwd=root, input=io.StringIO("no\n"), output=output).run(plan)

            self.assertFalse(result.success)
            self.assertEqual(1, result.return_code)
            self.assertFalse(calls_log.exists())
            self.assertEqual(["apply"], [gate.step_id for gate in result.gate_results])
            self.assertEqual("denied", result.gate_results[0].status)
            self.assertIn("Type 'apply demo' to continue: ", output.getvalue())

    def test_auto_confirm_satisfies_confirmation_gates_without_reading_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            calls_log = root / "calls.log"
            later = self._script(root, "later", calls_log)
            plan = OperatorWorkflowPlan(
                id="demo",
                steps=[
                    ConfirmationGate(
                        id="apply",
                        display_name="Apply",
                        prompt="Type 'apply demo' to continue: ",
                        required_input="apply demo",
                    ),
                    CommandPhase(
                        id="later",
                        display_name="Later",
                        command=[str(later)],
                        diagnostic_label="later phase",
                    ),
                ],
            )

            output = io.StringIO()
            result = OperatorWorkflowRunner(
                cwd=root,
                input=io.StringIO("wrong\n"),
                output=output,
                auto_confirm=True,
            ).run(plan)

            self.assertTrue(result.success)
            self.assertEqual(["later"], calls_log.read_text().splitlines())
            self.assertEqual("auto-confirmed", result.gate_results[0].status)
            self.assertEqual("", output.getvalue())

    def test_streaming_phase_prefixes_output_and_retains_bounded_tail(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            calls_log = root / "calls.log"
            script = self._script(
                root,
                "stream",
                calls_log,
                body="printf 'one\\n'; printf 'two\\n'; printf 'three\\n'\n",
            )
            plan = OperatorWorkflowPlan(
                id="demo",
                steps=[
                    CommandPhase(
                        id="stream",
                        display_name="Stream",
                        command=[str(script)],
                        diagnostic_label="stream phase",
                        streaming=True,
                    )
                ],
            )
            output = io.StringIO()

            result = OperatorWorkflowRunner(cwd=root, output=output, tail_lines=2).run(plan)

            self.assertTrue(result.success)
            self.assertEqual("[stream] one\n[stream] two\n[stream] three\n", output.getvalue())
            self.assertEqual("two\nthree\n", result.phase_results[0].tail)
            self.assertEqual("", result.phase_results[0].stdout)
            self.assertEqual("", result.phase_results[0].stderr)

    def test_failure_detail_uses_standard_precedence_for_streaming_and_non_streaming_phases(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            calls_log = root / "calls.log"
            stderr_wins = self._script(
                root,
                "stderr-wins",
                calls_log,
                body="echo stdout-detail; echo stderr-detail >&2; exit 5\n",
            )
            stdout_fallback = self._script(
                root,
                "stdout-fallback",
                calls_log,
                body="echo stdout-detail; exit 6\n",
            )
            streaming_tail = self._script(
                root,
                "streaming-tail",
                calls_log,
                body="echo stream-detail; echo ignored-stderr >&2; exit 7\n",
            )
            plan = OperatorWorkflowPlan(
                id="demo",
                steps=[
                    CommandPhase(
                        id="stderr-wins",
                        display_name="Stderr Wins",
                        command=[str(stderr_wins)],
                        diagnostic_label="stderr phase",
                        failure_policy=FailurePolicy.CONTINUE,
                    ),
                    CommandPhase(
                        id="stdout-fallback",
                        display_name="Stdout Fallback",
                        command=[str(stdout_fallback)],
                        diagnostic_label="stdout phase",
                        failure_policy=FailurePolicy.CONTINUE,
                    ),
                    CommandPhase(
                        id="exit-fallback",
                        display_name="Exit Fallback",
                        command=["bash", "-c", "exit 8"],
                        diagnostic_label="exit phase",
                        failure_policy=FailurePolicy.CONTINUE,
                    ),
                    CommandPhase(
                        id="streaming-tail",
                        display_name="Streaming Tail",
                        command=[str(streaming_tail)],
                        diagnostic_label="streaming phase",
                        streaming=True,
                        failure_policy=FailurePolicy.CONTINUE,
                    ),
                ],
            )

            result = OperatorWorkflowRunner(cwd=root, output=io.StringIO()).run(plan)

            self.assertFalse(result.success)
            self.assertEqual(
                ["stderr-detail", "stdout-detail", "exit 8", "stream-detail\nignored-stderr"],
                [phase.failure_detail for phase in result.phase_results],
            )
            self.assertEqual("stdout-detail\n", result.phase_results[0].stdout)
            self.assertEqual("stderr-detail\n", result.phase_results[0].stderr)

    def _script(self, root, name, calls_log, body=""):
        path = root / name
        path.write_text(
            "#!/usr/bin/env bash\n"
            f"printf '%s\\n' {name!r} >> {str(calls_log)!r}\n"
            f"{body}"
        )
        path.chmod(path.stat().st_mode | stat.S_IXUSR)
        return path


if __name__ == "__main__":
    unittest.main()
