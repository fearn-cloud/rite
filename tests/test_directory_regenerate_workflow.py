import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


class DirectoryRegenerateWorkflowTests(unittest.TestCase):
    def test_just_directory_regenerate_calls_workflow_script(self):
        justfile = (REPO_ROOT / "justfile").read_text()

        self.assertIn("directory-regenerate:", justfile)
        self.assertIn("./scripts/directory-regenerate", justfile)

    def test_directory_regenerate_pushes_generated_homepage_config_and_restarts_homepage(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            shutil.copytree(REPO_ROOT / "inventory", root / "inventory")
            self._enable_service_directory_entry(root, group="Infrastructure")
            calls_log = root / "calls.log"
            self._write_fake_vm_shell(root, calls_log)

            result = self._run_directory_regenerate(root)

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(
                [
                    "vm-shell observability-vm -- sudo install -D -m 0644 "
                    "/dev/stdin /srv/services/service-directory/config/services.yaml",
                    "stdin: - Infrastructure:",
                    "vm-shell observability-vm -- sudo systemctl restart "
                    "fortress-service-directory-homepage.service",
                ],
                calls_log.read_text().splitlines(),
            )

    def test_directory_regenerate_reports_missing_service_directory_service(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            shutil.copytree(REPO_ROOT / "inventory", root / "inventory")
            (root / "inventory" / "services" / "service-directory.yaml").unlink()
            calls_log = root / "calls.log"
            self._write_fake_vm_shell(root, calls_log)

            result = self._run_directory_regenerate(root)

            self.assertEqual(result.returncode, 1)
            self.assertIn("service-directory Service is required", result.stderr)
            self.assertFalse(calls_log.exists())

    def test_directory_regenerate_reports_missing_backend_vm(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            shutil.copytree(REPO_ROOT / "inventory", root / "inventory")
            (root / "inventory" / "vms" / "observability-vm.yaml").unlink()
            calls_log = root / "calls.log"
            self._write_fake_vm_shell(root, calls_log)

            result = self._run_directory_regenerate(root)

            self.assertEqual(result.returncode, 1)
            self.assertIn(
                "service-directory Backend VM observability-vm is required",
                result.stderr,
            )
            self.assertFalse(calls_log.exists())

    def test_directory_regenerate_pushes_updated_generated_content_from_current_inventory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            shutil.copytree(REPO_ROOT / "inventory", root / "inventory")
            service_directory = self._enable_service_directory_entry(
                root,
                group="Infrastructure",
            )
            calls_log = root / "calls.log"
            self._write_fake_vm_shell(root, calls_log)

            first = self._run_directory_regenerate(root)
            service_directory.write_text(
                service_directory.read_text().replace(
                    "      group: Infrastructure\n",
                    "      group: Apps\n",
                )
            )
            second = self._run_directory_regenerate(root)

            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertEqual(second.returncode, 0, second.stderr)
            calls = calls_log.read_text()
            self.assertIn("stdin: - Infrastructure:\n", calls)
            self.assertIn("stdin: - Apps:\n", calls)
            self.assertEqual(
                2,
                calls.count(
                    "sudo install -D -m 0644 /dev/stdin "
                    "/srv/services/service-directory/config/services.yaml"
                ),
            )

    def _enable_service_directory_entry(self, root, group):
        self._disable_directory_entries(root)
        service_directory = root / "inventory" / "services" / "service-directory.yaml"
        service_directory.write_text(
            service_directory.read_text().replace(
                "    auth:\n      type: none\n",
                "    auth:\n"
                "      type: none\n"
                "    directory_entry:\n"
                "      enabled: true\n"
                "      label: Directory\n"
                f"      group: {group}\n",
            )
        )
        return service_directory

    def _disable_directory_entries(self, root):
        for inventory_path in (
            list((root / "inventory" / "services").glob("*.yaml"))
            + list((root / "inventory" / "hosts").glob("*.yaml"))
            + list((root / "inventory" / "nas").glob("*.yaml"))
        ):
            if inventory_path.name.endswith(".sops.yaml"):
                continue
            inventory_path.write_text(
                re.sub(
                    r"\n {4}directory_entry:\n(?: {6}.+\n)+",
                    "\n",
                    inventory_path.read_text(),
                )
            )

    def _run_directory_regenerate(self, root):
        env = {
            "FORTRESS_ROOT": str(root),
            "CALLS_LOG": str(root / "calls.log"),
        }
        return subprocess.run(
            [str(REPO_ROOT / "scripts" / "directory-regenerate")],
            cwd=REPO_ROOT,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

    def _write_fake_vm_shell(self, root, calls_log):
        scripts = root / "scripts"
        scripts.mkdir(exist_ok=True)
        fake = scripts / "vm-shell"
        fake.write_text(
            "#!/usr/bin/env bash\n"
            "printf 'vm-shell %s\\n' \"$*\" >> \"$CALLS_LOG\"\n"
            "stdin=$(cat)\n"
            "if [ -n \"$stdin\" ]; then\n"
            "  printf 'stdin: %s\\n' \"$(printf '%s' \"$stdin\" | sed -n '1p')\" >> \"$CALLS_LOG\"\n"
            "fi\n"
        )
        fake.chmod(fake.stat().st_mode | 0o100)
