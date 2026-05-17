import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

from fortress_workflows import CommandPhase, ConfirmationGate
from fortress_workflows.host_update import HostUpdatePlanError, build_host_update_plan


REPO_ROOT = Path(__file__).resolve().parents[1]
HOST_UPDATE_COMMAND = (
    "sudo apt-get update && "
    "sudo env DEBIAN_FRONTEND=noninteractive apt-get --assume-yes --with-new-pkgs --no-remove upgrade"
)
HOST_CONFIGURE_TAGS = "proxmox_repos,system_hygiene,proxmox_network,proxmox_users,gpu_passthrough"


class HostUpdateWorkflowTests(unittest.TestCase):
    def test_host_update_plan_declares_configure_then_routine_software_advancement(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "inventory" / "hosts").mkdir(parents=True)
            (root / "inventory" / "hosts" / "wintermute.yaml").write_text("proxmox:\n  templates: []\n")

            plan = build_host_update_plan(root, "wintermute")

            self.assertEqual("host-update:wintermute", plan.id)
            self.assertEqual(["host-configure", "software-advancement"], [step.id for step in plan.steps])
            host_configure, software_advancement = plan.steps
            self.assertIsInstance(host_configure, CommandPhase)
            self.assertEqual("Host Configure", host_configure.display_name)
            self.assertEqual(
                [str(root / "scripts" / "host-configure"), "wintermute", HOST_CONFIGURE_TAGS],
                list(host_configure.command),
            )
            self.assertIsInstance(software_advancement, CommandPhase)
            self.assertEqual("Host Software Advancement", software_advancement.display_name)
            self.assertEqual(
                [
                    str(root / "scripts" / "host-shell"),
                    "wintermute",
                    "--",
                    "bash",
                    "-lc",
                    HOST_UPDATE_COMMAND,
                ],
                list(software_advancement.command),
            )
            all_command_text = "\n".join(" ".join(step.command) for step in plan.steps)
            self.assertNotIn("templates-build", all_command_text)
            self.assertNotIn("template-verify", all_command_text)
            self.assertNotIn("vm-up", all_command_text)
            self.assertNotIn("service-launch", all_command_text)
            self.assertNotIn("service-deploy", all_command_text)
            self.assertNotIn("full-upgrade", all_command_text)
            self.assertNotIn("dist-upgrade", all_command_text)
            self.assertNotIn("reboot", all_command_text)
            self.assertNotIn("shutdown", all_command_text)

    def test_host_update_reboot_plan_shows_impact_and_orders_shutdown_reboot_restore(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, _calls_log = self._workflow_fixture(tmp)
            self._write_vm(root, "media01", 101, "wintermute")
            self._write_vm(root, "forgejo01", 102, "wintermute")
            self._write_vm(root, "elsewhere01", 201, "straylight")
            self._write_service(root, "jellyfin", "media01")
            self._write_service(root, "forgejo", "forgejo01")

            plan = build_host_update_plan(root, "wintermute", reboot=True)

            self.assertEqual(
                [
                    "host-configure",
                    "software-advancement",
                    "confirm-host-reboot",
                    "shutdown-vm:forgejo01",
                    "shutdown-vm:media01",
                    "reboot-host",
                    "verify-host-reachable",
                    "start-vm:forgejo01",
                    "start-vm:media01",
                ],
                [step.id for step in plan.steps],
            )
            confirmation = plan.steps[2]
            self.assertIsInstance(confirmation, ConfirmationGate)
            self.assertIn("Ordinary VMs impacted on Host wintermute: forgejo01, media01", confirmation.prompt)
            self.assertIn("Resident Services impacted through those VMs: forgejo, jellyfin", confirmation.prompt)
            self.assertEqual("reboot wintermute", confirmation.required_input)

            shutdown_forgejo, shutdown_media = plan.steps[3], plan.steps[4]
            self.assertEqual(
                [str(root / "scripts" / "host-shell"), "wintermute", "--", "sudo", "qm", "shutdown", "102", "--timeout", "300"],
                list(shutdown_forgejo.command),
            )
            self.assertEqual(
                [str(root / "scripts" / "host-shell"), "wintermute", "--", "sudo", "qm", "shutdown", "101", "--timeout", "300"],
                list(shutdown_media.command),
            )
            self.assertEqual(
                [str(root / "scripts" / "host-shell"), "wintermute", "--", "sudo", "systemctl", "reboot"],
                list(plan.steps[5].command),
            )
            self.assertEqual([str(root / "scripts" / "host-shell"), "wintermute", "--", "true"], list(plan.steps[6].command))
            self.assertEqual(
                [str(root / "scripts" / "host-shell"), "wintermute", "--", "sudo", "qm", "start", "102"],
                list(plan.steps[7].command),
            )
            self.assertEqual(
                [str(root / "scripts" / "host-shell"), "wintermute", "--", "sudo", "qm", "start", "101"],
                list(plan.steps[8].command),
            )

    def test_host_update_plan_rejects_undeclared_hosts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "inventory" / "hosts").mkdir(parents=True)

            with self.assertRaisesRegex(HostUpdatePlanError, "Host 'ghost' is not declared"):
                build_host_update_plan(root, "ghost")

    def test_host_update_rejects_undeclared_hosts_before_any_mutation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "inventory" / "hosts").mkdir(parents=True)
            calls_log = root / "calls.log"
            env = os.environ.copy()
            env["FORTRESS_ROOT"] = str(root)
            env["CALLS_LOG"] = str(calls_log)

            result = subprocess.run(
                [str(REPO_ROOT / "scripts" / "host-update"), "ghost"],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            self.assertEqual(result.returncode, 1)
            self.assertIn("Host 'ghost' is not declared", result.stderr)
            self.assertFalse(calls_log.exists())

    def test_just_host_update_calls_workflow_script(self):
        justfile = (REPO_ROOT / "justfile").read_text()

        self.assertIn("host-update host:", justfile)
        self.assertIn("./scripts/host-update {{host}}", justfile)

    def test_host_update_runs_configure_then_host_software_advancement(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, calls_log = self._workflow_fixture(tmp)
            env = self._workflow_env(root, calls_log)

            result = subprocess.run(
                [str(REPO_ROOT / "scripts" / "host-update"), "wintermute"],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(
                [
                    f"host-configure wintermute {HOST_CONFIGURE_TAGS}",
                    f"host-shell wintermute -- bash -lc {HOST_UPDATE_COMMAND}",
                ],
                calls_log.read_text().splitlines(),
            )
            calls = calls_log.read_text()
            self.assertNotIn("templates-build", calls)
            self.assertNotIn("template-verify", calls)
            self.assertNotIn("vm-up", calls)
            self.assertNotIn("service-launch", calls)
            self.assertNotIn("service-deploy", calls)

    def test_host_update_reboot_runs_confirmed_interruption_reboot_and_restoration(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, calls_log = self._workflow_fixture(tmp)
            self._write_vm(root, "media01", 101, "wintermute")
            self._write_vm(root, "forgejo01", 102, "wintermute")
            self._write_service(root, "jellyfin", "media01")
            self._write_service(root, "forgejo", "forgejo01")
            env = self._workflow_env(root, calls_log)

            result = subprocess.run(
                [str(REPO_ROOT / "scripts" / "host-update"), "wintermute", "--reboot"],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                input="reboot wintermute\n",
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Ordinary VMs impacted on Host wintermute: forgejo01, media01", result.stdout)
            self.assertIn("Resident Services impacted through those VMs: forgejo, jellyfin", result.stdout)
            self.assertEqual(
                [
                    f"host-configure wintermute {HOST_CONFIGURE_TAGS}",
                    f"host-shell wintermute -- bash -lc {HOST_UPDATE_COMMAND}",
                    "host-shell wintermute -- sudo qm shutdown 102 --timeout 300",
                    "host-shell wintermute -- sudo qm shutdown 101 --timeout 300",
                    "host-shell wintermute -- sudo systemctl reboot",
                    "host-shell wintermute -- true",
                    "host-shell wintermute -- sudo qm start 102",
                    "host-shell wintermute -- sudo qm start 101",
                ],
                calls_log.read_text().splitlines(),
            )

    def test_host_update_reboot_denies_without_explicit_maintenance_window_confirmation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, calls_log = self._workflow_fixture(tmp)
            self._write_vm(root, "media01", 101, "wintermute")
            self._write_service(root, "jellyfin", "media01")
            env = self._workflow_env(root, calls_log)

            result = subprocess.run(
                [str(REPO_ROOT / "scripts" / "host-update"), "wintermute", "--reboot"],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                input="yes\n",
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            self.assertEqual(result.returncode, 1)
            self.assertIn("Host Update reboot denied for Host wintermute", result.stderr)
            self.assertEqual(
                [
                    f"host-configure wintermute {HOST_CONFIGURE_TAGS}",
                    f"host-shell wintermute -- bash -lc {HOST_UPDATE_COMMAND}",
                ],
                calls_log.read_text().splitlines(),
            )

    def test_host_update_reboot_stops_and_reports_reboot_path_failures(self):
        scenarios = {
            "shutdown-vm:media01": (
                "Graceful shutdown failed for VM media01 on Host wintermute",
                [
                    f"host-configure wintermute {HOST_CONFIGURE_TAGS}",
                    f"host-shell wintermute -- bash -lc {HOST_UPDATE_COMMAND}",
                    "host-shell wintermute -- sudo qm shutdown 102 --timeout 300",
                    "host-shell wintermute -- sudo qm shutdown 101 --timeout 300",
                ],
            ),
            "verify-host-reachable": (
                "Host reachability verification failed for Host wintermute",
                [
                    f"host-configure wintermute {HOST_CONFIGURE_TAGS}",
                    f"host-shell wintermute -- bash -lc {HOST_UPDATE_COMMAND}",
                    "host-shell wintermute -- sudo qm shutdown 102 --timeout 300",
                    "host-shell wintermute -- sudo qm shutdown 101 --timeout 300",
                    "host-shell wintermute -- sudo systemctl reboot",
                    "host-shell wintermute -- true",
                ],
            ),
            "start-vm:media01": (
                "VM restoration failed for VM media01 on Host wintermute",
                [
                    f"host-configure wintermute {HOST_CONFIGURE_TAGS}",
                    f"host-shell wintermute -- bash -lc {HOST_UPDATE_COMMAND}",
                    "host-shell wintermute -- sudo qm shutdown 102 --timeout 300",
                    "host-shell wintermute -- sudo qm shutdown 101 --timeout 300",
                    "host-shell wintermute -- sudo systemctl reboot",
                    "host-shell wintermute -- true",
                    "host-shell wintermute -- sudo qm start 102",
                    "host-shell wintermute -- sudo qm start 101",
                ],
            ),
        }

        for failed_phase, (message, expected_calls) in scenarios.items():
            with self.subTest(failed_phase=failed_phase), tempfile.TemporaryDirectory() as tmp:
                root, calls_log = self._workflow_fixture(tmp)
                self._write_vm(root, "media01", 101, "wintermute")
                self._write_vm(root, "forgejo01", 102, "wintermute")
                self._write_service(root, "jellyfin", "media01")
                self._write_service(root, "forgejo", "forgejo01")
                env = self._workflow_env(root, calls_log)
                env["FORTRESS_FAIL_PHASE"] = failed_phase

                result = subprocess.run(
                    [str(REPO_ROOT / "scripts" / "host-update"), "wintermute", "--reboot"],
                    cwd=REPO_ROOT,
                    env=env,
                    text=True,
                    input="reboot wintermute\n",
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )

                self.assertEqual(result.returncode, 42)
                self.assertIn(message, result.stderr)
                self.assertEqual(expected_calls, calls_log.read_text().splitlines())

    def test_host_update_stops_and_reports_the_failed_phase(self):
        scenarios = {
            "host-configure": (
                "Host Configure failed for Host wintermute",
                [f"host-configure wintermute {HOST_CONFIGURE_TAGS}"],
            ),
            "host-shell": (
                "Host Software Advancement failed for Host wintermute",
                [
                    f"host-configure wintermute {HOST_CONFIGURE_TAGS}",
                    f"host-shell wintermute -- bash -lc {HOST_UPDATE_COMMAND}",
                ],
            ),
        }

        for failed_phase, (message, expected_calls) in scenarios.items():
            with self.subTest(failed_phase=failed_phase), tempfile.TemporaryDirectory() as tmp:
                root, calls_log = self._workflow_fixture(tmp)
                env = self._workflow_env(root, calls_log)
                env["FORTRESS_FAIL_PHASE"] = failed_phase

                result = subprocess.run(
                    [str(REPO_ROOT / "scripts" / "host-update"), "wintermute"],
                    cwd=REPO_ROOT,
                    env=env,
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )

                self.assertEqual(result.returncode, 42)
                self.assertIn(message, result.stderr)
                self.assertEqual(expected_calls, calls_log.read_text().splitlines())

    def _workflow_fixture(self, tmp):
        root = Path(tmp)
        host_dir = root / "inventory" / "hosts"
        scripts_dir = root / "scripts"
        host_dir.mkdir(parents=True)
        (root / "inventory" / "vms").mkdir()
        (root / "inventory" / "services").mkdir()
        scripts_dir.mkdir()
        (host_dir / "wintermute.yaml").write_text("proxmox:\n  templates: [debian-13-base]\n")
        calls_log = root / "calls.log"
        for name in ["host-configure", "host-shell"]:
            script = scripts_dir / name
            script.write_text(
                "#!/usr/bin/env bash\n"
                "name=$(basename \"$0\")\n"
                "printf '%s %s\\n' \"$name\" \"$*\" >> \"$CALLS_LOG\"\n"
                "phase=\"$name\"\n"
                "if [ \"$name\" = host-shell ] && [[ \" $* \" == *\" qm shutdown 101 \"* ]]; then phase=\"shutdown-vm:media01\"; fi\n"
                "if [ \"$name\" = host-shell ] && [[ \" $* \" == *\" qm shutdown 102 \"* ]]; then phase=\"shutdown-vm:forgejo01\"; fi\n"
                "if [ \"$name\" = host-shell ] && [[ \" $* \" == *\" systemctl reboot \"* ]]; then phase=\"reboot-host\"; fi\n"
                "if [ \"$name\" = host-shell ] && [[ \" $* \" == *\" -- true \"* ]]; then phase=\"verify-host-reachable\"; fi\n"
                "if [ \"$name\" = host-shell ] && [[ \" $* \" == *\" qm start 101\"* ]]; then phase=\"start-vm:media01\"; fi\n"
                "if [ \"$name\" = host-shell ] && [[ \" $* \" == *\" qm start 102\"* ]]; then phase=\"start-vm:forgejo01\"; fi\n"
                "if [ \"$FORTRESS_FAIL_PHASE\" = \"$name\" ] || [ \"$FORTRESS_FAIL_PHASE\" = \"$phase\" ]; then exit 42; fi\n"
            )
            script.chmod(script.stat().st_mode | stat.S_IXUSR)
        return root, calls_log

    def _write_vm(self, root, name, vmid, host):
        (root / "inventory" / "vms" / f"{name}.yaml").write_text(
            f"vmid: {vmid}\n"
            "placement:\n"
            f"  host: {host}\n"
        )

    def _write_service(self, root, service, backend_vm):
        (root / "inventory" / "services" / f"{service}.yaml").write_text(
            f"name: {service}\n"
            "backend:\n"
            f"  vm: {backend_vm}\n"
            "  port: 8080\n"
            "deploy:\n"
            "  type: quadlet\n"
            "  containers:\n"
            "    - name: web\n"
            f"      image: example.invalid/{service}:1\n"
        )

    def _workflow_env(self, root, calls_log):
        env = os.environ.copy()
        env["FORTRESS_ROOT"] = str(root)
        env["CALLS_LOG"] = str(calls_log)
        return env


if __name__ == "__main__":
    unittest.main()
