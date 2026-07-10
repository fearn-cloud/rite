import json
import os
import shutil
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def ansible_value(value):
    if isinstance(value, dict) and set(value) == {"__ansible_unsafe"}:
        return value["__ansible_unsafe"]
    if isinstance(value, dict):
        return {key: ansible_value(child) for key, child in value.items()}
    if isinstance(value, list):
        return [ansible_value(child) for child in value]
    return value


class FortressInventoryPluginTests(unittest.TestCase):
    def load_inventory(self, inventory_path="tests/fixtures/inventory_valid/fortress.yaml"):
        result = subprocess.run(
            [
                "ansible-inventory",
                "-i",
                str(inventory_path),
                "--list",
            ],
            cwd=REPO_ROOT,
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        return json.loads(result.stdout)

    def test_inventory_plugin_builds_host_and_vm_groups(self):
        inventory = self.load_inventory()

        self.assertIn("wintermute", inventory["proxmox_hosts"]["hosts"])
        self.assertIn("media01", inventory["vms"]["hosts"])
        self.assertIn("media01", inventory["vms_on_wintermute"]["hosts"])

    def test_inventory_plugin_shapes_namespaced_hostvars(self):
        inventory = self.load_inventory()
        hostvars = inventory["_meta"]["hostvars"]
        wintermute = ansible_value(hostvars["wintermute"])
        media01 = ansible_value(hostvars["media01"])

        self.assertEqual(wintermute["fortress_entity_kind"], "Host")
        self.assertEqual(wintermute["fortress_host"]["proxmox"]["pve_node_name"], "wintermute")
        self.assertEqual(media01["fortress_entity_kind"], "VM")
        self.assertEqual(media01["fortress_vm"]["placement"]["host"], "wintermute")

    def test_inventory_plugin_exposes_forgejo_runner_registration_facts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "inventory" / "hosts").mkdir(parents=True)
            (root / "inventory" / "vms").mkdir()
            (root / "inventory" / "services").mkdir()
            (root / "inventory" / "templates").mkdir()
            (root / "inventory" / "group_vars").mkdir()
            (root / "fortress.yaml").write_text("plugin: fortress\nroot: .\n")
            (root / "inventory" / "hosts" / "wintermute.yaml").write_text(
                "proxmox:\n"
                "  pve_node_name: wintermute\n"
            )
            (root / "inventory" / "services" / "forgejo.yaml").write_text(
                "name: forgejo\n"
                "backend:\n"
                "  vm: forgejo-vm\n"
                "deploy:\n"
                "  type: quadlet\n"
                "  containers:\n"
                "    - name: server\n"
                "      image: codeberg.org/forgejo/forgejo:15.0.3\n"
                "      env:\n"
                "        FORGEJO__server__ROOT_URL: https://git.example.test/\n"
            )
            (root / "inventory" / "vms" / "forgejo-runner-vm.yaml").write_text(
                "vmid: 1010\n"
                "placement:\n"
                "  host: wintermute\n"
                "source:\n"
                "  template: debian-13-base\n"
                "hardware:\n"
                "  cores: 2\n"
                "  memory: 4096\n"
                "cloud_init:\n"
                "  hostname: forgejo-runner-vm\n"
                "forgejo_runner_runtime:\n"
                "  forgejo_service: forgejo\n"
                "  scope: instance\n"
                "  labels: [\"debian-13:docker://debian:13\"]\n"
                "  concurrency: 1\n"
                "  cleanup:\n"
                "    workspace: after_job\n"
                "    cache: disposable\n"
            )

            inventory = self.load_inventory(root / "fortress.yaml")
            runner = ansible_value(inventory["_meta"]["hostvars"]["forgejo-runner-vm"])
            registration = runner["fortress_forgejo_runner_registration"]

            self.assertEqual("fortress-forgejo-runner-vm", registration["name"])
            self.assertEqual("forgejo-vm", registration["forgejo_backend_vm"])
            self.assertEqual("", registration["cli_scope"])
            self.assertEqual("https://git.example.test/", registration["url"])
            self.assertEqual(["debian-13:docker://debian:13"], registration["labels"])
            self.assertRegex(registration["secret_token"], r"^[0-9a-f]{40}$")

    def test_inventory_plugin_exposes_datasets_to_ansible(self):
        inventory = self.load_inventory()
        media01 = ansible_value(inventory["_meta"]["hostvars"]["media01"])

        self.assertEqual(media01["fortress_datasets"]["media"]["name"], "media")

    def test_inventory_plugin_exposes_nas_endpoints_to_ansible(self):
        inventory = self.load_inventory()
        media01 = ansible_value(inventory["_meta"]["hostvars"]["media01"])

        self.assertEqual(media01["fortress_nas_endpoints"]["truenas"]["share_address"], "10.0.20.10")

    def test_inventory_plugin_materializes_sibling_sops_ssh_key_to_tmpfs_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            host_dir = root / "inventory" / "hosts"
            host_dir.mkdir(parents=True)
            (root / "inventory" / "vms").mkdir()
            (root / "inventory" / "services").mkdir()
            (root / "inventory" / "templates").mkdir()
            (root / "inventory" / "group_vars").mkdir()
            (root / "fortress.yaml").write_text("plugin: fortress\nroot: .\n")
            (host_dir / "wintermute.yaml").write_text("proxmox:\n  pve_node_name: wintermute\n")
            (host_dir / "wintermute.sops.yaml").write_text("encrypted: value\n")

            bin_dir = root / "bin"
            bin_dir.mkdir()
            fake_sops = bin_dir / "sops"
            fake_sops.write_text(
                "#!/usr/bin/env bash\n"
                "printf '%s\\n' \"$*\" >> \"$SOPS_LOG\"\n"
                "printf '%s' 'OPENSSH PRIVATE KEY'\n"
            )
            fake_sops.chmod(fake_sops.stat().st_mode | stat.S_IXUSR)
            key_dir = root / "tmpfs"

            env = os.environ.copy()
            env["PATH"] = f"{bin_dir}:{env['PATH']}"
            env["FORTRESS_KEY_DIR"] = str(key_dir)
            env["SOPS_LOG"] = str(root / "sops.log")

            result = subprocess.run(
                ["ansible-inventory", "-i", str(root / "fortress.yaml"), "--list"],
                cwd=REPO_ROOT,
                env=env,
                check=True,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            hostvars = ansible_value(json.loads(result.stdout)["_meta"]["hostvars"])

            self.assertEqual(hostvars["wintermute"]["ansible_ssh_private_key_file"], str(key_dir / "wintermute.key"))
            self.assertEqual((key_dir / "wintermute.key").read_text(), "OPENSSH PRIVATE KEY")
            self.assertIn('["ssh_keys"]["bootstrap"]["private_key"]', (root / "sops.log").read_text())

    def test_inventory_plugin_preserves_private_key_trailing_newline(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            host_dir = root / "inventory" / "hosts"
            host_dir.mkdir(parents=True)
            (root / "inventory" / "vms").mkdir()
            (root / "inventory" / "services").mkdir()
            (root / "inventory" / "templates").mkdir()
            (root / "inventory" / "group_vars").mkdir()
            (root / "fortress.yaml").write_text("plugin: fortress\nroot: .\n")
            (host_dir / "wintermute.yaml").write_text("proxmox:\n  pve_node_name: wintermute\n")
            (host_dir / "wintermute.sops.yaml").write_text("encrypted: value\n")

            bin_dir = root / "bin"
            bin_dir.mkdir()
            fake_sops = bin_dir / "sops"
            fake_sops.write_text(
                "#!/usr/bin/env bash\n"
                "case \"$*\" in\n"
                "  *'public_key'* ) printf '%s\\n' 'ssh-ed25519 public-key' ;;\n"
                "  *'private_key'* ) printf '%s\\n' 'OPENSSH PRIVATE KEY' ;;\n"
                "esac\n"
            )
            fake_sops.chmod(fake_sops.stat().st_mode | stat.S_IXUSR)
            key_dir = root / "tmpfs"

            env = os.environ.copy()
            env["PATH"] = f"{bin_dir}:{env['PATH']}"
            env["FORTRESS_KEY_DIR"] = str(key_dir)

            subprocess.run(
                ["ansible-inventory", "-i", str(root / "fortress.yaml"), "--list"],
                cwd=REPO_ROOT,
                env=env,
                check=True,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            self.assertEqual((key_dir / "wintermute.key").read_text(), "OPENSSH PRIVATE KEY\n")

    def test_inventory_plugin_exposes_sibling_sops_bootstrap_public_key_as_hostvar(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            vm_dir = root / "inventory" / "vms"
            vm_dir.mkdir(parents=True)
            (root / "inventory" / "hosts").mkdir()
            (root / "inventory" / "services").mkdir()
            (root / "inventory" / "templates").mkdir()
            (root / "inventory" / "group_vars").mkdir()
            (root / "fortress.yaml").write_text("plugin: fortress\nroot: .\n")
            (vm_dir / "tmp-template-verify.yaml").write_text(
                "vmid: 8901\n"
                "placement:\n"
                "  host: wintermute\n"
                "source:\n"
                "  template: debian-13-base\n"
                "hardware:\n"
                "  cores: 1\n"
                "  memory: 1024\n"
                "cloud_init:\n"
                "  hostname: tmp-template-verify\n"
                "ssh_public_key: ssh-ed25519 vm-yaml-key\n"
            )
            (vm_dir / "tmp-template-verify.sops.yaml").write_text("encrypted: value\n")

            bin_dir = root / "bin"
            bin_dir.mkdir()
            fake_sops = bin_dir / "sops"
            fake_sops.write_text(
                "#!/usr/bin/env bash\n"
                "printf '%s\\n' \"$*\" >> \"$SOPS_LOG\"\n"
                "case \"$*\" in\n"
                "  *'public_key'* ) printf '%s' 'ssh-ed25519 sops-public-key' ;;\n"
                "  *'private_key'* ) printf '%s' 'OPENSSH PRIVATE KEY' ;;\n"
                "esac\n"
            )
            fake_sops.chmod(fake_sops.stat().st_mode | stat.S_IXUSR)

            env = os.environ.copy()
            env["PATH"] = f"{bin_dir}:{env['PATH']}"
            env["FORTRESS_KEY_DIR"] = str(root / "tmpfs")
            env["SOPS_LOG"] = str(root / "sops.log")

            result = subprocess.run(
                ["ansible-inventory", "-i", str(root / "fortress.yaml"), "--list"],
                cwd=REPO_ROOT,
                env=env,
                check=True,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            hostvars = ansible_value(json.loads(result.stdout)["_meta"]["hostvars"])

            self.assertEqual(
                hostvars["tmp-template-verify"]["fortress_sibling_ssh_keys"]["bootstrap"]["public_key"],
                "ssh-ed25519 sops-public-key",
            )
            self.assertIn('["ssh_keys"]["bootstrap"]["public_key"]', (root / "sops.log").read_text())

    def test_inventory_plugin_uses_existing_tmpfs_key_without_decrypting_again(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            host_dir = root / "inventory" / "hosts"
            host_dir.mkdir(parents=True)
            (root / "inventory" / "vms").mkdir()
            (root / "inventory" / "services").mkdir()
            (root / "inventory" / "templates").mkdir()
            (root / "inventory" / "group_vars").mkdir()
            (root / "fortress.yaml").write_text("plugin: fortress\nroot: .\n")
            (host_dir / "wintermute.yaml").write_text("proxmox:\n  pve_node_name: wintermute\n")
            (host_dir / "wintermute.sops.yaml").write_text("encrypted: value\n")
            key_dir = root / "tmpfs"
            key_dir.mkdir()
            (key_dir / "wintermute.key").write_text("PREDECRYPTED KEY")

            bin_dir = root / "bin"
            bin_dir.mkdir()
            fake_sops = bin_dir / "sops"
            sops_log = root / "sops.log"
            fake_sops.write_text(
                "#!/usr/bin/env bash\n"
                "printf '%s\\n' \"$*\" >> \"$SOPS_LOG\"\n"
                "case \"$*\" in\n"
                "  *'public_key'* ) printf '%s' 'ssh-ed25519 existing-public-key' ;;\n"
                "  *'private_key'* ) exit 9 ;;\n"
                "esac\n"
            )
            fake_sops.chmod(fake_sops.stat().st_mode | stat.S_IXUSR)

            env = os.environ.copy()
            env["PATH"] = f"{bin_dir}:{env['PATH']}"
            env["FORTRESS_KEY_DIR"] = str(key_dir)
            env["SOPS_LOG"] = str(sops_log)

            result = subprocess.run(
                ["ansible-inventory", "-i", str(root / "fortress.yaml"), "--list"],
                cwd=REPO_ROOT,
                env=env,
                check=True,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            hostvars = ansible_value(json.loads(result.stdout)["_meta"]["hostvars"])

            self.assertEqual(hostvars["wintermute"]["ansible_ssh_private_key_file"], str(key_dir / "wintermute.key"))
            self.assertIn('["ssh_keys"]["bootstrap"]["public_key"]', sops_log.read_text())
            self.assertNotIn('["ssh_keys"]["bootstrap"]["private_key"]', sops_log.read_text())

    def test_inventory_plugin_allows_sibling_sops_file_without_ssh_keys(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            vm_dir = root / "inventory" / "vms"
            vm_dir.mkdir(parents=True)
            (root / "inventory" / "hosts").mkdir()
            (root / "inventory" / "services").mkdir()
            (root / "inventory" / "templates").mkdir()
            (root / "inventory" / "group_vars").mkdir()
            (root / "fortress.yaml").write_text("plugin: fortress\nroot: .\n")
            (vm_dir / "pbs-vm.yaml").write_text(
                "vmid: 1200\n"
                "placement:\n"
                "  host: wintermute\n"
                "network:\n"
                "  interfaces:\n"
                "    - address: 10.0.10.120/24\n"
            )
            (vm_dir / "pbs-vm.sops.yaml").write_text("recovery_secrets:\n  pbs_encryption_key:\n    value: encrypted\n")

            bin_dir = root / "bin"
            bin_dir.mkdir()
            fake_sops = bin_dir / "sops"
            sops_log = root / "sops.log"
            fake_sops.write_text(
                "#!/usr/bin/env bash\n"
                "printf '%s\\n' \"$*\" >> \"$SOPS_LOG\"\n"
                "printf 'error truncating tree: component ['\\''ssh_keys'\\''] not found\\n' >&2\n"
                "exit 1\n"
            )
            fake_sops.chmod(fake_sops.stat().st_mode | stat.S_IXUSR)

            env = os.environ.copy()
            env["PATH"] = f"{bin_dir}:{env['PATH']}"
            env["FORTRESS_KEY_DIR"] = str(root / "tmpfs")
            env["SOPS_LOG"] = str(sops_log)

            result = subprocess.run(
                ["ansible-inventory", "-i", str(root / "fortress.yaml"), "--list"],
                cwd=REPO_ROOT,
                env=env,
                check=True,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            hostvars = ansible_value(json.loads(result.stdout)["_meta"]["hostvars"])

            self.assertEqual(hostvars["pbs-vm"]["ansible_host"], "10.0.10.120")
            self.assertNotIn("fortress_sibling_ssh_keys", hostvars["pbs-vm"])
            self.assertNotIn("ansible_ssh_private_key_file", hostvars["pbs-vm"])

    def test_inventory_plugin_sets_host_connection_from_management_address(self):
        inventory = self.load_inventory()
        wintermute = ansible_value(inventory["_meta"]["hostvars"]["wintermute"])

        self.assertEqual(wintermute["ansible_host"], "10.0.0.10")
        self.assertEqual(wintermute["ansible_user"], "root")
        self.assertIn("StrictHostKeyChecking=accept-new", wintermute["ansible_ssh_common_args"])
        self.assertIn("UserKnownHostsFile=/dev/shm/fortress/known_hosts", wintermute["ansible_ssh_common_args"])

    def test_inventory_plugin_sets_vm_connection_from_inventory(self):
        inventory = self.load_inventory()
        media01 = ansible_value(inventory["_meta"]["hostvars"]["media01"])

        self.assertEqual(media01["ansible_host"], "10.0.10.101")
        self.assertEqual(media01["ansible_user"], "admin")
        self.assertIn("StrictHostKeyChecking=accept-new", media01["ansible_ssh_common_args"])
        self.assertIn("UserKnownHostsFile=/dev/shm/fortress/known_hosts", media01["ansible_ssh_common_args"])

    def test_inventory_plugin_disables_known_hosts_for_generated_temporary_vms(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "inventory_valid"
            shutil.copytree(REPO_ROOT / "tests" / "fixtures" / "inventory_valid", root)
            generated_vm = root / "inventory" / "vms" / "tmp-template-verify.yaml"
            generated_vm.write_text(
                "vmid: 8901\n"
                "description: Generated Template Verification VM. Do not edit by hand.\n"
                "lifecycle:\n"
                "  kind: operational\n"
                "  purpose: template-verification\n"
                "  generated: true\n"
                "placement:\n"
                "  host: wintermute\n"
                "source:\n"
                "  template: debian-13-base\n"
                "hardware:\n"
                "  cores: 1\n"
                "  memory: 1024\n"
                "network:\n"
                "  interfaces:\n"
                "    - bridge: vmbr0\n"
                "      address: 10.0.10.223/24\n"
                "cloud_init:\n"
                "  hostname: tmp-template-verify\n"
            )

            inventory = self.load_inventory(root / "fortress.yaml")
            vm = ansible_value(inventory["_meta"]["hostvars"]["tmp-template-verify"])

            self.assertIn("StrictHostKeyChecking=no", vm["ansible_ssh_common_args"])
            self.assertIn("UserKnownHostsFile=/dev/null", vm["ansible_ssh_common_args"])
