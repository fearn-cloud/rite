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
    "apt-get update && "
    "env DEBIAN_FRONTEND=noninteractive apt-get --assume-yes --with-new-pkgs --no-remove upgrade"
)
HOST_REBOOT_COMMAND = (
    "mkdir -p /var/lib/fortress && "
    "cat /proc/sys/kernel/random/boot_id > /var/lib/fortress/host-update-pre-reboot-boot-id && "
    "systemctl reboot"
)
HOST_CONFIGURE_TAGS = "proxmox_repos,system_hygiene,proxmox_network,proxmox_users,gpu_passthrough"
HOST_REBOOT_REQUIRED_COMMAND = (
    "if test -f /var/run/reboot-required; then exit 0; fi; "
    'running="$(uname -r)"; '
    "latest=\"$(find /boot -maxdepth 1 -type f -name 'vmlinuz-*' -printf '%f\\n' 2>/dev/null "
    "| sed 's/^vmlinuz-//' | sort -V | tail -n 1)\"; "
    'if test -n "$latest" && test "$latest" != "$running"; then exit 0; fi; '
    "if command -v needrestart >/dev/null 2>&1; then "
    'needrestart_output="$(needrestart -b -r l 2>/dev/null)"; '
    "if printf '%s\\n' \"$needrestart_output\" | "
    "awk -F': *' 'BEGIN { missing = 1 } /^NEEDRESTART-KSTA:/ { missing = 0; exit (($2 + 0) >= 2 ? 0 : 1) } END { if (missing) exit 1 }'; "
    "then exit 0; fi; "
    "if printf '%s\\n' \"$needrestart_output\" | grep -Eq '^NEEDRESTART-(SVC|BIN|UCODE):'; then exit 0; fi; "
    "fi; "
    "if command -v checkrestart >/dev/null 2>&1; then "
    "checkrestart -t >/dev/null 2>&1; "
    'checkrestart_status="$?"; '
    'if test "$checkrestart_status" -eq 1; then exit 0; fi; '
    'if test "$checkrestart_status" -ne 0; then exit 2; fi; '
    "fi; "
    "exit 1"
)
HOST_REBOOT_REQUIRED_CALL = f"host-shell wintermute -- bash -lc {HOST_REBOOT_REQUIRED_COMMAND}"
START_VM_101_COMMAND = "qm status 101 | grep -qx 'status: running' || qm start 101"
START_VM_102_COMMAND = "qm status 102 | grep -qx 'status: running' || qm start 102"


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
                [str(root / "scripts" / "host-shell"), "wintermute", "--", "qm", "shutdown", "102", "--timeout", "300"],
                list(shutdown_forgejo.command),
            )
            self.assertEqual(
                [str(root / "scripts" / "host-shell"), "wintermute", "--", "qm", "shutdown", "101", "--timeout", "300"],
                list(shutdown_media.command),
            )
            self.assertEqual(
                [str(root / "scripts" / "host-shell"), "wintermute", "--", "bash", "-lc", HOST_REBOOT_COMMAND],
                list(plan.steps[5].command),
            )
            self.assertEqual([str(root / "scripts" / "host-wait-reboot"), "wintermute"], list(plan.steps[6].command))
            self.assertEqual(
                [str(root / "scripts" / "host-shell"), "wintermute", "--", "bash", "-lc", START_VM_102_COMMAND],
                list(plan.steps[7].command),
            )
            self.assertEqual(
                [str(root / "scripts" / "host-shell"), "wintermute", "--", "bash", "-lc", START_VM_101_COMMAND],
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

        self.assertIn('host-update host reboot="false":', justfile)
        self.assertIn("./scripts/host-update {{host}}", justfile)
        self.assertIn("./scripts/host-update {{host}} --reboot", justfile)
        self.assertIn('"{{reboot}}" = "--reboot"', justfile)

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

    def test_host_update_reboot_treats_reboot_flag_as_explicit_confirmation(self):
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
                input="no interactive confirmation should be read\n",
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Ordinary VMs impacted on Host wintermute: forgejo01, media01", result.stdout)
            self.assertIn("Resident Services impacted through those VMs: forgejo, jellyfin", result.stdout)
            self.assertNotIn("Type 'reboot wintermute'", result.stdout)
            self.assertEqual(
                [
                    f"host-configure wintermute {HOST_CONFIGURE_TAGS}",
                    f"host-shell wintermute -- bash -lc {HOST_UPDATE_COMMAND}",
                    HOST_REBOOT_REQUIRED_CALL,
                    "host-shell wintermute -- qm shutdown 102 --timeout 300",
                    "host-shell wintermute -- qm shutdown 101 --timeout 300",
                    f"host-shell wintermute -- bash -lc {HOST_REBOOT_COMMAND}",
                    "host-wait-reboot wintermute",
                    f"host-shell wintermute -- bash -lc {START_VM_102_COMMAND}",
                    f"host-shell wintermute -- bash -lc {START_VM_101_COMMAND}",
                ],
                calls_log.read_text().splitlines(),
            )

    def test_host_update_reboot_restore_tolerates_vm_already_running(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, calls_log = self._workflow_fixture(tmp)
            self._write_vm(root, "media01", 101, "wintermute")
            self._write_vm(root, "forgejo01", 102, "wintermute")
            env = self._workflow_env(root, calls_log)
            env["FORTRESS_ALREADY_RUNNING_VMIDS"] = "101"

            result = subprocess.run(
                [str(REPO_ROOT / "scripts" / "host-update"), "wintermute", "--reboot"],
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
                    HOST_REBOOT_REQUIRED_CALL,
                    "host-shell wintermute -- qm shutdown 102 --timeout 300",
                    "host-shell wintermute -- qm shutdown 101 --timeout 300",
                    f"host-shell wintermute -- bash -lc {HOST_REBOOT_COMMAND}",
                    "host-wait-reboot wintermute",
                    f"host-shell wintermute -- bash -lc {START_VM_102_COMMAND}",
                    f"host-shell wintermute -- bash -lc {START_VM_101_COMMAND}",
                ],
                calls_log.read_text().splitlines(),
            )
            self.assertIn("VM 101 already running", result.stdout)

    def test_host_update_reboot_flag_skips_reboot_when_host_does_not_require_one(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, calls_log = self._workflow_fixture(tmp)
            self._write_vm(root, "media01", 101, "wintermute")
            self._write_service(root, "jellyfin", "media01")
            env = self._workflow_env(root, calls_log)
            env["FORTRESS_REBOOT_REQUIRED"] = "false"

            result = subprocess.run(
                [str(REPO_ROOT / "scripts" / "host-update"), "wintermute", "--reboot"],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                input="no interactive confirmation should be read\n",
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Host wintermute does not require reboot after update", result.stdout)
            self.assertNotIn("Ordinary VMs impacted on Host wintermute", result.stdout)
            self.assertNotIn("Type 'reboot wintermute'", result.stdout)
            self.assertEqual(
                [
                    f"host-configure wintermute {HOST_CONFIGURE_TAGS}",
                    f"host-shell wintermute -- bash -lc {HOST_UPDATE_COMMAND}",
                    HOST_REBOOT_REQUIRED_CALL,
                ],
                calls_log.read_text().splitlines(),
            )

    def test_host_update_reboot_flag_reboots_when_installed_kernel_differs_from_running_kernel(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, calls_log = self._workflow_fixture(tmp)
            self._write_vm(root, "media01", 101, "wintermute")
            self._write_service(root, "jellyfin", "media01")
            env = self._workflow_env(root, calls_log)
            env["FORTRESS_REBOOT_REQUIRED"] = "false"
            env["FORTRESS_INSTALLED_KERNEL_DIFFERS"] = "true"

            result = subprocess.run(
                [str(REPO_ROOT / "scripts" / "host-update"), "wintermute", "--reboot"],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                input="no interactive confirmation should be read\n",
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Ordinary VMs impacted on Host wintermute: media01", result.stdout)
            self.assertNotIn("does not require reboot", result.stdout)
            self.assertEqual(
                [
                    f"host-configure wintermute {HOST_CONFIGURE_TAGS}",
                    f"host-shell wintermute -- bash -lc {HOST_UPDATE_COMMAND}",
                    HOST_REBOOT_REQUIRED_CALL,
                    "host-shell wintermute -- qm shutdown 101 --timeout 300",
                    f"host-shell wintermute -- bash -lc {HOST_REBOOT_COMMAND}",
                    "host-wait-reboot wintermute",
                    f"host-shell wintermute -- bash -lc {START_VM_101_COMMAND}",
                ],
                calls_log.read_text().splitlines(),
            )

    def test_reboot_required_probe_accepts_needrestart_and_checkrestart_findings(self):
        scenarios = {
            "no_probe_finding": ({}, 1),
            "needrestart_kernel_upgrade": (
                {"needrestart": "printf 'NEEDRESTART-KSTA: 3\\n'\n"},
                0,
            ),
            "needrestart_service_restart": (
                {"needrestart": "printf 'NEEDRESTART-KSTA: 1\\nNEEDRESTART-SVC: pvedaemon.service\\n'\n"},
                0,
            ),
            "checkrestart_stale_process": (
                {"checkrestart": "exit 1\n"},
                0,
            ),
            "checkrestart_probe_error": (
                {"checkrestart": "exit 3\n"},
                2,
            ),
        }

        for name, (extra_scripts, expected_returncode) in scenarios.items():
            with self.subTest(name=name), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                bin_dir = root / "bin"
                bin_dir.mkdir()
                self._path_script(bin_dir, "uname", "printf '6.8.12-1-pve\\n'\n")
                self._path_script(bin_dir, "find", "printf 'vmlinuz-6.8.12-1-pve\\n'\n")
                for script_name, body in extra_scripts.items():
                    self._path_script(bin_dir, script_name, body)
                env = os.environ.copy()
                env["PATH"] = f"{bin_dir}:{env['PATH']}"

                result = subprocess.run(
                    ["bash", "-lc", HOST_REBOOT_REQUIRED_COMMAND],
                    cwd=REPO_ROOT,
                    env=env,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )

                self.assertEqual(expected_returncode, result.returncode, result.stderr)

    def test_host_update_reboot_flag_reports_reboot_required_check_failures(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, calls_log = self._workflow_fixture(tmp)
            env = self._workflow_env(root, calls_log)
            env["FORTRESS_FAIL_PHASE"] = "host-reboot-required"

            result = subprocess.run(
                [str(REPO_ROOT / "scripts" / "host-update"), "wintermute", "--reboot"],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            self.assertEqual(result.returncode, 1)
            self.assertIn("Host reboot-required check failed for Host wintermute", result.stderr)
            self.assertEqual(
                [
                    f"host-configure wintermute {HOST_CONFIGURE_TAGS}",
                    f"host-shell wintermute -- bash -lc {HOST_UPDATE_COMMAND}",
                    HOST_REBOOT_REQUIRED_CALL,
                ],
                calls_log.read_text().splitlines(),
            )

    def test_host_wait_reboot_accepts_changed_boot_id_without_observed_outage(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            scripts_dir = root / "scripts"
            scripts_dir.mkdir()
            calls_log = root / "calls.log"
            host_shell = scripts_dir / "host-shell"
            host_shell.write_text(
                "#!/usr/bin/env bash\n"
                "printf '%s\\n' \"$*\" >> \"$CALLS_LOG\"\n"
                "if [[ \"$*\" == \"wintermute -- cat /var/lib/fortress/host-update-pre-reboot-boot-id\" ]]; then echo boot-before; exit 0; fi\n"
                "if [[ \"$*\" == \"wintermute -- cat /proc/sys/kernel/random/boot_id\" ]]; then echo boot-after; exit 0; fi\n"
                "if [[ \"$*\" == \"wintermute -- rm -f /var/lib/fortress/host-update-pre-reboot-boot-id\" ]]; then exit 0; fi\n"
                "exit 1\n"
            )
            host_shell.chmod(host_shell.stat().st_mode | stat.S_IXUSR)
            env = self._workflow_env(root, calls_log)

            result = subprocess.run(
                [
                    str(REPO_ROOT / "scripts" / "host-wait-reboot"),
                    "wintermute",
                    "--down-timeout",
                    "1",
                    "--interval",
                    "1",
                ],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Waiting for Host wintermute to go down after reboot", result.stdout)
            self.assertIn("Host wintermute is reachable after reboot", result.stdout)
            self.assertEqual(
                [
                    "wintermute -- cat /var/lib/fortress/host-update-pre-reboot-boot-id",
                    "wintermute -- cat /proc/sys/kernel/random/boot_id",
                    "wintermute -- rm -f /var/lib/fortress/host-update-pre-reboot-boot-id",
                ],
                calls_log.read_text().splitlines(),
            )

    def test_host_wait_reboot_reports_unchanged_boot_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            scripts_dir = root / "scripts"
            scripts_dir.mkdir()
            calls_log = root / "calls.log"
            host_shell = scripts_dir / "host-shell"
            host_shell.write_text(
                "#!/usr/bin/env bash\n"
                "printf '%s\\n' \"$*\" >> \"$CALLS_LOG\"\n"
                "if [[ \"$*\" == \"wintermute -- cat /var/lib/fortress/host-update-pre-reboot-boot-id\" ]]; then echo boot-before; exit 0; fi\n"
                "if [[ \"$*\" == \"wintermute -- cat /proc/sys/kernel/random/boot_id\" ]]; then echo boot-before; exit 0; fi\n"
                "exit 1\n"
            )
            host_shell.chmod(host_shell.stat().st_mode | stat.S_IXUSR)
            env = self._workflow_env(root, calls_log)

            result = subprocess.run(
                [
                    str(REPO_ROOT / "scripts" / "host-wait-reboot"),
                    "wintermute",
                    "--down-timeout",
                    "1",
                    "--interval",
                    "1",
                ],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            self.assertEqual(result.returncode, 1)
            self.assertIn("Host wintermute boot ID did not change within 1s after reboot", result.stderr)

    def test_host_update_reboot_stops_before_restoration_when_reboot_wait_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, calls_log = self._workflow_fixture(tmp)
            self._write_vm(root, "media01", 101, "wintermute")
            self._write_service(root, "jellyfin", "media01")
            env = self._workflow_env(root, calls_log)
            env["FORTRESS_FAIL_PHASE"] = "verify-host-reachable"

            result = subprocess.run(
                [str(REPO_ROOT / "scripts" / "host-update"), "wintermute", "--reboot"],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            self.assertEqual(result.returncode, 42)
            self.assertIn("Host reachability verification failed for Host wintermute", result.stderr)
            self.assertEqual(
                [
                    f"host-configure wintermute {HOST_CONFIGURE_TAGS}",
                    f"host-shell wintermute -- bash -lc {HOST_UPDATE_COMMAND}",
                    HOST_REBOOT_REQUIRED_CALL,
                    "host-shell wintermute -- qm shutdown 101 --timeout 300",
                    f"host-shell wintermute -- bash -lc {HOST_REBOOT_COMMAND}",
                    "host-wait-reboot wintermute",
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
                    HOST_REBOOT_REQUIRED_CALL,
                    "host-shell wintermute -- qm shutdown 102 --timeout 300",
                    "host-shell wintermute -- qm shutdown 101 --timeout 300",
                ],
            ),
            "verify-host-reachable": (
                "Host reachability verification failed for Host wintermute",
                [
                    f"host-configure wintermute {HOST_CONFIGURE_TAGS}",
                    f"host-shell wintermute -- bash -lc {HOST_UPDATE_COMMAND}",
                    HOST_REBOOT_REQUIRED_CALL,
                    "host-shell wintermute -- qm shutdown 102 --timeout 300",
                    "host-shell wintermute -- qm shutdown 101 --timeout 300",
                    f"host-shell wintermute -- bash -lc {HOST_REBOOT_COMMAND}",
                    "host-wait-reboot wintermute",
                ],
            ),
            "start-vm:media01": (
                "VM restoration failed for VM media01 on Host wintermute",
                [
                    f"host-configure wintermute {HOST_CONFIGURE_TAGS}",
                    f"host-shell wintermute -- bash -lc {HOST_UPDATE_COMMAND}",
                    HOST_REBOOT_REQUIRED_CALL,
                    "host-shell wintermute -- qm shutdown 102 --timeout 300",
                    "host-shell wintermute -- qm shutdown 101 --timeout 300",
                    f"host-shell wintermute -- bash -lc {HOST_REBOOT_COMMAND}",
                    "host-wait-reboot wintermute",
                    f"host-shell wintermute -- bash -lc {START_VM_102_COMMAND}",
                    f"host-shell wintermute -- bash -lc {START_VM_101_COMMAND}",
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
        for name in ["host-configure", "host-shell", "host-wait-reboot"]:
            script = scripts_dir / name
            script.write_text(
                "#!/usr/bin/env bash\n"
                "name=$(basename \"$0\")\n"
                "printf '%s %s\\n' \"$name\" \"$*\" >> \"$CALLS_LOG\"\n"
                "phase=\"$name\"\n"
                "if [ \"$name\" = host-shell ] && [[ \" $* \" == *\" qm shutdown 101 \"* ]]; then phase=\"shutdown-vm:media01\"; fi\n"
                "if [ \"$name\" = host-shell ] && [[ \" $* \" == *\" qm shutdown 102 \"* ]]; then phase=\"shutdown-vm:forgejo01\"; fi\n"
                "if [ \"$name\" = host-shell ] && [[ \" $* \" == *\" systemctl reboot \"* ]]; then phase=\"reboot-host\"; fi\n"
                "if [ \"$name\" = host-shell ] && [[ \" $* \" == *\"/var/run/reboot-required\"* ]]; then phase=\"host-reboot-required\"; fi\n"
                "if [ \"$name\" = host-wait-reboot ]; then phase=\"verify-host-reachable\"; fi\n"
                "if [ \"$name\" = host-shell ] && [[ \" $* \" == *\" qm status 101 \"* ]]; then phase=\"start-vm:media01\"; fi\n"
                "if [ \"$name\" = host-shell ] && [[ \" $* \" == *\" qm status 102 \"* ]]; then phase=\"start-vm:forgejo01\"; fi\n"
                "if [ \"$phase\" = start-vm:media01 ] && [[ \" $FORTRESS_ALREADY_RUNNING_VMIDS \" == *\" 101 \"* ]]; then echo 'VM 101 already running'; exit 0; fi\n"
                "if [ \"$phase\" = start-vm:forgejo01 ] && [[ \" $FORTRESS_ALREADY_RUNNING_VMIDS \" == *\" 102 \"* ]]; then echo 'VM 102 already running'; exit 0; fi\n"
                "if [ \"$FORTRESS_FAIL_PHASE\" = \"$name\" ] || [ \"$FORTRESS_FAIL_PHASE\" = \"$phase\" ]; then exit 42; fi\n"
                "if [ \"$phase\" = host-reboot-required ] && [ \"$FORTRESS_INSTALLED_KERNEL_DIFFERS\" = true ]; then exit 0; fi\n"
                "if [ \"$phase\" = host-reboot-required ] && [ \"$FORTRESS_REBOOT_REQUIRED\" = false ]; then exit 1; fi\n"
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

    def _path_script(self, bin_dir, name, body):
        script = bin_dir / name
        script.write_text(
            "#!/usr/bin/env bash\n"
            f"{body}"
        )
        script.chmod(script.stat().st_mode | stat.S_IXUSR)
        return script


if __name__ == "__main__":
    unittest.main()
