import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


class HostBootstrapWorkflowTests(unittest.TestCase):
    def test_bootstrap_refuses_when_host_sops_file_has_bootstrap_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            host_dir = root / "inventory" / "hosts"
            host_dir.mkdir(parents=True)
            (host_dir / "wintermute.yaml").write_text(
                "network:\n"
                "  management_address: 10.0.0.10\n"
            )
            (host_dir / "wintermute.sops.yaml").write_text(
                "ssh_keys:\n"
                "  bootstrap:\n"
                "    type: host_ssh\n"
            )

            bin_dir = root / "bin"
            bin_dir.mkdir()
            calls_log = root / "calls.log"
            for name in ("ssh-keygen", "ansible-playbook", "sops"):
                tool = bin_dir / name
                tool.write_text(
                    "#!/usr/bin/env bash\n"
                    f"printf '{name}\\n' >> '{calls_log}'\n"
                    "exit 0\n"
                )
                tool.chmod(tool.stat().st_mode | stat.S_IXUSR)

            env = os.environ.copy()
            env["PATH"] = f"{bin_dir}:{env['PATH']}"
            env["FORTRESS_ROOT"] = str(root)
            env["FORTRESS_BOOTSTRAP_SSH_KEY"] = str(root / "bootstrap.key")

            result = subprocess.run(
                [str(REPO_ROOT / "scripts" / "host-bootstrap"), "wintermute"],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            self.assertEqual(result.returncode, 1)
            self.assertIn("already contains a bootstrap key entry", result.stderr)
            self.assertFalse(calls_log.exists())

    def test_bootstrap_generates_key_runs_playbook_and_writes_structured_sops_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            host_dir = root / "inventory" / "hosts"
            host_dir.mkdir(parents=True)
            (host_dir / "wintermute.yaml").write_text(
                "network:\n"
                "  management_address: 10.0.0.10\n"
            )
            bootstrap_key = root / "bootstrap.key"
            bootstrap_key.write_text("shared private key\n")

            bin_dir = root / "bin"
            bin_dir.mkdir()
            calls_log = root / "calls.log"

            ssh_keygen = bin_dir / "ssh-keygen"
            ssh_keygen.write_text(
                "#!/usr/bin/env bash\n"
                f"printf 'ssh-keygen %s\\n' \"$*\" >> '{calls_log}'\n"
                "if [ \"$1\" = \"-y\" ]; then\n"
                "  printf 'ssh-ed25519 shared-public bootstrap\\n'\n"
                "  exit 0\n"
                "fi\n"
                "while [ \"$#\" -gt 0 ]; do\n"
                "  if [ \"$1\" = \"-f\" ]; then shift; key_path=\"$1\"; fi\n"
                "  shift\n"
                "done\n"
                "printf 'PRIVATE KEY FOR HOST\\n' > \"$key_path\"\n"
                "printf 'ssh-ed25519 host-public wintermute\\n' > \"$key_path.pub\"\n"
            )
            ssh_keygen.chmod(ssh_keygen.stat().st_mode | stat.S_IXUSR)

            ansible_playbook = bin_dir / "ansible-playbook"
            ansible_playbook.write_text(
                "#!/usr/bin/env bash\n"
                f"printf 'ansible-playbook %s\\n' \"$*\" >> '{calls_log}'\n"
                "exit 0\n"
            )
            ansible_playbook.chmod(ansible_playbook.stat().st_mode | stat.S_IXUSR)

            sops = bin_dir / "sops"
            sops.write_text(
                "#!/usr/bin/env bash\n"
                f"printf 'sops %s\\n' \"$*\" >> '{calls_log}'\n"
                "while [ \"$#\" -gt 0 ]; do\n"
                "  if [ \"$1\" = \"--output\" ]; then shift; output=\"$1\"; fi\n"
                "  input=\"$1\"\n"
                "  shift\n"
                "done\n"
                "cp \"$input\" \"$output\"\n"
            )
            sops.chmod(sops.stat().st_mode | stat.S_IXUSR)

            env = os.environ.copy()
            env["PATH"] = f"{bin_dir}:{env['PATH']}"
            env["FORTRESS_ROOT"] = str(root)
            env["FORTRESS_BOOTSTRAP_SSH_KEY"] = str(bootstrap_key)

            result = subprocess.run(
                [str(REPO_ROOT / "scripts" / "host-bootstrap"), "wintermute"],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            calls = calls_log.read_text()
            self.assertIn("ssh-keygen -t ed25519", calls)
            self.assertIn("ansible/playbooks/host-bootstrap.yml", calls)
            self.assertIn("--private-key", calls)
            self.assertIn(str(bootstrap_key), calls)
            self.assertIn("sops --encrypt --config", calls)
            self.assertIn("--filename-override", calls)

            host_sops = host_dir / "wintermute.sops.yaml"
            self.assertTrue(host_sops.is_file())
            content = host_sops.read_text()
            self.assertIn("ssh_keys:", content)
            self.assertIn("  bootstrap:", content)
            self.assertIn("type: host_ssh", content)
            self.assertIn("created:", content)
            self.assertIn("public_key: ssh-ed25519 host-public wintermute", content)
            self.assertIn("private_key: |", content)
            self.assertIn("PRIVATE KEY FOR HOST", content)

    def test_just_host_bootstrap_calls_workflow_script(self):
        justfile = (REPO_ROOT / "justfile").read_text()

        self.assertIn("host-bootstrap host:", justfile)
        self.assertIn("./scripts/host-bootstrap {{host}}", justfile)

    def test_bootstrap_rejects_named_just_argument_shape(self):
        result = subprocess.run(
            [str(REPO_ROOT / "scripts" / "host-bootstrap"), "host=wintermute"],
            cwd=REPO_ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        self.assertEqual(result.returncode, 2)
        self.assertIn("positional argument", result.stderr)
        self.assertIn("just host-bootstrap wintermute", result.stderr)

    def test_host_bootstrap_playbook_verifies_new_key_before_removing_shared_key(self):
        playbook = (REPO_ROOT / "ansible" / "playbooks" / "host-bootstrap.yml").read_text()

        verify_index = playbook.index("Verify per-host private key authenticates")
        remove_index = playbook.index("Remove shared bootstrap public key")
        self.assertLess(verify_index, remove_index)
        self.assertIn("ansible.posix.authorized_key", playbook)
        self.assertIn("state: absent", playbook)

    def test_new_host_runbook_documents_bootstrap_step(self):
        runbook = REPO_ROOT / "runbooks" / "new-host.md"

        self.assertTrue(runbook.is_file())
        content = runbook.read_text()
        self.assertIn("just host-bootstrap <name>", content)
        self.assertIn("shared bootstrap SSH key", content)
        self.assertIn("inventory/hosts/<name>.sops.yaml", content)
        self.assertIn("refuses to re-run", content)
