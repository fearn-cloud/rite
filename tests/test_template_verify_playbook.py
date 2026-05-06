import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


class TemplateVerifyPlaybookTests(unittest.TestCase):
    def test_template_verify_playbook_accepts_vm_lifecycle_contract_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._fixture(tmp)

            result = self._run_playbook(root)

            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)

    def test_template_verify_playbook_reports_lifecycle_contract_failures(self):
        scenarios = {
            "cloud-init": ("FORTRESS_FAKE_CLOUD_INIT_FAIL", "Verify VM Lifecycle Contract: cloud-init completed"),
            "admin-user": ("FORTRESS_FAKE_GETENT_FAIL", "Verify VM Lifecycle Contract: configured VM admin user exists"),
            "sudo": ("FORTRESS_FAKE_SUDO_FAIL", "Verify VM Lifecycle Contract: VM admin user has passwordless sudo"),
            "hostname": ("FORTRESS_FAKE_HOSTNAME", "VM Lifecycle Contract failed: hostname does not match VM declaration"),
        }

        for scenario, (env_name, message) in scenarios.items():
            with self.subTest(scenario=scenario), tempfile.TemporaryDirectory() as tmp:
                root = self._fixture(tmp)
                extra_env = {env_name: "wrong-hostname" if scenario == "hostname" else "ssh-ed25519 different-key"}

                result = self._run_playbook(root, extra_env)

                self.assertNotEqual(result.returncode, 0)
                self.assertIn(message, result.stderr + result.stdout)

    def test_template_verify_playbook_reports_vm_yaml_and_sibling_sops_key_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._fixture(tmp)
            inventory = root / "inventory.yaml"
            inventory.write_text(
                inventory.read_text().replace(
                    "          public_key: ssh-ed25519 expected-key",
                    "          public_key: ssh-ed25519 different-key",
                )
            )

            result = self._run_playbook(root)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("VM Lifecycle Contract failed: VM yaml ssh_public_key must match Sibling SOPS File", result.stderr + result.stdout)

    def test_template_verify_playbook_reports_authorized_key_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._fixture(tmp)
            (root / "authorized_keys").write_text("ssh-ed25519 another-key\n")

            result = self._run_playbook(root)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Verify VM Lifecycle Contract: authorized key contains VM admin public key", result.stderr + result.stdout)

    def _run_playbook(self, root, extra_env=None):
        env = os.environ.copy()
        env["PATH"] = f"{root / 'bin'}:{env['PATH']}"
        env.update(extra_env or {})
        return subprocess.run(
            [
                "ansible-playbook",
                "ansible/playbooks/template-verify.yml",
                "-i",
                str(root / "inventory.yaml"),
            ],
            cwd=REPO_ROOT,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

    def _fixture(self, tmp):
        root = Path(tmp)
        bin_dir = root / "bin"
        bin_dir.mkdir()
        public_key = "ssh-ed25519 expected-key"
        (root / "authorized_keys").write_text(f"{public_key}\n")
        (root / "inventory.yaml").write_text(
            "vms:\n"
            "  hosts:\n"
            "    tmp-template-verify:\n"
            "      ansible_connection: local\n"
            "      ansible_user: admin\n"
            "      fortress_vm:\n"
            "        cloud_init:\n"
            "          hostname: tmp-template-verify\n"
            f"        ssh_public_key: {public_key}\n"
            "      fortress_sibling_ssh_keys:\n"
            "        bootstrap:\n"
            f"          public_key: {public_key}\n"
            f"      template_verify_authorized_keys_path: {root / 'authorized_keys'}\n"
            f"      template_verify_cloud_init_command: {bin_dir / 'cloud-init'}\n"
            f"      template_verify_getent_command: {bin_dir / 'getent'}\n"
            f"      template_verify_sudo_command: {bin_dir / 'sudo'}\n"
            f"      template_verify_hostname_command: {bin_dir / 'hostname'}\n"
            f"      template_verify_grep_command: {bin_dir / 'grep'}\n"
        )
        self._fake_tool(
            bin_dir / "cloud-init",
            "if [ -n \"${FORTRESS_FAKE_CLOUD_INIT_FAIL:-}\" ]; then exit 42; fi\n",
        )
        self._fake_tool(
            bin_dir / "getent",
            "if [ -n \"${FORTRESS_FAKE_GETENT_FAIL:-}\" ]; then exit 42; fi\nprintf 'admin:x:1000:1000::/home/admin:/bin/bash\\n'\n",
        )
        self._fake_tool(
            bin_dir / "sudo",
            "if [ -n \"${FORTRESS_FAKE_SUDO_FAIL:-}\" ]; then exit 42; fi\n",
        )
        self._fake_tool(
            bin_dir / "hostname",
            "printf '%s\\n' \"${FORTRESS_FAKE_HOSTNAME:-tmp-template-verify}\"\n",
        )
        self._fake_tool(
            bin_dir / "grep",
            "exec /usr/bin/grep \"$@\"\n",
        )
        return root

    def _fake_tool(self, path, body):
        path.write_text("#!/usr/bin/env bash\n" + body)
        path.chmod(path.stat().st_mode | stat.S_IXUSR)


if __name__ == "__main__":
    unittest.main()
