import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


class TemplateDestroyWorkflowTests(unittest.TestCase):
    def test_rejects_undeclared_template(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, calls_log = self._workflow_fixture(tmp)
            env = self._workflow_env(root, calls_log)

            result = subprocess.run(
                [str(REPO_ROOT / "scripts" / "template-destroy"), "wintermute", "ghost"],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            self.assertEqual(result.returncode, 1)
            self.assertIn("'ghost' is not declared", result.stderr)
            self.assertFalse(calls_log.exists())

    def test_local_qm_destroy_wiring(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, calls_log = self._workflow_fixture(tmp)
            env = self._workflow_env(root, calls_log)

            result = subprocess.run(
                [str(REPO_ROOT / "scripts" / "template-destroy"), "wintermute", "debian-12-base"],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(["qm destroy 9001"], calls_log.read_text().splitlines())

    def test_preserves_template_yaml_by_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, calls_log = self._workflow_fixture(tmp)
            template_yaml = root / "inventory" / "templates" / "debian-12-base.yaml"
            original = template_yaml.read_text()
            env = self._workflow_env(root, calls_log)

            result = subprocess.run(
                [str(REPO_ROOT / "scripts" / "template-destroy"), "wintermute", "debian-12-base"],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(original, template_yaml.read_text())

    def test_delete_template_yaml_flag_removes_yaml_after_destroy(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, calls_log = self._workflow_fixture(tmp)
            template_yaml = root / "inventory" / "templates" / "debian-12-base.yaml"
            env = self._workflow_env(root, calls_log)

            result = subprocess.run(
                [
                    str(REPO_ROOT / "scripts" / "template-destroy"),
                    "wintermute", "debian-12-base", "--delete-template-yaml",
                ],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse(template_yaml.exists())
            self.assertIn("Deleted Template YAML:", result.stdout)

    def test_just_template_destroy_calls_workflow_script(self):
        justfile = (REPO_ROOT / "justfile").read_text()

        self.assertIn('template-destroy host template delete_template_yaml="false":', justfile)
        self.assertIn('"{{delete_template_yaml}}" = "delete_template_yaml=true"', justfile)
        self.assertIn("./scripts/template-destroy {{host}} {{template}} --delete-template-yaml", justfile)

    def test_rejects_undeclared_host(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, calls_log = self._workflow_fixture(tmp)
            env = self._workflow_env(root, calls_log)

            result = subprocess.run(
                [str(REPO_ROOT / "scripts" / "template-destroy"), "phantom", "debian-12-base"],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            self.assertEqual(result.returncode, 1)
            self.assertIn("'phantom' is not declared", result.stderr)
            self.assertFalse(calls_log.exists())

    def _workflow_fixture(self, tmp):
        root = Path(tmp)
        hosts_dir = root / "inventory" / "hosts"
        templates_dir = root / "inventory" / "templates"
        bin_dir = root / "bin"
        hosts_dir.mkdir(parents=True)
        templates_dir.mkdir(parents=True)
        bin_dir.mkdir()

        (hosts_dir / "wintermute.yaml").write_text(
            "proxmox:\n"
            "  pve_node_name: wintermute\n"
            "  templates:\n"
            "    - debian-12-base\n"
            "network:\n"
            "  management_address: 10.10.0.11\n"
        )
        (templates_dir / "debian-12-base.yaml").write_text(
            "name: debian-12-base\n"
            "vmid: 9001\n"
        )

        calls_log = root / "calls.log"
        qm = bin_dir / "qm"
        qm.write_text(
            "#!/usr/bin/env bash\n"
            'printf \'qm %s\\n\' "$*" >> "$CALLS_LOG"\n'
        )
        qm.chmod(qm.stat().st_mode | stat.S_IXUSR)
        return root, calls_log

    def _workflow_env(self, root, calls_log):
        env = os.environ.copy()
        env["FORTRESS_ROOT"] = str(root)
        env["CALLS_LOG"] = str(calls_log)
        env["PATH"] = str(root / "bin") + ":" + env.get("PATH", "")
        return env


if __name__ == "__main__":
    unittest.main()
