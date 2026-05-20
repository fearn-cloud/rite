import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


class VMPrepareSatisfiedTests(unittest.TestCase):
    def test_probe_passes_when_public_keys_match_and_private_key_is_structurally_present(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, calls_log = self._fixture(tmp)
            env = self._fake_tools(root, calls_log, public_key="ssh-ed25519 vm-public demo01")

            result = subprocess.run(
                [str(REPO_ROOT / "scripts" / "vm-prepare-satisfied"), "demo01"],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Prepare already satisfied for VM demo01", result.stdout)
            calls = calls_log.read_text()
            self.assertIn('sops --decrypt --extract ["ssh_keys"]["bootstrap"]["public_key"]', calls)
            self.assertNotIn('["ssh_keys"]["bootstrap"]["private_key"]', calls)

    def test_probe_fails_when_inventory_and_sops_public_keys_differ(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, calls_log = self._fixture(tmp)
            env = self._fake_tools(root, calls_log, public_key="ssh-ed25519 different demo01")

            result = subprocess.run(
                [str(REPO_ROOT / "scripts" / "vm-prepare-satisfied"), "demo01"],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            self.assertEqual(result.returncode, 1)
            self.assertIn("VM SSH public key mismatch for demo01", result.stderr)
            self.assertNotIn('["ssh_keys"]["bootstrap"]["private_key"]', calls_log.read_text())

    def test_probe_fails_when_private_key_is_not_structurally_present(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, calls_log = self._fixture(tmp)
            (root / "inventory" / "vms" / "demo01.sops.yaml").write_text(
                "ssh_keys:\n"
                "  bootstrap:\n"
                "    public_key: ENC[public]\n"
            )
            env = self._fake_tools(root, calls_log, public_key="ssh-ed25519 vm-public demo01")

            result = subprocess.run(
                [str(REPO_ROOT / "scripts" / "vm-prepare-satisfied"), "demo01"],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            self.assertEqual(result.returncode, 1)
            self.assertIn("does not structurally contain ssh_keys.bootstrap.private_key", result.stderr)
            self.assertFalse(calls_log.exists())

    def test_probe_fails_when_present_credential_type_is_not_vm_ssh(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, calls_log = self._fixture(tmp)
            (root / "inventory" / "vms" / "demo01.sops.yaml").write_text(
                "ssh_keys:\n"
                "  bootstrap:\n"
                "    type: ENC[type]\n"
                "    public_key: ENC[public]\n"
                "    private_key: ENC[private]\n"
            )
            env = self._fake_tools(
                root,
                calls_log,
                public_key="ssh-ed25519 vm-public demo01",
                credential_type="host_ssh",
            )

            result = subprocess.run(
                [str(REPO_ROOT / "scripts" / "vm-prepare-satisfied"), "demo01"],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            self.assertEqual(result.returncode, 1)
            self.assertIn("ssh_keys.bootstrap.type must be vm_ssh", result.stderr)

    def _fixture(self, tmp):
        root = Path(tmp)
        vm_dir = root / "inventory" / "vms"
        vm_dir.mkdir(parents=True)
        (vm_dir / "demo01.yaml").write_text(
            "vmid: 801\n"
            "placement:\n"
            "  host: wintermute\n"
            "ssh_public_key: ssh-ed25519 vm-public demo01\n"
        )
        (vm_dir / "demo01.sops.yaml").write_text(
            "ssh_keys:\n"
            "  bootstrap:\n"
            "    public_key: ENC[public]\n"
            "    private_key: ENC[private]\n"
        )
        return root, root / "calls.log"

    def _fake_tools(self, root, calls_log, public_key, credential_type=None):
        bin_dir = root / "bin"
        bin_dir.mkdir()
        sops = bin_dir / "sops"
        sops.write_text(
            "#!/usr/bin/env bash\n"
            "printf 'sops %s\\n' \"$*\" >> \"$CALLS_LOG\"\n"
            "case \"$3\" in\n"
            "  '[\"ssh_keys\"][\"bootstrap\"][\"public_key\"]' ) printf \"$FORTRESS_FAKE_PUBLIC_KEY\\n\" ;;\n"
            "  '[\"ssh_keys\"][\"bootstrap\"][\"type\"]' ) if [ -n \"$FORTRESS_FAKE_TYPE\" ]; then printf \"$FORTRESS_FAKE_TYPE\\n\"; else exit 1; fi ;;\n"
            "  * ) exit 1 ;;\n"
            "esac\n"
        )
        sops.chmod(sops.stat().st_mode | stat.S_IXUSR)
        env = os.environ.copy()
        env["FORTRESS_ROOT"] = str(root)
        env["CALLS_LOG"] = str(calls_log)
        env["FORTRESS_FAKE_PUBLIC_KEY"] = public_key
        env["FORTRESS_FAKE_TYPE"] = credential_type or ""
        env["PATH"] = f"{bin_dir}:{env['PATH']}"
        return env


if __name__ == "__main__":
    unittest.main()
