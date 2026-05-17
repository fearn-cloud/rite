import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

from fortress_workflows import CommandPhase, ConfirmationGate
from fortress_workflows.service_update import build_service_update_plan

REPO_ROOT = Path(__file__).resolve().parents[1]
IMMICH_ACTIVE_CHECK = (
    'for unit in fortress-immich-postgres.service fortress-immich-redis.service '
    'fortress-immich-server.service; do sudo systemctl is-active --quiet "$unit" || exit $?; done'
)


class ServiceUpdateWorkflowTests(unittest.TestCase):
    def test_just_service_update_calls_workflow_script(self):
        justfile = (REPO_ROOT / "justfile").read_text()

        self.assertIn('service-update service auto_confirm="false":', justfile)
        self.assertIn("./scripts/service-update {{service}}", justfile)
        self.assertIn("--auto-confirm", justfile)
        self.assertIn('"{{auto_confirm}}" = "auto_confirm=true"', justfile)

    def test_service_update_plan_deploys_then_restarts_only_named_service_units(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, _calls_log = self._workflow_fixture(tmp)
            self._write_quadlet_service(root, "seerr", "media01", service_group="media", containers=["web"])

            plan = build_service_update_plan(root, "immich")

            self.assertEqual("service-update:immich", plan.id)
            self.assertEqual(
                ["service-deploy", "confirm-restart", "restart-service-units", "verify-service-units-active"],
                [step.id for step in plan.steps],
            )
            service_deploy, confirmation, restart_units, verify_units = plan.steps
            self.assertIsInstance(service_deploy, CommandPhase)
            self.assertEqual("Service Deploy", service_deploy.display_name)
            self.assertEqual([str(root / "scripts" / "service-deploy"), "immich"], list(service_deploy.command))
            self.assertIsInstance(confirmation, ConfirmationGate)
            self.assertEqual("Type 'update immich' to restart Service immich units: ", confirmation.prompt)
            self.assertEqual("update immich", confirmation.required_input)
            self.assertIsInstance(restart_units, CommandPhase)
            self.assertEqual("Restart Service units", restart_units.display_name)
            self.assertEqual(
                [
                    str(root / "scripts" / "vm-shell"),
                    "media01",
                    "--",
                    "sudo",
                    "systemctl",
                    "restart",
                    "fortress-immich-postgres.service",
                    "fortress-immich-redis.service",
                    "fortress-immich-server.service",
                ],
                list(restart_units.command),
            )
            self.assertIsInstance(verify_units, CommandPhase)
            self.assertEqual("Verify Service units are active", verify_units.display_name)
            self.assertEqual(
                [
                    str(root / "scripts" / "vm-shell"),
                    "media01",
                    "--",
                    "sh",
                    "-lc",
                    IMMICH_ACTIVE_CHECK,
                ],
                list(verify_units.command),
            )
            self.assertNotIn("seerr", " ".join(restart_units.command))
            self.assertNotIn("seerr", " ".join(verify_units.command))

    def test_service_update_plan_restarts_declared_native_service_unit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, _calls_log = self._workflow_fixture(tmp)
            self._write_native_service(root, "internal-ingress", "ingress01", "caddy")
            (root / "inventory" / "vms" / "ingress01.yaml").write_text("vmid: 102\n")

            plan = build_service_update_plan(root, "internal-ingress")

            restart_units = plan.steps[2]
            verify_units = plan.steps[3]
            self.assertEqual(
                [
                    str(root / "scripts" / "vm-shell"),
                    "ingress01",
                    "--",
                    "sudo",
                    "systemctl",
                    "restart",
                    "caddy",
                ],
                list(restart_units.command),
            )
            self.assertEqual(
                [
                    str(root / "scripts" / "vm-shell"),
                    "ingress01",
                    "--",
                    "sh",
                    "-lc",
                    'for unit in caddy; do sudo systemctl is-active --quiet "$unit" || exit $?; done',
                ],
                list(verify_units.command),
            )

    def test_service_update_runs_deploy_then_confirmed_restart_and_active_check(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, calls_log = self._workflow_fixture(tmp)
            self._write_fake_command_scripts(root)
            env = self._workflow_env(root, calls_log)

            result = subprocess.run(
                [str(REPO_ROOT / "scripts" / "service-update"), "immich"],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                input="update immich\n",
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(
                [
                    "service-deploy immich",
                    "vm-shell media01 -- sudo systemctl restart "
                    "fortress-immich-postgres.service fortress-immich-redis.service fortress-immich-server.service",
                    f"vm-shell media01 -- sh -lc {IMMICH_ACTIVE_CHECK}",
                ],
                calls_log.read_text().splitlines(),
            )

    def test_service_update_denies_restart_without_matching_confirmation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, calls_log = self._workflow_fixture(tmp)
            self._write_fake_command_scripts(root)
            env = self._workflow_env(root, calls_log)

            result = subprocess.run(
                [str(REPO_ROOT / "scripts" / "service-update"), "immich"],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                input="yes\n",
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            self.assertEqual(result.returncode, 1)
            self.assertIn("Service Update denied for Service immich", result.stderr)
            self.assertEqual(["service-deploy immich"], calls_log.read_text().splitlines())

    def test_service_update_auto_confirm_skips_interactive_restart_approval(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, calls_log = self._workflow_fixture(tmp)
            self._write_fake_command_scripts(root)
            env = self._workflow_env(root, calls_log)

            result = subprocess.run(
                [str(REPO_ROOT / "scripts" / "service-update"), "immich", "--auto-confirm"],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(
                [
                    "service-deploy immich",
                    "vm-shell media01 -- sudo systemctl restart "
                    "fortress-immich-postgres.service fortress-immich-redis.service fortress-immich-server.service",
                    f"vm-shell media01 -- sh -lc {IMMICH_ACTIVE_CHECK}",
                ],
                calls_log.read_text().splitlines(),
            )
            self.assertNotIn("Type 'update immich'", result.stdout)

    def test_service_update_stops_and_reports_failed_phase(self):
        scenarios = {
            "service-deploy": (
                "Service Deploy failed for Service immich",
                ["service-deploy immich"],
            ),
            "restart-service-units": (
                "Service unit restart failed for Service immich",
                [
                    "service-deploy immich",
                    "vm-shell media01 -- sudo systemctl restart "
                    "fortress-immich-postgres.service fortress-immich-redis.service fortress-immich-server.service",
                ],
            ),
            "verify-service-units-active": (
                "Service unit active check failed for Service immich",
                [
                    "service-deploy immich",
                    "vm-shell media01 -- sudo systemctl restart "
                    "fortress-immich-postgres.service fortress-immich-redis.service fortress-immich-server.service",
                    f"vm-shell media01 -- sh -lc {IMMICH_ACTIVE_CHECK}",
                ],
            ),
        }

        for failed_phase, (message, expected_calls) in scenarios.items():
            with self.subTest(failed_phase=failed_phase), tempfile.TemporaryDirectory() as tmp:
                root, calls_log = self._workflow_fixture(tmp)
                self._write_fake_command_scripts(root)
                env = self._workflow_env(root, calls_log)
                env["FORTRESS_FAIL_PHASE"] = failed_phase

                result = subprocess.run(
                    [str(REPO_ROOT / "scripts" / "service-update"), "immich"],
                    cwd=REPO_ROOT,
                    env=env,
                    text=True,
                    input="update immich\n",
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )

                self.assertEqual(result.returncode, 42)
                self.assertIn(message, result.stderr)
                self.assertEqual(expected_calls, calls_log.read_text().splitlines())

    def test_service_update_validates_service_before_any_workflow_command(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "inventory" / "services").mkdir(parents=True)
            calls_log = root / "calls.log"
            env = self._workflow_env(root, calls_log)

            result = subprocess.run(
                [str(REPO_ROOT / "scripts" / "service-update"), "ghost"],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            self.assertEqual(result.returncode, 1)
            self.assertIn("Service 'ghost' is not declared", result.stderr)
            self.assertFalse(calls_log.exists())

    def test_service_update_validates_backend_before_any_workflow_command(self):
        scenarios = {
            "missing-backend": (
                "name: missing-backend\n"
                "deploy:\n"
                "  type: quadlet\n"
                "  containers:\n"
                "    - name: web\n"
                "      image: example.invalid/web:1\n",
                "Service 'missing-backend' has no backend.vm",
            ),
            "ghost-vm": (
                "name: ghost-vm\n"
                "backend:\n"
                "  vm: ghost\n"
                "  port: 8080\n"
                "deploy:\n"
                "  type: quadlet\n"
                "  containers:\n"
                "    - name: web\n"
                "      image: example.invalid/web:1\n",
                "Backend VM 'ghost' for Service 'ghost-vm' is not declared",
            ),
        }

        for service_name, (service_yaml, message) in scenarios.items():
            with self.subTest(service_name=service_name), tempfile.TemporaryDirectory() as tmp:
                root, calls_log = self._workflow_fixture(tmp)
                (root / "inventory" / "services" / f"{service_name}.yaml").write_text(service_yaml)
                self._write_fake_command_scripts(root)
                env = self._workflow_env(root, calls_log)

                result = subprocess.run(
                    [str(REPO_ROOT / "scripts" / "service-update"), service_name],
                    cwd=REPO_ROOT,
                    env=env,
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )

                self.assertEqual(result.returncode, 1)
                self.assertIn(message, result.stderr)
                self.assertFalse(calls_log.exists())

    def test_service_update_rejects_unknown_flags(self):
        result = subprocess.run(
            [str(REPO_ROOT / "scripts" / "service-update"), "immich", "--yes"],
            cwd=REPO_ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        self.assertEqual(result.returncode, 2)
        self.assertIn("usage: scripts/service-update <service> [--auto-confirm]", result.stderr)

    def _workflow_fixture(self, tmp):
        root = Path(tmp)
        (root / "inventory" / "services").mkdir(parents=True)
        (root / "inventory" / "vms").mkdir(parents=True)
        (root / "scripts").mkdir()
        (root / "inventory" / "vms" / "media01.yaml").write_text("vmid: 101\n")
        self._write_quadlet_service(
            root,
            "immich",
            "media01",
            service_group="media",
            containers=["postgres", "redis", "server"],
        )
        calls_log = root / "calls.log"
        return root, calls_log

    def _write_fake_command_scripts(self, root):
        for name in ["service-deploy", "vm-shell"]:
            script = root / "scripts" / name
            script.write_text(
                "#!/usr/bin/env bash\n"
                "name=$(basename \"$0\")\n"
                "printf '%s %s\\n' \"$name\" \"$*\" >> \"$CALLS_LOG\"\n"
                "phase=\"$name\"\n"
                "if [ \"$name\" = vm-shell ] && [[ \" $* \" == *\" systemctl restart \"* ]]; then phase=\"restart-service-units\"; fi\n"
                "if [ \"$name\" = vm-shell ] && [[ \" $* \" == *\" systemctl is-active \"* ]]; then phase=\"verify-service-units-active\"; fi\n"
                "if [ \"$FORTRESS_FAIL_PHASE\" = \"$phase\" ]; then exit 42; fi\n"
            )
            script.chmod(script.stat().st_mode | stat.S_IXUSR)

    def _write_quadlet_service(self, root, service_name, backend_vm, service_group, containers):
        container_yaml = "".join(
            f"    - name: {container}\n"
            f"      image: example.invalid/{service_name}-{container}:1\n"
            for container in containers
        )
        (root / "inventory" / "services" / f"{service_name}.yaml").write_text(
            f"name: {service_name}\n"
            f"service_group: {service_group}\n"
            "backend:\n"
            f"  vm: {backend_vm}\n"
            "  port: 8080\n"
            "deploy:\n"
            "  type: quadlet\n"
            "  containers:\n"
            f"{container_yaml}"
        )

    def _write_native_service(self, root, service_name, backend_vm, unit):
        (root / "inventory" / "services" / f"{service_name}.yaml").write_text(
            f"name: {service_name}\n"
            "backend:\n"
            f"  vm: {backend_vm}\n"
            "  port: 443\n"
            "deploy:\n"
            "  type: native\n"
            "  package: caddy\n"
            f"  service_name: {unit}\n"
        )

    def _workflow_env(self, root, calls_log):
        env = os.environ.copy()
        env["FORTRESS_ROOT"] = str(root)
        env["CALLS_LOG"] = str(calls_log)
        return env


if __name__ == "__main__":
    unittest.main()
