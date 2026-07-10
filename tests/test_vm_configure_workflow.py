import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


class VMConfigureWorkflowTests(unittest.TestCase):
    def test_just_vm_configure_calls_workflow_script(self):
        justfile = (REPO_ROOT / "justfile").read_text()

        self.assertIn("vm-configure vm:", justfile)
        self.assertIn("./scripts/vm-configure {{vm}}", justfile)

    def test_vm_configure_rejects_undeclared_vms(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "inventory" / "vms").mkdir(parents=True)
            env = os.environ.copy()
            env["FORTRESS_ROOT"] = str(root)

            result = subprocess.run(
                [str(REPO_ROOT / "scripts" / "vm-configure"), "ghost"],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            self.assertEqual(result.returncode, 1)
            self.assertIn("VM 'ghost' is not declared", result.stderr)

    def test_vm_configure_requires_vm_sibling_sops_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            vm_dir = root / "inventory" / "vms"
            vm_dir.mkdir(parents=True)
            (vm_dir / "media01.yaml").write_text(
                "vmid: 101\n"
                "placement:\n"
                "  host: wintermute\n"
                "source:\n"
                "  template: debian-13-base\n"
                "hardware:\n"
                "  cores: 2\n"
                "  memory: 4096\n"
                "cloud_init:\n"
                "  hostname: media01\n"
            )
            env = os.environ.copy()
            env["FORTRESS_ROOT"] = str(root)

            result = subprocess.run(
                [str(REPO_ROOT / "scripts" / "vm-configure"), "media01"],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            self.assertEqual(result.returncode, 1)
            self.assertIn("VM Sibling SOPS File is required", result.stderr)
            self.assertIn("inventory/vms/media01.sops.yaml", result.stderr)

    def test_vm_configure_uses_tmpfs_key_wrapper_for_ansible_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, calls_log = self._configure_fixture(tmp)
            env = os.environ.copy()
            env["FORTRESS_ROOT"] = str(root)
            env["CALLS_LOG"] = str(calls_log)

            result = subprocess.run(
                [str(REPO_ROOT / "scripts" / "vm-configure"), "media01"],
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
            self.assertIn("ansible/playbooks/vm-configure.yml", calls)
            self.assertIn("--limit media01", calls)
            self.assertIn('"fortress_vm_sops_file":', calls)
            self.assertIn("inventory/vms/media01.sops.yaml", calls)

    def test_vm_configure_predecrypts_forgejo_backend_key_for_runner_registration(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, calls_log = self._configure_fixture(tmp)
            vm_dir = root / "inventory" / "vms"
            service_dir = root / "inventory" / "services"
            service_dir.mkdir(exist_ok=True)
            (service_dir / "forgejo.yaml").write_text(
                "name: forgejo\n"
                "backend:\n"
                "  vm: forgejo-vm\n"
                "deploy:\n"
                "  type: quadlet\n"
                "  containers:\n"
                "    - name: server\n"
                "      image: codeberg.org/forgejo/forgejo:15.0.3\n"
            )
            (vm_dir / "forgejo-vm.yaml").write_text(
                "vmid: 102\n"
                "placement:\n"
                "  host: wintermute\n"
                "source:\n"
                "  template: debian-13-base\n"
                "hardware:\n"
                "  cores: 2\n"
                "  memory: 4096\n"
                "cloud_init:\n"
                "  hostname: forgejo-vm\n"
            )
            (vm_dir / "forgejo-vm.sops.yaml").write_text("encrypted forgejo vm material\n")
            media_vm = vm_dir / "media01.yaml"
            media_vm.write_text(
                media_vm.read_text()
                + "forgejo_runner_runtime:\n"
                + "  forgejo_service: forgejo\n"
                + "  scope: instance\n"
                + "  labels: [\"debian-13:docker://debian:13\"]\n"
                + "  concurrency: 1\n"
                + "  cleanup:\n"
                + "    workspace: after_job\n"
                + "    cache: disposable\n"
            )
            env = os.environ.copy()
            env["FORTRESS_ROOT"] = str(root)
            env["CALLS_LOG"] = str(calls_log)

            result = subprocess.run(
                [str(REPO_ROOT / "scripts" / "vm-configure"), "media01"],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            calls = calls_log.read_text()
            self.assertIn(str(vm_dir / "media01.sops.yaml"), calls)
            self.assertIn(str(vm_dir / "forgejo-vm.sops.yaml"), calls)
            self.assertLess(
                calls.index(str(vm_dir / "media01.sops.yaml")),
                calls.index("-- ansible-playbook"),
            )
            self.assertLess(
                calls.index(str(vm_dir / "forgejo-vm.sops.yaml")),
                calls.index("-- ansible-playbook"),
            )

    def test_vm_configure_returns_child_failure_without_traceback(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, _calls_log = self._configure_fixture(tmp)
            env = os.environ.copy()
            env["FORTRESS_ROOT"] = str(root)
            env["CALLS_LOG"] = str(root / "calls.log")
            env["FORTRESS_FAKE_DECRYPT_KEYS_FAIL"] = "7"

            result = subprocess.run(
                [str(REPO_ROOT / "scripts" / "vm-configure"), "media01"],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            self.assertEqual(result.returncode, 7)
            self.assertNotIn("Traceback", result.stderr)

    def test_tmpfs_key_wrapper_decrypts_structured_bootstrap_private_key(self):
        decrypt_keys = (REPO_ROOT / "scripts" / "decrypt-keys").read_text()

        self.assertIn('["ssh_keys"]["bootstrap"]["private_key"]', decrypt_keys)
        self.assertNotIn("ssh_root_key", decrypt_keys)

    def test_vm_configure_playbook_waits_for_cloud_init_before_admin_finalization(self):
        playbook = (REPO_ROOT / "ansible" / "playbooks" / "vm-configure.yml").read_text()

        self.assertIn("ansible.builtin.wait_for_connection", playbook)
        self.assertIn("cloud-init status --wait", playbook)
        self.assertLess(
            playbook.index("cloud-init status --wait"),
            playbook.index("name: vm_admin_user"),
        )
        self.assertTrue((REPO_ROOT / "ansible" / "roles" / "vm_admin_user" / "tasks" / "main.yml").is_file())

    def test_vm_configure_playbook_writes_nfs_mount_units_before_admin_finalization(self):
        playbook = (REPO_ROOT / "ansible" / "playbooks" / "vm-configure.yml").read_text()

        self.assertIn("name: vm_nfs_mounts", playbook)
        self.assertLess(
            playbook.index("name: vm_nfs_mounts"),
            playbook.index("name: vm_admin_user"),
        )

    def test_vm_configure_playbook_converges_network_addresses_before_other_roles(self):
        playbook = (REPO_ROOT / "ansible" / "playbooks" / "vm-configure.yml").read_text()
        role = (REPO_ROOT / "ansible" / "roles" / "vm_network_addresses" / "tasks" / "main.yml").read_text()
        template = (
            REPO_ROOT / "ansible" / "roles" / "vm_network_addresses" / "templates" / "fortress-network-addresses.sh.j2"
        ).read_text()

        self.assertIn("name: vm_network_addresses", playbook)
        self.assertLess(
            playbook.index("name: vm_network_addresses"),
            playbook.index("name: vm_nfs_mounts"),
        )
        self.assertIn("/etc/fortress-network-intent.yaml", role)
        self.assertIn("secondary_addresses", template)
        self.assertIn("ip address add", template)
        self.assertNotIn("ip address del", template)

    def test_vm_configure_playbook_converges_management_ssh_policy_after_network_addresses(self):
        playbook = (REPO_ROOT / "ansible" / "playbooks" / "vm-configure.yml").read_text()
        role = (REPO_ROOT / "ansible" / "roles" / "management_ssh_policy" / "tasks" / "main.yml").read_text()
        template = (
            REPO_ROOT / "ansible" / "roles" / "management_ssh_policy" / "templates" / "fortress-listen-addresses.conf.j2"
        ).read_text()

        self.assertIn("name: management_ssh_policy", playbook)
        self.assertLess(
            playbook.index("name: vm_network_addresses"),
            playbook.index("name: management_ssh_policy"),
        )
        self.assertLess(
            playbook.index("name: management_ssh_policy"),
            playbook.index("name: vm_nfs_mounts"),
        )
        self.assertIn("when: fortress_vm.management_ssh_policy is defined", playbook)
        self.assertIn("sshd -t", role)
        self.assertIn("systemctl reload sshd", role)
        self.assertIn("when: fortress_management_ssh_policy_dropin.changed", role)
        self.assertIn("ListenAddress {{ listen_address }}", template)

    def test_vm_configure_playbook_configures_tailnet_subnet_router_before_admin_finalization(self):
        playbook = (REPO_ROOT / "ansible" / "playbooks" / "vm-configure.yml").read_text()

        self.assertIn("name: tailnet_subnet_router", playbook)
        self.assertIn("when: fortress_vm.tailnet_subnet_router is defined", playbook)
        self.assertLess(
            playbook.index("name: tailnet_subnet_router"),
            playbook.index("name: vm_admin_user"),
        )

    def test_vm_configure_playbook_applies_baseline_collectors_before_admin_finalization(self):
        playbook = (REPO_ROOT / "ansible" / "playbooks" / "vm-configure.yml").read_text()

        self.assertIn("name: vm_baseline_collectors", playbook)
        self.assertLess(
            playbook.index("name: vm_baseline_collectors"),
            playbook.index("name: vm_admin_user"),
        )

    def test_vm_configure_playbook_installs_guest_support_for_pci_device_assignment(self):
        playbook = (REPO_ROOT / "ansible" / "playbooks" / "vm-configure.yml").read_text()
        role = (REPO_ROOT / "ansible" / "roles" / "vm_pci_device_assignment" / "tasks" / "main.yml").read_text()

        self.assertIn("name: vm_pci_device_assignment", playbook)
        self.assertLess(
            playbook.index("name: vm_pci_device_assignment"),
            playbook.index("name: vm_admin_user"),
        )
        self.assertIn("fortress_vm.hardware.pci_devices", role)
        self.assertIn("linux-image-amd64", role)
        self.assertIn("intel-media-va-driver", role)
        self.assertIn("mesa-va-drivers", role)
        self.assertIn("vainfo", role)
        self.assertIn("fortress-vm-pci-device-assignment.cfg", role)
        self.assertIn("GRUB_DEFAULT=", role)
        self.assertIn("GRUB_DEFAULT=saved", role)
        self.assertIn("grub-editenv /boot/grub/grubenv list", role)
        self.assertIn('grub-set-default "$desired_entry"', role)
        self.assertNotIn("GRUB_DEFAULT='${advanced_id}>${kernel_id}'", role)
        self.assertIn("update-grub", role)
        self.assertIn("stdout_lines", role)

    def test_vm_configure_playbook_converges_forgejo_runner_runtime_from_vm_intent(self):
        playbook = (REPO_ROOT / "ansible" / "playbooks" / "vm-configure.yml").read_text()
        role = (REPO_ROOT / "ansible" / "roles" / "forgejo_runner_runtime" / "tasks" / "main.yml").read_text()
        unit_template = (
            REPO_ROOT / "ansible" / "roles" / "forgejo_runner_runtime" / "templates" / "forgejo-runner.service.j2"
        ).read_text()

        self.assertIn("name: forgejo_runner_runtime", playbook)
        self.assertIn("when: fortress_vm.forgejo_runner_runtime is defined", playbook)
        self.assertLess(
            playbook.index("name: forgejo_runner_runtime"),
            playbook.index("name: vm_admin_user"),
        )
        self.assertIn("forgejo-runner", role)
        self.assertIn("podman", role)
        self.assertIn("git", role)
        self.assertIn("loginctl enable-linger", role)
        self.assertIn("systemctl --user -M {{ forgejo_runner_runtime_user }}@ enable --now podman.socket", role)
        self.assertIn("Register declared Forgejo Runner with Forgejo", role)
        self.assertIn("delegate_to: \"{{ fortress_forgejo_runner_registration.forgejo_backend_vm }}\"", role)
        self.assertIn("fortress-forgejo-server", role)
        self.assertIn("forgejo-cli", role)
        self.assertIn("actions", role)
        self.assertIn("register", role)
        self.assertIn("fortress_forgejo_runner_registration.secret_token", role)
        self.assertIn("ConditionPathExists={{ forgejo_runner_runtime_state_dir }}/.runner", unit_template)

    def test_forgejo_runner_runtime_renders_runner_config_from_vm_intent(self):
        config_template = (
            REPO_ROOT / "ansible" / "roles" / "forgejo_runner_runtime" / "templates" / "config.yaml.j2"
        ).read_text()

        self.assertIn("file: {{ forgejo_runner_runtime_state_dir }}/.runner", config_template)
        self.assertIn("capacity: {{ fortress_vm.forgejo_runner_runtime.concurrency }}", config_template)
        self.assertIn("labels:", config_template)
        self.assertIn("{% for label in fortress_vm.forgejo_runner_runtime.labels %}", config_template)
        self.assertIn("- {{ label | to_json }}", config_template)
        self.assertIn('docker_host: "-"', config_template)
        self.assertNotIn("automount", config_template)
        self.assertNotIn("/var/run/docker.sock", config_template)

    def test_forgejo_runner_runtime_systemd_unit_uses_runner_user_podman_socket(self):
        unit_template = (
            REPO_ROOT / "ansible" / "roles" / "forgejo_runner_runtime" / "templates" / "forgejo-runner.service.j2"
        ).read_text()

        self.assertIn("User={{ forgejo_runner_runtime_user }}", unit_template)
        self.assertIn("Group={{ forgejo_runner_runtime_user }}", unit_template)
        self.assertIn("WorkingDirectory={{ forgejo_runner_runtime_state_dir }}", unit_template)
        self.assertIn(
            "Environment=DOCKER_HOST=unix:///run/user/{{ forgejo_runner_runtime_uid.stdout }}/podman/podman.sock",
            unit_template,
        )
        self.assertIn("ExecStart=/usr/local/bin/forgejo-runner daemon -c {{ forgejo_runner_runtime_config_path }}", unit_template)
        self.assertIn("Restart=on-failure", unit_template)

    def test_forgejo_runner_runtime_renders_registered_runner_state_before_service_start(self):
        role = (REPO_ROOT / "ansible" / "roles" / "forgejo_runner_runtime" / "tasks" / "main.yml").read_text()
        state_template = (
            REPO_ROOT / "ansible" / "roles" / "forgejo_runner_runtime" / "templates" / "runner-state.json.j2"
        ).read_text()

        self.assertLess(
            role.index("Render Forgejo Runner registration state"),
            role.index("Enable Forgejo Runner service and cleanup timer"),
        )
        self.assertIn("forgejo_runner_runtime_registration.stdout", state_template)
        self.assertIn("fortress_forgejo_runner_registration.name", state_template)
        self.assertIn("fortress_forgejo_runner_registration.secret_token", state_template)
        self.assertIn("fortress_forgejo_runner_registration.url", state_template)
        self.assertIn("fortress_forgejo_runner_registration.labels", state_template)

    def test_forgejo_runner_runtime_installs_cleanup_schedule_for_disposable_workspaces(self):
        role = (REPO_ROOT / "ansible" / "roles" / "forgejo_runner_runtime" / "tasks" / "main.yml").read_text()
        cleanup_template = (
            REPO_ROOT / "ansible" / "roles" / "forgejo_runner_runtime" / "templates" / "cleanup.sh.j2"
        ).read_text()

        self.assertIn("fortress-forgejo-runner-cleanup.service", role)
        self.assertIn("fortress-forgejo-runner-cleanup.timer", role)
        self.assertIn("podman system prune --force --filter until=168h", cleanup_template)
        self.assertIn('find "{{ forgejo_runner_runtime_workspace_dir }}"', cleanup_template)
        self.assertIn("-mindepth 1 -maxdepth 1 -mtime +1 -exec rm -rf -- {} +", cleanup_template)

    def test_forgejo_runner_runtime_does_not_model_job_containers_as_services(self):
        role_dir = REPO_ROOT / "ansible" / "roles" / "forgejo_runner_runtime"
        role_text = "\n".join(path.read_text() for path in sorted(role_dir.rglob("*")) if path.is_file())
        service_schema = (REPO_ROOT / "inventory" / "services" / "_schema.json").read_text()

        self.assertNotIn("/etc/containers/systemd", role_text)
        self.assertNotIn(".container", role_text)
        self.assertNotIn("quadlet", role_text.lower())
        self.assertNotIn("forgejo_runner_runtime", service_schema)

    def test_vm_admin_user_role_uses_only_builtin_modules_for_configure(self):
        role = (REPO_ROOT / "ansible" / "roles" / "vm_admin_user" / "tasks" / "main.yml").read_text()

        self.assertNotIn("ansible.posix.authorized_key", role)
        self.assertIn("ansible.builtin.lineinfile", role)
        self.assertIn("authorized_keys", role)

    def _configure_fixture(self, tmp):
        root = Path(tmp)
        vm_dir = root / "inventory" / "vms"
        scripts_dir = root / "scripts"
        vm_dir.mkdir(parents=True)
        scripts_dir.mkdir()
        (root / "inventory" / "fortress.yaml").write_text("plugin: fortress\nroot: ..\n")
        (vm_dir / "media01.yaml").write_text(
            "vmid: 101\n"
            "placement:\n"
            "  host: wintermute\n"
            "source:\n"
            "  template: debian-13-base\n"
            "hardware:\n"
            "  cores: 2\n"
            "  memory: 4096\n"
            "cloud_init:\n"
            "  hostname: media01\n"
        )
        (vm_dir / "media01.sops.yaml").write_text("encrypted: value\n")
        calls_log = root / "calls.log"
        decrypt_keys = scripts_dir / "decrypt-keys"
        decrypt_keys.write_text(
            "#!/usr/bin/env bash\n"
            "printf 'decrypt-keys %s\\n' \"$*\" >> \"$CALLS_LOG\"\n"
            "if [ -n \"$FORTRESS_FAKE_DECRYPT_KEYS_FAIL\" ]; then exit \"$FORTRESS_FAKE_DECRYPT_KEYS_FAIL\"; fi\n"
        )
        decrypt_keys.chmod(decrypt_keys.stat().st_mode | stat.S_IXUSR)
        return root, calls_log
