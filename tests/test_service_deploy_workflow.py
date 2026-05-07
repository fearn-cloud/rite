import json
import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURES = REPO_ROOT / "tests" / "fixtures"


class ServiceDeployWorkflowTests(unittest.TestCase):
    def test_just_service_deploy_calls_workflow_script(self):
        justfile = (REPO_ROOT / "justfile").read_text()

        self.assertIn("service-deploy service:", justfile)
        self.assertIn("./scripts/service-deploy {{service}}", justfile)

    def test_service_deploy_passes_share_backed_subpaths_to_playbook(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            subprocess.run(["cp", "-R", str(FIXTURES / "inventory_valid") + "/.", str(root)], check=True)
            scripts_dir = root / "scripts"
            scripts_dir.mkdir(exist_ok=True)
            calls_log = root / "calls.log"
            self._fake_decrypt_keys(scripts_dir / "decrypt-keys", calls_log)
            (root / "inventory" / "vms" / "media01.sops.yaml").write_text("encrypted vm material\n")
            (root / "inventory" / "services" / "immich.yaml").write_text(
                "name: immich\n"
                "backend:\n"
                "  vm: media01\n"
                "  port: 2283\n"
                "deploy:\n"
                "  type: quadlet\n"
                "  containers:\n"
                "    - name: server\n"
                "      image: ghcr.io/immich-app/immich-server:v1.120.0\n"
                "      volumes:\n"
                "        - mount: media\n"
                "          source: photos\n"
                "          container: /photos\n"
                "          access: read_only\n"
            )
            env = os.environ.copy()
            env["FORTRESS_ROOT"] = str(root)
            env["CALLS_LOG"] = str(calls_log)

            result = subprocess.run(
                [str(REPO_ROOT / "scripts" / "service-deploy"), "immich"],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            command = calls_log.read_text()
            self.assertIn("ansible-playbook", command)
            self.assertIn("service-deploy.yml", command)
            extra_vars = json.loads(command.split("--extra-vars ", 1)[1])
            self.assertEqual("media01", extra_vars["deploy_service_backend_vm"])
            self.assertEqual(["/mnt/nas/media/photos"], extra_vars["fortress_share_backed_volume_subpaths"])

    def test_service_deploy_playbook_validates_subpaths_before_starting_containers(self):
        playbook = (REPO_ROOT / "ansible" / "playbooks" / "service-deploy.yml").read_text()

        self.assertLess(
            playbook.index("name: Validate Share-backed Volume subpaths"),
            playbook.index("name: Start Service containers"),
        )

    def _fake_decrypt_keys(self, path, calls_log):
        path.write_text(
            "#!/usr/bin/env bash\n"
            "shift 2\n"
            "printf '%s ' \"$@\" > \"$CALLS_LOG\"\n"
        )
        path.chmod(path.stat().st_mode | stat.S_IXUSR)


if __name__ == "__main__":
    unittest.main()
