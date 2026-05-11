import json
import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


class HostShellWorkflowTests(unittest.TestCase):
    def test_just_host_shell_calls_workflow_script(self):
        justfile = (REPO_ROOT / "justfile").read_text()

        self.assertIn("host-shell host:", justfile)
        self.assertIn("./scripts/host-shell {{host}}", justfile)

    def test_host_shell_rejects_extra_arguments(self):
        result = subprocess.run(
            [str(REPO_ROOT / "scripts" / "host-shell"), "wintermute", "hostname"],
            cwd=REPO_ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        self.assertEqual(result.returncode, 2)
        self.assertIn("usage: scripts/host-shell <host>", result.stderr)

    def test_host_shell_rejects_undeclared_hosts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "inventory" / "hosts").mkdir(parents=True)
            env = os.environ.copy()
            env["FORTRESS_ROOT"] = str(root)

            result = subprocess.run(
                [str(REPO_ROOT / "scripts" / "host-shell"), "ghost"],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            self.assertEqual(result.returncode, 1)
            self.assertIn("Host 'ghost' is not declared", result.stderr)

    def test_host_shell_requires_host_sibling_sops_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            host_dir = root / "inventory" / "hosts"
            host_dir.mkdir(parents=True)
            (host_dir / "wintermute.yaml").write_text("network:\n  management_address: 10.0.0.2\n")
            env = os.environ.copy()
            env["FORTRESS_ROOT"] = str(root)

            result = subprocess.run(
                [str(REPO_ROOT / "scripts" / "host-shell"), "wintermute"],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            self.assertEqual(result.returncode, 1)
            self.assertIn("Host Sibling SOPS File is required", result.stderr)
            self.assertIn("inventory/hosts/wintermute.sops.yaml", result.stderr)

    def test_host_shell_fails_before_ssh_without_ansible_host(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, calls_log = self._shell_fixture(tmp, {"ansible_user": "root"})
            env = self._shell_env(root, calls_log)

            result = subprocess.run(
                [str(REPO_ROOT / "scripts" / "host-shell"), "wintermute"],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            self.assertEqual(result.returncode, 1)
            self.assertIn("Host 'wintermute' has no ansible_host in Ansible Inventory", result.stderr)
            self.assertNotIn("ssh ", calls_log.read_text())

    def test_host_shell_uses_ansible_inventory_connection_vars_for_ssh(self):
        hostvars = {
            "ansible_host": "10.0.0.2",
            "ansible_user": "root",
            "ansible_ssh_private_key_file": "/dev/shm/fortress/wintermute.key",
            "ansible_ssh_common_args": "-o StrictHostKeyChecking=accept-new",
        }
        with tempfile.TemporaryDirectory() as tmp:
            root, calls_log = self._shell_fixture(tmp, hostvars)
            env = self._shell_env(root, calls_log)

            result = subprocess.run(
                [str(REPO_ROOT / "scripts" / "host-shell"), "host=wintermute"],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("ansible-inventory -i", calls_log.read_text())
            self.assertIn("decrypt-keys", calls_log.read_text())
            self.assertIn("inventory/hosts/wintermute.sops.yaml -- ssh", calls_log.read_text())
            self.assertIn(
                "ssh -t -o StrictHostKeyChecking=accept-new -i /dev/shm/fortress/wintermute.key root@10.0.0.2",
                calls_log.read_text(),
            )

    def _shell_fixture(self, tmp, host_hostvars):
        root = Path(tmp)
        host_dir = root / "inventory" / "hosts"
        bin_dir = root / "bin"
        host_dir.mkdir(parents=True)
        bin_dir.mkdir()
        (root / "inventory" / "fortress.yaml").write_text("plugin: fortress\nroot: ..\n")
        (host_dir / "wintermute.yaml").write_text("network:\n  management_address: 10.0.0.2\n")
        (host_dir / "wintermute.sops.yaml").write_text("encrypted: value\n")

        calls_log = root / "calls.log"
        inventory = {"_meta": {"hostvars": {"wintermute": host_hostvars}}}
        fake_inventory = bin_dir / "ansible-inventory"
        fake_inventory.write_text(
            "#!/usr/bin/env python3\n"
            "import json, os, sys\n"
            "with open(os.environ['CALLS_LOG'], 'a') as log:\n"
            "    log.write('ansible-inventory ' + ' '.join(sys.argv[1:]) + '\\n')\n"
            f"print({json.dumps(inventory)!r})\n"
        )
        fake_inventory.chmod(fake_inventory.stat().st_mode | stat.S_IXUSR)

        fake_ssh = bin_dir / "ssh"
        fake_ssh.write_text(
            "#!/usr/bin/env bash\n"
            "printf 'ssh %s\\n' \"$*\" >> \"$CALLS_LOG\"\n"
        )
        fake_ssh.chmod(fake_ssh.stat().st_mode | stat.S_IXUSR)

        scripts_dir = root / "scripts"
        scripts_dir.mkdir()
        fake_decrypt_keys = scripts_dir / "decrypt-keys"
        fake_decrypt_keys.write_text(
            "#!/usr/bin/env bash\n"
            "printf 'decrypt-keys %s\\n' \"$*\" >> \"$CALLS_LOG\"\n"
            "while [ \"$1\" != \"--\" ]; do shift; done\n"
            "shift\n"
            "exec \"$@\"\n"
        )
        fake_decrypt_keys.chmod(fake_decrypt_keys.stat().st_mode | stat.S_IXUSR)
        return root, calls_log

    def _shell_env(self, root, calls_log):
        env = os.environ.copy()
        env["FORTRESS_ROOT"] = str(root)
        env["CALLS_LOG"] = str(calls_log)
        env["PATH"] = f"{root / 'bin'}:{env['PATH']}"
        return env


if __name__ == "__main__":
    unittest.main()
