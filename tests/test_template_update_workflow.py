import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

from fortress_workflows import CommandPhase
from fortress_workflows.template_update import TemplateUpdatePlanError, build_template_update_plan


REPO_ROOT = Path(__file__).resolve().parents[1]


class TemplateUpdateWorkflowTests(unittest.TestCase):
    def test_plan_rebuilds_selected_template_with_replacement_then_verifies(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._fixture(tmp)

            plan = build_template_update_plan(
                root,
                host_name="wintermute",
                template_name="debian-13-base",
                keep_on_fail=False,
            )

            self.assertEqual("template-update:wintermute:debian-13-base", plan.id)
            self.assertEqual(["template-rebuild", "template-verify"], [step.id for step in plan.steps])
            rebuild, verify = plan.steps
            self.assertIsInstance(rebuild, CommandPhase)
            self.assertEqual("Template Rebuild", rebuild.display_name)
            self.assertEqual(
                [
                    str(root / "scripts" / "templates-build"),
                    "wintermute",
                    "debian-13-base",
                    "--replace-existing",
                ],
                list(rebuild.command),
            )
            self.assertIsInstance(verify, CommandPhase)
            self.assertEqual("Template Verification", verify.display_name)
            self.assertEqual(
                [
                    str(root / "scripts" / "template-verify"),
                    "host=wintermute",
                    "template=debian-13-base",
                    "keep_on_fail=false",
                ],
                list(verify.command),
            )

    def test_plan_rebuilds_and_verifies_selected_template_for_every_declaring_host(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._fixture(tmp)
            self._write_host(root, "molly", ["debian-13-base"])
            self._write_host(root, "straylight", ["ubuntu-2404-base"])

            plan = build_template_update_plan(
                root,
                host_name="all",
                template_name="debian-13-base",
                keep_on_fail=False,
            )

            self.assertEqual("template-update:all:debian-13-base", plan.id)
            self.assertEqual(
                [
                    "template-rebuild:molly",
                    "template-verify:molly",
                    "template-rebuild:wintermute",
                    "template-verify:wintermute",
                ],
                [step.id for step in plan.steps],
            )
            self.assertEqual(
                [
                    str(root / "scripts" / "templates-build"),
                    "molly",
                    "debian-13-base",
                    "--replace-existing",
                ],
                list(plan.steps[0].command),
            )
            self.assertEqual(
                [
                    str(root / "scripts" / "template-verify"),
                    "host=wintermute",
                    "template=debian-13-base",
                    "keep_on_fail=false",
                ],
                list(plan.steps[3].command),
            )

    def test_plan_rejects_undeclared_host_template_and_host_template_pair(self):
        scenarios = [
            ("ghost", "debian-13-base", "Host 'ghost' is not declared"),
            ("wintermute", "ubuntu-2404-base", "Template 'ubuntu-2404-base' is not declared"),
            ("molly", "debian-13-base", "Host molly does not declare Template debian-13-base"),
        ]
        for host_name, template_name, message in scenarios:
            with self.subTest(host_name=host_name, template_name=template_name), tempfile.TemporaryDirectory() as tmp:
                root = self._fixture(tmp)
                (root / "inventory" / "hosts" / "molly.yaml").write_text(
                    "proxmox:\n"
                    "  templates: []\n"
                )

                with self.assertRaisesRegex(TemplateUpdatePlanError, message):
                    build_template_update_plan(
                        root,
                        host_name=host_name,
                        template_name=template_name,
                        keep_on_fail=False,
                    )

    def test_template_update_runs_rebuild_then_verification_for_selected_host_template(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._fixture(tmp)
            self._write_host(root, "molly", ["debian-13-base"])
            calls_log = self._fake_workflow_scripts(root)
            env = self._workflow_env(root, calls_log)

            result = subprocess.run(
                [
                    str(REPO_ROOT / "scripts" / "template-update"),
                    "host=wintermute",
                    "template=debian-13-base",
                ],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(
                [
                    "templates-build wintermute debian-13-base --replace-existing",
                    "template-verify host=wintermute template=debian-13-base keep_on_fail=false",
                ],
                calls_log.read_text().splitlines(),
            )
            self.assertNotIn("vm-up", calls_log.read_text())
            self.assertNotIn("service-deploy", calls_log.read_text())

    def test_template_update_all_hosts_reports_lineage_and_updates_every_declaring_host(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._fixture(tmp)
            self._write_host(root, "molly", ["debian-13-base"])
            self._write_host(root, "straylight", ["ubuntu-2404-base"])
            self._write_vm(root, "media01", 101, "wintermute", "debian-13-base")
            self._write_vm(root, "dns01", 102, "molly", "debian-13-base")
            service_path = self._write_service(root, "photos", "media01")
            vm_before = (root / "inventory" / "vms" / "media01.yaml").read_text()
            service_before = service_path.read_text()
            calls_log = self._fake_workflow_scripts(root)
            env = self._workflow_env(root, calls_log)

            result = subprocess.run(
                [
                    str(REPO_ROOT / "scripts" / "template-update"),
                    "host=all",
                    "template=debian-13-base",
                ],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Template Update lineage for debian-13-base:", result.stdout)
            self.assertIn("dns01 (vmid 102, host molly)", result.stdout)
            self.assertIn("media01 (vmid 101, host wintermute)", result.stdout)
            self.assertIn("Existing durable VMs are lineage context only; Template Update does not change them.", result.stdout)
            self.assertEqual(
                [
                    "templates-build molly debian-13-base --replace-existing",
                    "template-verify host=molly template=debian-13-base keep_on_fail=false",
                    "templates-build wintermute debian-13-base --replace-existing",
                    "template-verify host=wintermute template=debian-13-base keep_on_fail=false",
                ],
                calls_log.read_text().splitlines(),
            )
            self.assertEqual(vm_before, (root / "inventory" / "vms" / "media01.yaml").read_text())
            self.assertEqual(service_before, service_path.read_text())
            self.assertNotIn("vm-up", calls_log.read_text())
            self.assertNotIn("service-deploy", calls_log.read_text())

    def test_just_template_update_calls_workflow_script_with_explicit_host_template(self):
        justfile = (REPO_ROOT / "justfile").read_text()

        self.assertIn('template-update host template keep_on_fail="false":', justfile)
        self.assertIn("./scripts/template-update host={{host}} template={{template}} keep_on_fail={{keep_on_fail}}", justfile)
        self.assertIn('template-update-all template keep_on_fail="false":', justfile)
        self.assertIn("./scripts/template-update host=all template={{template}} keep_on_fail={{keep_on_fail}}", justfile)

    def test_template_update_validates_before_workflow_commands(self):
        scenarios = [
            ("host=ghost", "template=debian-13-base", "Host 'ghost' is not declared"),
            ("host=wintermute", "template=ubuntu-2404-base", "Template 'ubuntu-2404-base' is not declared"),
            ("host=molly", "template=debian-13-base", "Host molly does not declare Template debian-13-base"),
            ("host=all", "template=ubuntu-2404-base", "No Host declares Template ubuntu-2404-base"),
        ]
        for host_arg, template_arg, message in scenarios:
            with self.subTest(host_arg=host_arg, template_arg=template_arg), tempfile.TemporaryDirectory() as tmp:
                root = self._fixture(tmp)
                (root / "inventory" / "hosts" / "molly.yaml").write_text(
                    "proxmox:\n"
                    "  templates: []\n"
                )
                if host_arg == "host=all":
                    (root / "inventory" / "templates" / "ubuntu-2404-base.yaml").write_text(
                        "name: ubuntu-2404-base\n"
                        "vmid: 9002\n"
                    )
                calls_log = self._fake_workflow_scripts(root)
                env = self._workflow_env(root, calls_log)

                result = subprocess.run(
                    [str(REPO_ROOT / "scripts" / "template-update"), host_arg, template_arg],
                    cwd=REPO_ROOT,
                    env=env,
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )

                self.assertEqual(result.returncode, 1)
                self.assertIn(message, result.stderr)
                self.assertFalse(calls_log.exists())

    def test_template_update_stops_and_reports_failed_phase(self):
        scenarios = [
            (
                "templates-build",
                ["templates-build wintermute debian-13-base --replace-existing"],
                "Template Rebuild debian-13-base@wintermute: templates-build failed intentionally",
            ),
            (
                "template-verify",
                [
                    "templates-build wintermute debian-13-base --replace-existing",
                    "template-verify host=wintermute template=debian-13-base keep_on_fail=false",
                ],
                "Template Verification debian-13-base@wintermute: template-verify failed intentionally",
            ),
        ]
        for failed_phase, expected_calls, message in scenarios:
            with self.subTest(failed_phase=failed_phase), tempfile.TemporaryDirectory() as tmp:
                root = self._fixture(tmp)
                calls_log = self._fake_workflow_scripts(root)
                env = self._workflow_env(root, calls_log)
                env["FORTRESS_FAIL_PHASE"] = failed_phase

                result = subprocess.run(
                    [str(REPO_ROOT / "scripts" / "template-update"), "host=wintermute", "template=debian-13-base"],
                    cwd=REPO_ROOT,
                    env=env,
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )

                self.assertEqual(result.returncode, 42)
                self.assertEqual(expected_calls, calls_log.read_text().splitlines())
                self.assertIn(message, result.stderr)
                if failed_phase == "template-verify":
                    self.assertIn(
                        "Template Verification artifacts not preserved according to keep_on_fail=false",
                        result.stderr,
                    )

    def test_template_update_verification_failure_reports_artifact_preservation_policy(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._fixture(tmp)
            calls_log = self._fake_workflow_scripts(root)
            env = self._workflow_env(root, calls_log)
            env["FORTRESS_FAIL_PHASE"] = "template-verify"

            result = subprocess.run(
                [
                    str(REPO_ROOT / "scripts" / "template-update"),
                    "host=wintermute",
                    "template=debian-13-base",
                    "keep_on_fail=true",
                ],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            self.assertEqual(result.returncode, 42)
            self.assertIn("Template Verification artifacts preserved according to keep_on_fail=true", result.stderr)
            self.assertIn("keep_on_fail=true", calls_log.read_text())

    def _fixture(self, tmp):
        root = Path(tmp)
        (root / "inventory" / "hosts").mkdir(parents=True)
        (root / "inventory" / "templates").mkdir()
        (root / "inventory" / "vms").mkdir()
        (root / "inventory" / "services").mkdir()
        (root / "scripts").mkdir()
        (root / "inventory" / "hosts" / "wintermute.yaml").write_text(
            "proxmox:\n"
            "  templates: [debian-13-base]\n"
        )
        (root / "inventory" / "templates" / "debian-13-base.yaml").write_text(
            "name: debian-13-base\n"
            "vmid: 9001\n"
        )
        return root

    def _write_host(self, root, host_name, templates):
        template_list = ", ".join(templates)
        (root / "inventory" / "hosts" / f"{host_name}.yaml").write_text(
            "proxmox:\n"
            f"  templates: [{template_list}]\n"
        )

    def _write_vm(self, root, vm_name, vmid, host_name, template_name):
        (root / "inventory" / "vms" / f"{vm_name}.yaml").write_text(
            f"vmid: {vmid}\n"
            "placement:\n"
            f"  host: {host_name}\n"
            "source:\n"
            f"  template: {template_name}\n"
            "hardware:\n"
            "  cores: 2\n"
            "  memory: 4096\n"
            "cloud_init:\n"
            f"  hostname: {vm_name}\n"
        )

    def _write_service(self, root, service_name, vm_name):
        path = root / "inventory" / "services" / f"{service_name}.yaml"
        path.write_text(
            f"name: {service_name}\n"
            "backend:\n"
            f"  vm: {vm_name}\n"
            "  port: 8080\n"
        )
        return path

    def _fake_workflow_scripts(self, root):
        calls_log = root / "calls.log"
        for name in ["templates-build", "template-verify"]:
            script = root / "scripts" / name
            script.write_text(
                "#!/usr/bin/env bash\n"
                "name=$(basename \"$0\")\n"
                "printf '%s' \"$name\" >> \"$CALLS_LOG\"\n"
                "if [ \"$#\" -gt 0 ]; then printf ' %s' \"$*\" >> \"$CALLS_LOG\"; fi\n"
                "printf '\\n' >> \"$CALLS_LOG\"\n"
                "if [ \"$FORTRESS_FAIL_PHASE\" = \"$name\" ]; then printf '%s failed intentionally\\n' \"$name\" >&2; exit 42; fi\n"
            )
            script.chmod(script.stat().st_mode | stat.S_IXUSR)
        return calls_log

    def _workflow_env(self, root, calls_log):
        env = os.environ.copy()
        env["FORTRESS_ROOT"] = str(root)
        env["CALLS_LOG"] = str(calls_log)
        return env


if __name__ == "__main__":
    unittest.main()
