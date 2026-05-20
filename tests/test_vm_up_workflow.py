import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

from fortress_workflows import CommandPhase, ConfirmationGate
from fortress_workflows.vm_lifecycle import build_vm_lifecycle_plan


REPO_ROOT = Path(__file__).resolve().parents[1]
MEDIA01_TARGETS = (
    '-target module.vms_wintermute.proxmox_virtual_environment_file.cloud_init_user_data["media01"] '
    '-target module.vms_wintermute.proxmox_virtual_environment_vm.vm["media01"]'
)


class VMUpWorkflowTests(unittest.TestCase):
    def test_vm_lifecycle_plan_declares_prepare_plan_confirmation_apply_configure(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, _calls_log = self._workflow_fixture(tmp)

            plan = build_vm_lifecycle_plan(root, "media01")

            self.assertEqual("vm-lifecycle:media01", plan.id)
            self.assertEqual(
                ["prepare", "tofu-plan", "confirm-apply", "tofu-apply", "configure"],
                [step.id for step in plan.steps],
            )
            prepare, tofu_plan, confirmation, tofu_apply, configure = plan.steps
            self.assertIsInstance(prepare, CommandPhase)
            self.assertEqual("Prepare", prepare.display_name)
            self.assertEqual([str(root / "scripts" / "vm-prepare"), "media01"], list(prepare.command))
            self.assertIsInstance(tofu_plan, CommandPhase)
            self.assertEqual(
                [
                    str(root / "scripts" / "tofu-wrap"),
                    "plan",
                    "-var",
                    "selected_vm=media01",
                    "-target",
                    'module.vms_wintermute.proxmox_virtual_environment_file.cloud_init_user_data["media01"]',
                    "-target",
                    'module.vms_wintermute.proxmox_virtual_environment_vm.vm["media01"]',
                ],
                list(tofu_plan.command),
            )
            self.assertIsInstance(confirmation, ConfirmationGate)
            self.assertEqual("Type 'apply media01' to apply the selected-VM plan: ", confirmation.prompt)
            self.assertEqual("apply media01", confirmation.required_input)
            self.assertIsInstance(tofu_apply, CommandPhase)
            self.assertEqual(
                [
                    str(root / "scripts" / "tofu-wrap"),
                    "apply",
                    "-var",
                    "selected_vm=media01",
                    "-target",
                    'module.vms_wintermute.proxmox_virtual_environment_file.cloud_init_user_data["media01"]',
                    "-target",
                    'module.vms_wintermute.proxmox_virtual_environment_vm.vm["media01"]',
                    "-auto-approve",
                ],
                list(tofu_apply.command),
            )
            self.assertIsInstance(configure, CommandPhase)
            self.assertEqual("Configure", configure.display_name)
            self.assertEqual([str(root / "scripts" / "vm-configure"), "media01"], list(configure.command))

    def test_just_vm_up_calls_workflow_script(self):
        justfile = (REPO_ROOT / "justfile").read_text()

        self.assertIn('vm-up vm auto_confirm="false":', justfile)
        self.assertIn("./scripts/vm-up {{vm}}", justfile)
        self.assertIn("--auto-confirm", justfile)
        self.assertIn('"{{auto_confirm}}" = "auto_confirm=true"', justfile)

    def test_vm_up_rejects_undeclared_vms_before_any_mutation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "inventory" / "vms").mkdir(parents=True)
            calls_log = root / "calls.log"
            env = os.environ.copy()
            env["FORTRESS_ROOT"] = str(root)
            env["CALLS_LOG"] = str(calls_log)

            result = subprocess.run(
                [str(REPO_ROOT / "scripts" / "vm-up"), "ghost"],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                input="apply ghost\n",
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            self.assertEqual(result.returncode, 1)
            self.assertIn("VM 'ghost' is not declared", result.stderr)
            self.assertFalse(calls_log.exists())

    def test_vm_up_runs_prepare_selected_plan_apply_then_configure_after_approval(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, calls_log = self._workflow_fixture(tmp)
            env = self._workflow_env(root, calls_log)

            result = subprocess.run(
                [str(REPO_ROOT / "scripts" / "vm-up"), "media01"],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                input="apply media01\n",
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(
                [
                    "vm-prepare media01",
                    f"tofu-wrap plan -var selected_vm=media01 {MEDIA01_TARGETS}",
                    f"tofu-wrap apply -var selected_vm=media01 {MEDIA01_TARGETS} -auto-approve",
                    "vm-configure media01",
                ],
                calls_log.read_text().splitlines(),
            )

    def test_vm_up_uses_satisfied_prepare_when_vm_ssh_material_already_exists(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, calls_log = self._workflow_fixture(tmp)
            (root / "inventory" / "vms" / "media01.sops.yaml").write_text(
                "ssh_keys:\n"
                "  bootstrap:\n"
                "    public_key: ENC[public]\n"
                "    private_key: ENC[private]\n"
            )
            env = self._workflow_env(root, calls_log)

            result = subprocess.run(
                [str(REPO_ROOT / "scripts" / "vm-up"), "media01"],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                input="apply media01\n",
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(
                [
                    "vm-prepare-satisfied media01",
                    f"tofu-wrap plan -var selected_vm=media01 {MEDIA01_TARGETS}",
                    f"tofu-wrap apply -var selected_vm=media01 {MEDIA01_TARGETS} -auto-approve",
                    "vm-configure media01",
                ],
                calls_log.read_text().splitlines(),
            )
            self.assertNotIn("vm-prepare media01", calls_log.read_text())

    def test_vm_up_runs_prepare_when_vm_sibling_sops_file_has_only_non_ssh_material(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, calls_log = self._workflow_fixture(tmp)
            (root / "inventory" / "vms" / "media01.sops.yaml").write_text(
                "tailnet:\n"
                "  auth_key:\n"
                "    value: ENC[auth]\n"
            )
            env = self._workflow_env(root, calls_log)

            result = subprocess.run(
                [str(REPO_ROOT / "scripts" / "vm-up"), "media01"],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                input="apply media01\n",
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual("vm-prepare media01", calls_log.read_text().splitlines()[0])

    def test_vm_up_stops_when_satisfied_prepare_probe_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, calls_log = self._workflow_fixture(tmp)
            (root / "inventory" / "vms" / "media01.sops.yaml").write_text(
                "ssh_keys:\n"
                "  bootstrap:\n"
                "    public_key: ENC[public]\n"
                "    private_key: ENC[private]\n"
            )
            env = self._workflow_env(root, calls_log)
            env["FORTRESS_FAIL_PHASE"] = "vm-prepare-satisfied"

            result = subprocess.run(
                [str(REPO_ROOT / "scripts" / "vm-up"), "media01"],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                input="apply media01\n",
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            self.assertEqual(result.returncode, 42)
            self.assertIn("Prepare satisfaction failed for VM media01", result.stderr)
            self.assertEqual(["vm-prepare-satisfied media01"], calls_log.read_text().splitlines())

    def test_vm_up_shows_selected_plan_output_before_approval(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, _calls_log = self._workflow_fixture(tmp)
            env = self._workflow_env(root, root / "calls.log")
            env["FORTRESS_TOFU_PLAN_STDOUT"] = "selected plan output"

            result = subprocess.run(
                [str(REPO_ROOT / "scripts" / "vm-up"), "media01"],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                input="apply media01\n",
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("selected plan output", result.stdout)
            self.assertLess(
                result.stdout.index("selected plan output"),
                result.stdout.index("Type 'apply media01'"),
            )

    def test_vm_up_denies_apply_without_explicit_matching_approval(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, calls_log = self._workflow_fixture(tmp)
            env = self._workflow_env(root, calls_log)

            result = subprocess.run(
                [str(REPO_ROOT / "scripts" / "vm-up"), "media01"],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                input="yes\n",
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            self.assertEqual(result.returncode, 1)
            self.assertIn("Apply denied for VM media01", result.stderr)
            self.assertEqual(
                [
                    "vm-prepare media01",
                    f"tofu-wrap plan -var selected_vm=media01 {MEDIA01_TARGETS}",
                ],
                calls_log.read_text().splitlines(),
            )

    def test_vm_up_auto_confirm_skips_interactive_approval(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, calls_log = self._workflow_fixture(tmp)
            env = self._workflow_env(root, calls_log)

            result = subprocess.run(
                [str(REPO_ROOT / "scripts" / "vm-up"), "media01", "--auto-confirm"],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(
                [
                    "vm-prepare media01",
                    f"tofu-wrap plan -var selected_vm=media01 {MEDIA01_TARGETS}",
                    f"tofu-wrap apply -var selected_vm=media01 {MEDIA01_TARGETS} -auto-approve",
                    "vm-configure media01",
                ],
                calls_log.read_text().splitlines(),
            )

    def test_vm_up_rejects_unknown_flags(self):
        result = subprocess.run(
            [str(REPO_ROOT / "scripts" / "vm-up"), "media01", "--yes"],
            cwd=REPO_ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        self.assertEqual(result.returncode, 2)
        self.assertIn("usage: scripts/vm-up <vm> [--auto-confirm]", result.stderr)

    def test_vm_up_stops_and_reports_the_failed_phase(self):
        scenarios = {
            "vm-prepare": (
                "Prepare failed for VM media01",
                ["vm-prepare media01"],
            ),
            "tofu-plan": (
                "tofu plan failed for VM media01",
                ["vm-prepare media01", f"tofu-wrap plan -var selected_vm=media01 {MEDIA01_TARGETS}"],
            ),
            "tofu-apply": (
                "tofu apply failed for VM media01",
                [
                    "vm-prepare media01",
                    f"tofu-wrap plan -var selected_vm=media01 {MEDIA01_TARGETS}",
                    f"tofu-wrap apply -var selected_vm=media01 {MEDIA01_TARGETS} -auto-approve",
                ],
            ),
            "vm-configure": (
                "Configure failed for VM media01",
                [
                    "vm-prepare media01",
                    f"tofu-wrap plan -var selected_vm=media01 {MEDIA01_TARGETS}",
                    f"tofu-wrap apply -var selected_vm=media01 {MEDIA01_TARGETS} -auto-approve",
                    "vm-configure media01",
                ],
            ),
        }

        for failed_phase, (message, expected_calls) in scenarios.items():
            with self.subTest(failed_phase=failed_phase), tempfile.TemporaryDirectory() as tmp:
                root, calls_log = self._workflow_fixture(tmp)
                env = self._workflow_env(root, calls_log)
                env["FORTRESS_FAIL_PHASE"] = failed_phase

                result = subprocess.run(
                    [str(REPO_ROOT / "scripts" / "vm-up"), "media01"],
                    cwd=REPO_ROOT,
                    env=env,
                    text=True,
                    input="apply media01\n",
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )

                self.assertEqual(result.returncode, 42)
                self.assertIn(message, result.stderr)
                self.assertEqual(expected_calls, calls_log.read_text().splitlines())

    def test_vm_up_reports_missing_phase_command_as_failed_phase(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, _calls_log = self._workflow_fixture(tmp)
            (root / "scripts" / "vm-prepare").unlink()
            env = self._workflow_env(root, root / "calls.log")

            result = subprocess.run(
                [str(REPO_ROOT / "scripts" / "vm-up"), "media01"],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                input="apply media01\n",
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            self.assertEqual(result.returncode, 1)
            self.assertIn("Prepare failed for VM media01", result.stderr)

    def _workflow_fixture(self, tmp):
        root = Path(tmp)
        vm_dir = root / "inventory" / "vms"
        scripts_dir = root / "scripts"
        vm_dir.mkdir(parents=True)
        scripts_dir.mkdir()
        (vm_dir / "media01.yaml").write_text(
            "vmid: 101\n"
            "placement:\n"
            "  host: wintermute\n"
        )
        calls_log = root / "calls.log"
        for name in ["vm-prepare", "vm-prepare-satisfied", "tofu-wrap", "vm-configure"]:
            script = scripts_dir / name
            script.write_text(
                "#!/usr/bin/env bash\n"
                "name=$(basename \"$0\")\n"
                "printf '%s %s\\n' \"$name\" \"$*\" >> \"$CALLS_LOG\"\n"
                "phase=\"$name\"\n"
                "if [ \"$name\" = tofu-wrap ]; then phase=\"tofu-$1\"; fi\n"
                "if [ \"$phase\" = tofu-plan ] && [ -n \"$FORTRESS_TOFU_PLAN_STDOUT\" ]; then echo \"$FORTRESS_TOFU_PLAN_STDOUT\"; fi\n"
                "if [ \"$FORTRESS_FAIL_PHASE\" = \"$phase\" ]; then exit 42; fi\n"
            )
            script.chmod(script.stat().st_mode | stat.S_IXUSR)
        return root, calls_log

    def _workflow_env(self, root, calls_log):
        env = os.environ.copy()
        env["FORTRESS_ROOT"] = str(root)
        env["CALLS_LOG"] = str(calls_log)
        return env


if __name__ == "__main__":
    unittest.main()
