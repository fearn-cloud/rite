import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

from fortress_workflows import CommandPhase, ConfirmationGate
from fortress_workflows.vm_update import VM_REBOOT_COMMAND, build_vm_update_plan


REPO_ROOT = Path(__file__).resolve().parents[1]


class VMUpdateWorkflowTests(unittest.TestCase):
    def test_vm_update_plan_declares_configure_then_routine_software_advancement(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, _calls_log = self._workflow_fixture(tmp)

            plan = build_vm_update_plan(root, "media01")

            self.assertEqual("vm-update:media01", plan.id)
            self.assertEqual(["configure", "software-advancement"], [step.id for step in plan.steps])
            configure, software_advancement = plan.steps
            self.assertIsInstance(configure, CommandPhase)
            self.assertEqual("VM Configure", configure.display_name)
            self.assertEqual([str(root / "scripts" / "vm-configure"), "media01"], list(configure.command))
            self.assertIsInstance(software_advancement, CommandPhase)
            self.assertEqual("Routine Software Advancement", software_advancement.display_name)
            self.assertEqual(
                [str(root / "scripts" / "vm-routine-software-advance"), "media01"],
                list(software_advancement.command),
            )

    def test_vm_update_reboot_plan_shows_resident_services_and_orders_interruption_reboot_restore(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, _calls_log = self._workflow_fixture(tmp)
            self._write_quadlet_service(root, "jellyfin", "media01", service_group="media", containers=["web"])
            self._write_native_service(root, "node-exporter", "media01", "prometheus-node-exporter")
            self._write_quadlet_service(root, "forgejo", "forgejo01", service_group="forge", containers=["web"])
            (root / "inventory" / "vms" / "forgejo01.yaml").write_text("vmid: 102\n")

            plan = build_vm_update_plan(root, "media01", reboot=True)

            self.assertEqual(
                [
                    "configure",
                    "software-advancement",
                    "confirm-vm-reboot",
                    "stop-service:jellyfin",
                    "verify-service-stopped:jellyfin",
                    "stop-service:node-exporter",
                    "verify-service-stopped:node-exporter",
                    "reboot-vm",
                    "verify-vm-reachable",
                    "restore-service:jellyfin",
                    "verify-service-active:jellyfin",
                    "restore-service:node-exporter",
                    "verify-service-active:node-exporter",
                ],
                [step.id for step in plan.steps],
            )
            confirmation = plan.steps[2]
            self.assertIsInstance(confirmation, ConfirmationGate)
            self.assertIn("Resident fortress-managed Services on VM media01: jellyfin, node-exporter", confirmation.prompt)
            self.assertEqual("reboot media01", confirmation.required_input)
            self.assertNotIn("forgejo", confirmation.prompt)

            stop_jellyfin, verify_jellyfin = plan.steps[3], plan.steps[4]
            self.assertEqual(
                [
                    str(root / "scripts" / "vm-shell"),
                    "media01",
                    "--",
                    "sudo",
                    "systemctl",
                    "stop",
                    "fortress-jellyfin-web.service",
                ],
                list(stop_jellyfin.command),
            )
            self.assertEqual(
                [
                    str(root / "scripts" / "vm-shell"),
                    "media01",
                    "--",
                    "sh",
                    "-lc",
                    'for unit in fortress-jellyfin-web.service; do sudo systemctl is-active --quiet "$unit" && exit 1 || true; done',
                ],
                list(verify_jellyfin.command),
            )
            self.assertEqual(
                [str(root / "scripts" / "vm-shell"), "media01", "--", "bash", "-lc", VM_REBOOT_COMMAND],
                list(plan.steps[7].command),
            )
            self.assertEqual([str(root / "scripts" / "vm-wait-reboot"), "media01"], list(plan.steps[8].command))
            self.assertEqual(
                [
                    str(root / "scripts" / "vm-shell"),
                    "media01",
                    "--",
                    "sudo",
                    "systemctl",
                    "start",
                    "fortress-jellyfin-web.service",
                ],
                list(plan.steps[9].command),
            )
            self.assertEqual(
                [
                    str(root / "scripts" / "vm-shell"),
                    "media01",
                    "--",
                    "sudo",
                    "systemctl",
                    "start",
                    "prometheus-node-exporter",
                ],
                list(plan.steps[11].command),
            )

    def test_vm_update_rejects_undeclared_vms_before_any_mutation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "inventory" / "vms").mkdir(parents=True)
            calls_log = root / "calls.log"
            env = os.environ.copy()
            env["FORTRESS_ROOT"] = str(root)
            env["CALLS_LOG"] = str(calls_log)

            result = subprocess.run(
                [str(REPO_ROOT / "scripts" / "vm-update"), "ghost"],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            self.assertEqual(result.returncode, 1)
            self.assertIn("VM 'ghost' is not declared", result.stderr)
            self.assertFalse(calls_log.exists())

    def test_vm_update_runs_configure_before_routine_software_advancement(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, calls_log = self._workflow_fixture(tmp)
            env = self._workflow_env(root, calls_log)

            result = subprocess.run(
                [str(REPO_ROOT / "scripts" / "vm-update"), "media01"],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(
                [
                    "vm-configure media01",
                    "vm-routine-software-advance media01",
                ],
                calls_log.read_text().splitlines(),
            )

    def test_vm_update_reboot_denies_without_matching_maintenance_window_confirmation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, calls_log = self._workflow_fixture(tmp)
            self._write_quadlet_service(root, "jellyfin", "media01", service_group="media", containers=["web"])
            env = self._workflow_env(root, calls_log)

            result = subprocess.run(
                [str(REPO_ROOT / "scripts" / "vm-update"), "media01", "--reboot"],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                input="yes\n",
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            self.assertEqual(result.returncode, 1)
            self.assertIn("Resident fortress-managed Services on VM media01: jellyfin", result.stdout)
            self.assertIn("VM Update reboot denied for VM media01", result.stderr)
            self.assertEqual(
                [
                    "vm-configure media01",
                    "vm-routine-software-advance media01",
                ],
                calls_log.read_text().splitlines(),
            )

    def test_vm_update_reboot_stops_reboots_verifies_reachability_and_restores_resident_services(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, calls_log = self._workflow_fixture(tmp)
            self._write_quadlet_service(root, "jellyfin", "media01", service_group="media", containers=["web"])
            self._write_quadlet_service(root, "forgejo", "forgejo01", service_group="forge", containers=["web"])
            (root / "inventory" / "vms" / "forgejo01.yaml").write_text("vmid: 102\n")
            env = self._workflow_env(root, calls_log)

            result = subprocess.run(
                [str(REPO_ROOT / "scripts" / "vm-update"), "media01", "--reboot", "--auto-confirm"],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(
                [
                    "vm-configure media01",
                    "vm-routine-software-advance media01",
                    "vm-shell media01 -- sudo systemctl stop fortress-jellyfin-web.service",
                    "vm-shell media01 -- sh -lc "
                    'for unit in fortress-jellyfin-web.service; do sudo systemctl is-active --quiet "$unit" && exit 1 || true; done',
                    f"vm-shell media01 -- bash -lc {VM_REBOOT_COMMAND}",
                    "vm-wait-reboot media01",
                    "vm-shell media01 -- sudo systemctl start fortress-jellyfin-web.service",
                    "vm-shell media01 -- sh -lc "
                    'for unit in fortress-jellyfin-web.service; do sudo systemctl is-active --quiet "$unit" || exit $?; done',
                ],
                calls_log.read_text().splitlines(),
            )
            self.assertNotIn("forgejo", calls_log.read_text())

    def test_vm_update_reboot_stops_and_reports_service_stop_or_reachability_failures(self):
        scenarios = {
            "verify-service-stopped": (
                "Service stopped-state check failed for Service jellyfin before VM reboot",
                [
                    "vm-configure media01",
                    "vm-routine-software-advance media01",
                    "vm-shell media01 -- sudo systemctl stop fortress-jellyfin-web.service",
                    "vm-shell media01 -- sh -lc "
                    'for unit in fortress-jellyfin-web.service; do sudo systemctl is-active --quiet "$unit" && exit 1 || true; done',
                ],
            ),
            "verify-vm-reachable": (
                "VM reachability check failed for VM media01 after reboot",
                [
                    "vm-configure media01",
                    "vm-routine-software-advance media01",
                    "vm-shell media01 -- sudo systemctl stop fortress-jellyfin-web.service",
                    "vm-shell media01 -- sh -lc "
                    'for unit in fortress-jellyfin-web.service; do sudo systemctl is-active --quiet "$unit" && exit 1 || true; done',
                    f"vm-shell media01 -- bash -lc {VM_REBOOT_COMMAND}",
                    "vm-wait-reboot media01",
                ],
            ),
        }

        for failed_phase, (message, expected_calls) in scenarios.items():
            with self.subTest(failed_phase=failed_phase), tempfile.TemporaryDirectory() as tmp:
                root, calls_log = self._workflow_fixture(tmp)
                self._write_quadlet_service(root, "jellyfin", "media01", service_group="media", containers=["web"])
                env = self._workflow_env(root, calls_log)
                env["FORTRESS_FAIL_PHASE"] = failed_phase

                result = subprocess.run(
                    [str(REPO_ROOT / "scripts" / "vm-update"), "media01", "--reboot", "--auto-confirm"],
                    cwd=REPO_ROOT,
                    env=env,
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )

                self.assertEqual(result.returncode, 42)
                self.assertIn(message, result.stderr)
                self.assertEqual(expected_calls, calls_log.read_text().splitlines())

    def test_vm_wait_reboot_accepts_changed_boot_id_without_observed_outage(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            scripts_dir = root / "scripts"
            scripts_dir.mkdir()
            calls_log = root / "calls.log"
            vm_shell = scripts_dir / "vm-shell"
            vm_shell.write_text(
                "#!/usr/bin/env bash\n"
                "printf '%s\\n' \"$*\" >> \"$CALLS_LOG\"\n"
                "if [[ \"$*\" == \"media01 -- sudo cat /var/lib/fortress/vm-update-pre-reboot-boot-id\" ]]; then echo boot-before; exit 0; fi\n"
                "if [[ \"$*\" == \"media01 -- sudo cat /proc/sys/kernel/random/boot_id\" ]]; then echo boot-after; exit 0; fi\n"
                "if [[ \"$*\" == \"media01 -- sudo rm -f /var/lib/fortress/vm-update-pre-reboot-boot-id\" ]]; then exit 0; fi\n"
                "exit 1\n"
            )
            vm_shell.chmod(vm_shell.stat().st_mode | stat.S_IXUSR)
            env = self._workflow_env(root, calls_log)

            result = subprocess.run(
                [
                    str(REPO_ROOT / "scripts" / "vm-wait-reboot"),
                    "media01",
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
            self.assertIn("Waiting for VM media01 to go down after reboot", result.stdout)
            self.assertIn("VM media01 is reachable after reboot", result.stdout)
            self.assertEqual(
                [
                    "media01 -- sudo cat /var/lib/fortress/vm-update-pre-reboot-boot-id",
                    "media01 -- sudo cat /proc/sys/kernel/random/boot_id",
                    "media01 -- sudo rm -f /var/lib/fortress/vm-update-pre-reboot-boot-id",
                ],
                calls_log.read_text().splitlines(),
            )

    def test_vm_wait_reboot_reports_unchanged_boot_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            scripts_dir = root / "scripts"
            scripts_dir.mkdir()
            calls_log = root / "calls.log"
            vm_shell = scripts_dir / "vm-shell"
            vm_shell.write_text(
                "#!/usr/bin/env bash\n"
                "printf '%s\\n' \"$*\" >> \"$CALLS_LOG\"\n"
                "if [[ \"$*\" == \"media01 -- sudo cat /var/lib/fortress/vm-update-pre-reboot-boot-id\" ]]; then echo boot-before; exit 0; fi\n"
                "if [[ \"$*\" == \"media01 -- sudo cat /proc/sys/kernel/random/boot_id\" ]]; then echo boot-before; exit 0; fi\n"
                "exit 1\n"
            )
            vm_shell.chmod(vm_shell.stat().st_mode | stat.S_IXUSR)
            env = self._workflow_env(root, calls_log)

            result = subprocess.run(
                [
                    str(REPO_ROOT / "scripts" / "vm-wait-reboot"),
                    "media01",
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
            self.assertIn("VM media01 boot ID did not change within 1s after reboot", result.stderr)

    def test_vm_update_does_not_rebuild_or_mutate_template_clone_sources(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, calls_log = self._workflow_fixture(tmp)
            env = self._workflow_env(root, calls_log)

            result = subprocess.run(
                [str(REPO_ROOT / "scripts" / "vm-update"), "media01"],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            calls = calls_log.read_text()
            self.assertNotIn("templates-build", calls)
            self.assertNotIn("template-verify", calls)
            self.assertNotIn("template-destroy", calls)
            self.assertNotIn("tofu-wrap", calls)

    def test_vm_update_stops_and_reports_the_failed_phase(self):
        scenarios = {
            "vm-configure": (
                "VM Configure failed for VM media01",
                ["vm-configure media01"],
            ),
            "vm-routine-software-advance": (
                "Routine Software Advancement failed for VM media01",
                ["vm-configure media01", "vm-routine-software-advance media01"],
            ),
        }

        for failed_phase, (message, expected_calls) in scenarios.items():
            with self.subTest(failed_phase=failed_phase), tempfile.TemporaryDirectory() as tmp:
                root, calls_log = self._workflow_fixture(tmp)
                env = self._workflow_env(root, calls_log)
                env["FORTRESS_FAIL_PHASE"] = failed_phase

                result = subprocess.run(
                    [str(REPO_ROOT / "scripts" / "vm-update"), "media01"],
                    cwd=REPO_ROOT,
                    env=env,
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )

                self.assertEqual(result.returncode, 42)
                self.assertIn(message, result.stderr)
                self.assertEqual(expected_calls, calls_log.read_text().splitlines())

    def test_just_vm_update_calls_workflow_script(self):
        justfile = (REPO_ROOT / "justfile").read_text()

        self.assertIn('vm-update vm reboot="false":', justfile)
        self.assertIn("./scripts/vm-update {{vm}}", justfile)
        self.assertIn("./scripts/vm-update {{vm}} --reboot", justfile)
        self.assertIn('"{{reboot}}" = "--reboot"', justfile)

    def test_routine_software_advancement_uses_tmpfs_key_wrapper_for_ansible_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, calls_log = self._workflow_fixture(tmp)
            env = self._workflow_env(root, calls_log)

            result = subprocess.run(
                [str(REPO_ROOT / "scripts" / "vm-routine-software-advance"), "media01"],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            calls = calls_log.read_text()
            self.assertIn("decrypt-keys", calls)
            self.assertIn("inventory/vms/media01.sops.yaml -- ansible-playbook", calls)
            self.assertIn("ansible/playbooks/vm-routine-software-advance.yml", calls)
            self.assertIn("--limit media01", calls)
            self.assertIn('"update_vm": "media01"', calls)

    def test_routine_software_advancement_avoids_removals_and_release_transitions(self):
        playbook = (REPO_ROOT / "ansible" / "playbooks" / "vm-routine-software-advance.yml").read_text()

        self.assertIn("apt-get update", playbook)
        self.assertIn("apt-get --simulate upgrade --with-new-pkgs --no-remove", playbook)
        self.assertIn("apt-get upgrade --assume-yes --with-new-pkgs --no-remove", playbook)
        self.assertNotIn("dist-upgrade", playbook)
        self.assertNotIn("full-upgrade", playbook)
        self.assertNotIn("autoremove", playbook)

    def test_routine_software_advancement_reports_updated_and_security_packages(self):
        playbook = (REPO_ROOT / "ansible" / "playbooks" / "vm-routine-software-advance.yml").read_text()

        self.assertIn("name: Preview routine apt package advancement", playbook)
        self.assertIn("name: Use injected routine apt package advancement preview", playbook)
        self.assertIn("register: fortress_apt_upgrade_preview", playbook)
        self.assertIn("fortress_apt_updated_packages:", playbook)
        self.assertIn("fortress_apt_security_updates:", playbook)
        self.assertIn("select('match', '^Inst ')", playbook)
        self.assertIn("select('search', '(?i)security')", playbook)
        self.assertIn("Updated packages:", playbook)
        self.assertIn("Security updates:", playbook)

    def test_routine_software_advancement_report_expands_package_names(self):
        result = subprocess.run(
            [
                "ansible-playbook",
                str(REPO_ROOT / "ansible" / "playbooks" / "vm-routine-software-advance.yml"),
                "-i",
                "localhost,",
                "-c",
                "local",
                "--extra-vars",
                (
                    '{"update_vm":"localhost",'
                    '"fortress_skip_apt_metadata_refresh":true,'
                    '"fortress_skip_routine_software_apply":true,'
                    '"fortress_apt_upgrade_preview_override":{'
                    '"stdout_lines":['
                    '"Inst openssl [3.0] (3.1 Debian-Security:13/stable-security [amd64])",'
                    '"Inst curl [8.0] (8.1 Debian:13/stable [amd64])",'
                    '"Conf curl (8.1 Debian:13/stable [amd64])"'
                    "]}}"
                ),
            ],
            cwd=REPO_ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        output = result.stdout + result.stderr
        self.assertEqual(result.returncode, 0, output)
        self.assertIn("Updated packages: openssl, curl", output)
        self.assertIn("Security updates: openssl", output)
        self.assertNotIn("\\1", output)

    def _workflow_fixture(self, tmp):
        root = Path(tmp)
        (root / "inventory" / "vms").mkdir(parents=True)
        (root / "inventory" / "services").mkdir()
        (root / "scripts").mkdir()
        (root / "inventory" / "vms" / "media01.yaml").write_text(
            "vmid: 101\n"
            "placement:\n"
            "  host: wintermute\n"
        )
        (root / "inventory" / "vms" / "media01.sops.yaml").write_text("encrypted: value\n")
        (root / "inventory" / "fortress.yaml").write_text("plugin: fortress\nroot: ..\n")
        calls_log = root / "calls.log"
        for name in ["vm-configure", "vm-routine-software-advance", "vm-shell", "vm-wait-reboot"]:
            script = root / "scripts" / name
            script.write_text(
                "#!/usr/bin/env bash\n"
                "name=$(basename \"$0\")\n"
                "printf '%s %s\\n' \"$name\" \"$*\" >> \"$CALLS_LOG\"\n"
                "phase=\"$name\"\n"
                "if [ \"$name\" = vm-shell ] && [[ \" $* \" == *\" systemctl stop \"* ]]; then phase=\"stop-service\"; fi\n"
                "if [ \"$name\" = vm-shell ] && [[ \" $* \" == *\" is-active --quiet \"* && \" $* \" == *\" && exit 1 \"* ]]; then phase=\"verify-service-stopped\"; fi\n"
                "if [ \"$name\" = vm-shell ] && [[ \" $* \" == *\" systemctl reboot \"* ]]; then phase=\"reboot-vm\"; fi\n"
                "if [ \"$name\" = vm-wait-reboot ]; then phase=\"verify-vm-reachable\"; fi\n"
                "if [ \"$name\" = vm-shell ] && [[ \" $* \" == *\" systemctl start \"* ]]; then phase=\"restore-service\"; fi\n"
                "if [ \"$name\" = vm-shell ] && [[ \" $* \" == *\" is-active --quiet \"* && \" $* \" == *\" || exit $? \"* ]]; then phase=\"verify-service-active\"; fi\n"
                "if [ \"$FORTRESS_FAIL_PHASE\" = \"$name\" ] || [ \"$FORTRESS_FAIL_PHASE\" = \"$phase\" ]; then exit 42; fi\n"
            )
            script.chmod(script.stat().st_mode | stat.S_IXUSR)
        decrypt_keys = root / "scripts" / "decrypt-keys"
        decrypt_keys.write_text(
            "#!/usr/bin/env bash\n"
            "printf 'decrypt-keys %s\\n' \"$*\" >> \"$CALLS_LOG\"\n"
            "if [ -n \"$FORTRESS_FAKE_DECRYPT_KEYS_FAIL\" ]; then exit \"$FORTRESS_FAKE_DECRYPT_KEYS_FAIL\"; fi\n"
        )
        decrypt_keys.chmod(decrypt_keys.stat().st_mode | stat.S_IXUSR)
        return root, root / "calls.log"

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
            "  port: 9100\n"
            "deploy:\n"
            "  type: native\n"
            "  package: node-exporter\n"
            f"  service_name: {unit}\n"
        )

    def _workflow_env(self, root, calls_log):
        env = os.environ.copy()
        env["FORTRESS_ROOT"] = str(root)
        env["CALLS_LOG"] = str(calls_log)
        return env


if __name__ == "__main__":
    unittest.main()
