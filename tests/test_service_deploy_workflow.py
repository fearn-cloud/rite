import json
import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

from fortress_inventory.service_runtime_intent import (
    BackendRuntimeFact,
    ContainerIdentityRuntimeFact,
    ServiceDataDirectoryRuntimeFact,
    ServiceNetworkIdentityRuntimeFact,
    ServiceOwnedVolumeRuntimeFact,
    ServiceRuntimeIntent,
    ServiceUnitOrderRuntimeFact,
    analyze_service_runtime_intent,
)
from fortress_inventory.model import load_inventory_tree
from fortress_services.deploy import (
    native_deploy_vars,
    native_environment_secret_keys,
    quadlet_deploy_vars,
    service_backend_vm_name,
    service_secret_keys,
    share_backed_volume_subpaths,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURES = REPO_ROOT / "tests" / "fixtures"


class ServiceDeployWorkflowTests(unittest.TestCase):
    def test_just_service_deploy_calls_workflow_script(self):
        justfile = (REPO_ROOT / "justfile").read_text()

        self.assertIn("service-deploy service:", justfile)
        self.assertIn("./scripts/service-deploy {{service}}", justfile)

    def test_declared_native_service_config_templates_exist(self):
        model = load_inventory_tree(REPO_ROOT)

        missing_templates = []
        for service_name, service in sorted(model.services.items()):
            deploy = service.get("deploy", {})
            if deploy.get("type") != "native":
                continue
            template_root = REPO_ROOT / "inventory" / "services" / f"{service_name}.native.d"
            for config_file in deploy.get("config_files", []) or []:
                template_path = template_root / config_file["template"]
                if not template_path.is_file():
                    missing_templates.append(str(template_path.relative_to(REPO_ROOT)))

        self.assertEqual([], missing_templates)

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
            self.assertNotIn("fortress_service_sops_file", extra_vars)
            self.assertEqual([], extra_vars["fortress_service_secrets"])

    def test_service_deploy_with_instrumentation_remains_scoped_to_named_service(self):
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
                "instrumentation:\n"
                "  telemetry_targets:\n"
                "    - name: metrics\n"
                "      type: prometheus_metrics\n"
                "      published_port: 2283\n"
                "deploy:\n"
                "  type: quadlet\n"
                "  containers:\n"
                "    - name: server\n"
                "      image: ghcr.io/immich-app/immich-server:v1.120.0\n"
                "      published_ports:\n"
                "        - container: 2283\n"
                "          host: 2283\n"
                "          bind: 0.0.0.0\n"
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
            self.assertNotIn("service-update", command)
            self.assertNotIn("observability", command)
            extra_vars = json.loads(command.split("--extra-vars ", 1)[1])
            self.assertEqual("immich", extra_vars["deploy_service"])
            self.assertEqual("media01", extra_vars["deploy_service_backend_vm"])

    def test_service_deploy_observability_reconciles_current_generated_view_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            subprocess.run(["cp", "-R", str(FIXTURES / "inventory_valid") + "/.", str(root)], check=True)
            scripts_dir = root / "scripts"
            scripts_dir.mkdir(exist_ok=True)
            calls_log = root / "calls.log"
            self._fake_decrypt_keys(scripts_dir / "decrypt-keys", calls_log)
            (root / "inventory" / "vms" / "observability-vm.yaml").write_text(
                "vmid: 102\n"
                "placement:\n"
                "  host: wintermute\n"
                "network:\n"
                "  interfaces:\n"
                "    - address: 10.0.10.102/24\n"
                "backup:\n"
                "  enabled: true\n"
            )
            (root / "inventory" / "vms" / "observability-vm.sops.yaml").write_text("encrypted vm material\n")
            (root / "inventory" / "services" / "observability.yaml").write_text(
                "name: observability\n"
                "backend:\n"
                "  vm: observability-vm\n"
                "  port: 3000\n"
                "deploy:\n"
                "  type: quadlet\n"
                "  containers:\n"
                "    - name: grafana\n"
                "      image: docker.io/grafana/grafana:12.0.0\n"
                "    - name: prometheus\n"
                "      image: docker.io/prom/prometheus:v3.4.0\n"
            )
            immich_path = root / "inventory" / "services" / "immich.yaml"
            immich_path.write_text(
                "name: immich\n"
                "backend:\n"
                "  vm: media01\n"
                "  port: 2283\n"
                "instrumentation:\n"
                "  telemetry_targets:\n"
                "    - name: metrics\n"
                "      type: prometheus_metrics\n"
                "      published_port: 2283\n"
                "  observability_views:\n"
                "    - profile: prometheus_generic\n"
                "deploy:\n"
                "  type: quadlet\n"
                "  containers:\n"
                "    - name: server\n"
                "      image: ghcr.io/immich-app/immich-server:v1.120.0\n"
                "      published_ports:\n"
                "        - container: 2283\n"
                "          host: 2283\n"
                "          bind: 0.0.0.0\n"
            )
            env = os.environ.copy()
            env["FORTRESS_ROOT"] = str(root)
            env["CALLS_LOG"] = str(calls_log)

            result = subprocess.run(
                [str(REPO_ROOT / "scripts" / "service-deploy"), "observability"],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            extra_vars = json.loads(calls_log.read_text().split("--extra-vars ", 1)[1])
            self.assertEqual(
                ["/srv/services/observability/grafana-dashboards/generated"],
                extra_vars["fortress_service_data_reconcile_directories"],
            )
            self.assertIn(
                "/srv/services/observability/grafana-dashboards/generated/service-immich-prometheus_generic.json",
                [file["path"] for file in extra_vars["fortress_service_data_files"]],
            )

            immich_path.write_text(immich_path.read_text().replace("  observability_views:\n    - profile: prometheus_generic\n", ""))
            (root / "inventory" / "vms" / "media01.yaml").write_text(
                (root / "inventory" / "vms" / "media01.yaml").read_text()
                + "instrumentation:\n"
                + "  enabled: false\n"
            )

            result = subprocess.run(
                [str(REPO_ROOT / "scripts" / "service-deploy"), "observability"],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            extra_vars = json.loads(calls_log.read_text().split("--extra-vars ", 1)[1])
            generated_dashboard_paths = [
                file["path"]
                for file in extra_vars["fortress_service_data_files"]
                if file["path"].startswith("/srv/services/observability/grafana-dashboards/generated/")
            ]
            self.assertEqual(
                ["/srv/services/observability/grafana-dashboards/generated/vm-observability-vm-vm_baseline.json"],
                generated_dashboard_paths,
            )
            self.assertEqual(
                ["/srv/services/observability/grafana-dashboards/generated"],
                extra_vars["fortress_service_data_reconcile_directories"],
            )

    def test_service_deploy_requires_service_sibling_sops_file_only_when_service_secrets_are_declared(self):
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
                "      secrets:\n"
                "        - secret: secrets.db_password\n"
                "          env: IMMICH_DB_PASSWORD_FILE\n"
            )
            env = os.environ.copy()
            env["FORTRESS_ROOT"] = str(root)
            env["CALLS_LOG"] = str(calls_log)

            missing = subprocess.run(
                [str(REPO_ROOT / "scripts" / "service-deploy"), "immich"],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            self.assertEqual(missing.returncode, 1)
            self.assertIn("Service Sibling SOPS File is required", missing.stderr)

            service_sops = root / "inventory" / "services" / "immich.sops.yaml"
            service_sops.write_text("encrypted service secret material\n")
            self._fake_sops(
                root / "bin" / "sops",
                calls_log,
                "secrets:\n"
                "  db_password:\n"
                "    created: 2026-05-12T00:00:00Z\n"
                "    version: 1\n"
                "    value: structured-db-password\n",
            )
            env["PATH"] = f"{root / 'bin'}:{env['PATH']}"

            result = subprocess.run(
                [str(REPO_ROOT / "scripts" / "service-deploy"), "immich"],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            extra_vars = json.loads(calls_log.read_text().split("--extra-vars ", 1)[1])
            self.assertEqual(str(service_sops), extra_vars["fortress_service_sops_file"])
            self.assertEqual(
                [
                    {
                        "podman_name": "fortress_immich_db_password",
                        "sops_extract": '["secrets"]["db_password"]["value"]',
                    }
                ],
                extra_vars["fortress_service_secrets"],
            )

    def test_service_deploy_requires_service_sibling_sops_file_for_native_environment_secrets(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            subprocess.run(["cp", "-R", str(FIXTURES / "inventory_valid") + "/.", str(root)], check=True)
            scripts_dir = root / "scripts"
            scripts_dir.mkdir(exist_ok=True)
            calls_log = root / "calls.log"
            self._fake_decrypt_keys(scripts_dir / "decrypt-keys", calls_log)
            (root / "inventory" / "vms" / "media01.sops.yaml").write_text("encrypted vm material\n")
            template_dir = root / "inventory" / "services" / "caddy.native.d"
            template_dir.mkdir()
            (template_dir / "caddy.env.j2").write_text(
                "CLOUDFLARE_API_TOKEN={{ fortress_native_environment_secrets.CLOUDFLARE_API_TOKEN }}\n"
            )
            (root / "inventory" / "services" / "caddy.yaml").write_text(
                "name: caddy\n"
                "backend:\n"
                "  vm: media01\n"
                "  port: 80\n"
                "deploy:\n"
                "  type: native\n"
                "  package: caddy\n"
                "  service_name: caddy\n"
                "  environment_secrets:\n"
                "    - secret: secrets.cloudflare_api_token\n"
                "      env: CLOUDFLARE_API_TOKEN\n"
                "  config_files:\n"
                "    - template: caddy.env.j2\n"
                "      dest: /etc/default/caddy\n"
                "      mode: '0600'\n"
                "      restart_on_change: true\n"
            )
            env = os.environ.copy()
            env["FORTRESS_ROOT"] = str(root)
            env["CALLS_LOG"] = str(calls_log)

            missing = subprocess.run(
                [str(REPO_ROOT / "scripts" / "service-deploy"), "caddy"],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            self.assertEqual(missing.returncode, 1)
            self.assertIn("Native Service Environment Secrets", missing.stderr)
            self.assertNotIn("Service Secrets.", missing.stderr)
            self.assertFalse(calls_log.exists())

    def test_service_deploy_preflights_native_environment_secrets_and_passes_extract_specs_to_playbook(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            subprocess.run(["cp", "-R", str(FIXTURES / "inventory_valid") + "/.", str(root)], check=True)
            scripts_dir = root / "scripts"
            scripts_dir.mkdir(exist_ok=True)
            calls_log = root / "calls.log"
            self._fake_decrypt_keys(scripts_dir / "decrypt-keys", calls_log)
            self._fake_sops(
                root / "bin" / "sops",
                calls_log,
                "secrets:\n"
                "  cloudflare_api_token:\n"
                "    created: 2026-05-14T00:00:00Z\n"
                "    version: 1\n"
                "    value: do-not-pass-this-token-in-extra-vars\n",
            )
            (root / "inventory" / "vms" / "media01.sops.yaml").write_text("encrypted vm material\n")
            (root / "inventory" / "services" / "caddy.sops.yaml").write_text("encrypted service secret material\n")
            template_dir = root / "inventory" / "services" / "caddy.native.d"
            template_dir.mkdir()
            (template_dir / "caddy.env.j2").write_text(
                "CLOUDFLARE_API_TOKEN={{ fortress_native_environment_secrets.CLOUDFLARE_API_TOKEN }}\n"
            )
            (root / "inventory" / "services" / "caddy.yaml").write_text(
                "name: caddy\n"
                "backend:\n"
                "  vm: media01\n"
                "  port: 80\n"
                "deploy:\n"
                "  type: native\n"
                "  package: caddy\n"
                "  service_name: caddy\n"
                "  environment_secrets:\n"
                "    - secret: secrets.cloudflare_api_token\n"
                "      env: CLOUDFLARE_API_TOKEN\n"
                "  config_files:\n"
                "    - template: caddy.env.j2\n"
                "      dest: /etc/default/caddy\n"
                "      mode: '0600'\n"
                "      restart_on_change: true\n"
            )
            env = os.environ.copy()
            env["FORTRESS_ROOT"] = str(root)
            env["CALLS_LOG"] = str(calls_log)
            env["PATH"] = f"{root / 'bin'}:{env['PATH']}"

            result = subprocess.run(
                [str(REPO_ROOT / "scripts" / "service-deploy"), "caddy"],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            command = calls_log.read_text()
            self.assertNotIn("do-not-pass-this-token-in-extra-vars", command)
            extra_vars = json.loads(command.split("--extra-vars ", 1)[1])
            self.assertEqual(str(root / "inventory" / "services" / "caddy.sops.yaml"), extra_vars["fortress_service_sops_file"])
            self.assertEqual(
                [
                    {
                        "env": "CLOUDFLARE_API_TOKEN",
                        "sops_extract": '["secrets"]["cloudflare_api_token"]["value"]',
                    }
                ],
                extra_vars["fortress_native_environment_secret_specs"],
            )

    def test_service_deploy_rejects_malformed_native_environment_secret_before_remote_playbook(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            subprocess.run(["cp", "-R", str(FIXTURES / "inventory_valid") + "/.", str(root)], check=True)
            scripts_dir = root / "scripts"
            scripts_dir.mkdir(exist_ok=True)
            calls_log = root / "calls.log"
            self._fake_decrypt_keys(scripts_dir / "decrypt-keys", calls_log)
            self._fake_sops(
                root / "bin" / "sops",
                calls_log,
                "secrets:\n"
                "  cloudflare_api_token: do-not-print-this-token\n",
            )
            (root / "inventory" / "vms" / "media01.sops.yaml").write_text("encrypted vm material\n")
            (root / "inventory" / "services" / "caddy.sops.yaml").write_text("encrypted service secret material\n")
            (root / "inventory" / "services" / "caddy.yaml").write_text(
                "name: caddy\n"
                "backend:\n"
                "  vm: media01\n"
                "  port: 80\n"
                "deploy:\n"
                "  type: native\n"
                "  package: caddy\n"
                "  service_name: caddy\n"
                "  environment_secrets:\n"
                "    - secret: secrets.cloudflare_api_token\n"
                "      env: CLOUDFLARE_API_TOKEN\n"
                "  config_files:\n"
                "    - template: caddy.env.j2\n"
                "      dest: /etc/default/caddy\n"
                "      mode: '0600'\n"
                "      restart_on_change: true\n"
            )
            env = os.environ.copy()
            env["FORTRESS_ROOT"] = str(root)
            env["CALLS_LOG"] = str(calls_log)
            env["PATH"] = f"{root / 'bin'}:{env['PATH']}"

            result = subprocess.run(
                [str(REPO_ROOT / "scripts" / "service-deploy"), "caddy"],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            self.assertEqual(result.returncode, 1)
            self.assertIn("Native Service Environment Secret secrets.cloudflare_api_token", result.stderr)
            self.assertIn("structured entry", result.stderr)
            self.assertNotIn("do-not-print-this-token", result.stderr)
            self.assertNotIn("ansible-playbook", calls_log.read_text())

    def test_service_deploy_rejects_scalar_legacy_service_secret_before_remote_playbook(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            subprocess.run(["cp", "-R", str(FIXTURES / "inventory_valid") + "/.", str(root)], check=True)
            scripts_dir = root / "scripts"
            scripts_dir.mkdir(exist_ok=True)
            calls_log = root / "calls.log"
            self._fake_decrypt_keys(scripts_dir / "decrypt-keys", calls_log)
            self._fake_sops(
                root / "bin" / "sops",
                calls_log,
                "secrets:\n"
                "  db_password: do-not-print-this-legacy-secret\n",
            )
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
                "      secrets:\n"
                "        - secret: secrets.db_password\n"
                "          env: IMMICH_DB_PASSWORD_FILE\n"
            )
            (root / "inventory" / "services" / "immich.sops.yaml").write_text("encrypted service secret material\n")
            env = os.environ.copy()
            env["FORTRESS_ROOT"] = str(root)
            env["CALLS_LOG"] = str(calls_log)
            env["PATH"] = f"{root / 'bin'}:{env['PATH']}"

            result = subprocess.run(
                [str(REPO_ROOT / "scripts" / "service-deploy"), "immich"],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            self.assertEqual(result.returncode, 1)
            self.assertIn("Service Secret secrets.db_password", result.stderr)
            self.assertIn("structured entry", result.stderr)
            self.assertNotIn("do-not-print-this-legacy-secret", result.stderr)
            self.assertNotIn("ansible-playbook", calls_log.read_text())

    def test_service_deploy_preflight_reports_missing_structured_service_secret_fields(self):
        cases = {
            "missing_entry": (
                "secrets:\n"
                "  other_password:\n"
                "    created: 2026-05-12T00:00:00Z\n"
                "    version: 1\n"
                "    value: do-not-print-other\n",
                "missing Service Secret secrets.db_password",
            ),
            "missing_created": (
                "secrets:\n"
                "  db_password:\n"
                "    version: 1\n"
                "    value: do-not-print-password\n",
                "missing required field(s): created",
            ),
            "missing_version": (
                "secrets:\n"
                "  db_password:\n"
                "    created: 2026-05-12T00:00:00Z\n"
                "    value: do-not-print-password\n",
                "missing required field(s): version",
            ),
            "missing_value": (
                "secrets:\n"
                "  db_password:\n"
                "    created: 2026-05-12T00:00:00Z\n"
                "    version: 1\n",
                "missing required field(s): value",
            ),
        }
        for scenario, (decrypted, expected_error) in cases.items():
            with self.subTest(scenario=scenario), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                subprocess.run(["cp", "-R", str(FIXTURES / "inventory_valid") + "/.", str(root)], check=True)
                scripts_dir = root / "scripts"
                scripts_dir.mkdir(exist_ok=True)
                calls_log = root / "calls.log"
                self._fake_decrypt_keys(scripts_dir / "decrypt-keys", calls_log)
                self._fake_sops(root / "bin" / "sops", calls_log, decrypted)
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
                    "      secrets:\n"
                    "        - secret: secrets.db_password\n"
                    "          env: IMMICH_DB_PASSWORD_FILE\n"
                )
                (root / "inventory" / "services" / "immich.sops.yaml").write_text("encrypted service secret material\n")
                env = os.environ.copy()
                env["FORTRESS_ROOT"] = str(root)
                env["CALLS_LOG"] = str(calls_log)
                env["PATH"] = f"{root / 'bin'}:{env['PATH']}"

                result = subprocess.run(
                    [str(REPO_ROOT / "scripts" / "service-deploy"), "immich"],
                    cwd=REPO_ROOT,
                    env=env,
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )

                self.assertEqual(result.returncode, 1)
                self.assertIn(expected_error, result.stderr)
                self.assertNotIn("do-not-print", result.stderr)
                self.assertNotIn("ansible-playbook", calls_log.read_text())

    def test_service_deploy_playbook_validates_subpaths_before_starting_containers(self):
        playbook = (REPO_ROOT / "ansible" / "playbooks" / "service-deploy.yml").read_text()

        self.assertIn("become: true", playbook)
        self.assertLess(
            playbook.index("name: Validate Share-backed Volume subpaths"),
            playbook.index("name: Start Service containers"),
        )

    def test_service_deploy_playbook_installs_service_secrets_before_starting_containers(self):
        playbook = (REPO_ROOT / "ansible" / "playbooks" / "service-deploy.yml").read_text()

        self.assertLess(
            playbook.index("name: Ensure Podman is installed for Quadlet Services"),
            playbook.index("name: Install Service Secrets as Podman secrets"),
        )
        self.assertLess(
            playbook.index("name: Remove Service Secrets before replacement"),
            playbook.index("name: Install Service Secrets as Podman secrets"),
        )
        self.assertLess(
            playbook.index("name: Install Service Secrets as Podman secrets"),
            playbook.index("name: Start Service containers"),
        )
        self.assertIn("no_log: true", playbook)
        self.assertIn("podman secret rm", playbook)
        self.assertIn("podman secret create", playbook)
        self.assertIn("stdin_add_newline: false", playbook)

    def test_service_deploy_playbook_creates_service_data_files_before_starting_containers(self):
        playbook = (REPO_ROOT / "ansible" / "playbooks" / "service-deploy.yml").read_text()

        self.assertLess(
            playbook.index("name: Ensure Service Data Directories exist"),
            playbook.index("name: Ensure Service Data Files exist"),
        )
        self.assertLess(
            playbook.index("name: Ensure Service Data Files exist"),
            playbook.index("name: Start Service containers in dependency order"),
        )
        self.assertIn("force: \"{{ item.force | default(false) }}\"", playbook)
        self.assertIn("fortress_service_data_files", playbook)

    def test_service_deploy_playbook_reconciles_generated_service_data_before_copying_current_files(self):
        playbook = (REPO_ROOT / "ansible" / "playbooks" / "service-deploy.yml").read_text()

        self.assertLess(
            playbook.index("name: Find stale generated Service Data Files"),
            playbook.index("name: Ensure Service Data Files exist"),
        )
        self.assertLess(
            playbook.index("name: Prune stale generated Service Data Files"),
            playbook.index("name: Ensure Service Data Files exist"),
        )
        self.assertIn("fortress_service_data_reconcile_directories", playbook)
        self.assertIn("state: absent", playbook)

    def test_observability_deploy_vars_create_parent_directories_for_generated_nested_files(self):
        model = load_inventory_tree(REPO_ROOT)

        deploy_vars = quadlet_deploy_vars(
            model.services["observability"],
            model.vms["observability-vm"],
            inventory_root=REPO_ROOT / "inventory",
            model=model,
        )

        directories = {
            directory["path"]: directory
            for directory in deploy_vars["fortress_service_data_directories"]
        }
        self.assertIn(
            "/srv/services/observability/grafana-provisioning/dashboards",
            directories,
        )
        self.assertEqual(
            {
                "path": "/srv/services/observability/grafana-provisioning/dashboards",
                "uid": 1000,
                "gid": 1000,
            },
            directories["/srv/services/observability/grafana-provisioning/dashboards"],
        )

    def test_service_deploy_passes_rendered_artifacts_and_restart_order_to_playbook(self):
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
                "service_group: media\n"
                "service_network: media\n"
                "backend:\n"
                "  vm: media01\n"
                "  port: 2283\n"
                "deploy:\n"
                "  type: quadlet\n"
                "  containers:\n"
                "    - name: server\n"
                "      image: ghcr.io/immich-app/immich-server:v1.120.0\n"
                "      depends_on: [postgres]\n"
                "    - name: postgres\n"
                "      image: postgres:16\n"
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
            extra_vars = json.loads(calls_log.read_text().split("--extra-vars ", 1)[1])
            self.assertEqual(
                ["fortress-network-media.network", "fortress-immich-server.container", "fortress-immich-postgres.container"],
                [artifact["filename"] for artifact in extra_vars["fortress_quadlet_artifacts"]],
            )
            self.assertEqual(
                ["fortress-network-media-network.service"],
                extra_vars["fortress_service_network_units"],
            )
            self.assertEqual(
                ["fortress-immich-postgres.service", "fortress-immich-server.service"],
                extra_vars["fortress_service_start_units"],
            )
            self.assertEqual(
                ["ghcr.io/immich-app/immich-server:v1.120.0", "postgres:16"],
                extra_vars["fortress_service_container_images"],
            )
            self.assertEqual(
                ["fortress-immich-server.service", "fortress-immich-postgres.service"],
                extra_vars["fortress_service_stop_units"],
            )
            self.assertEqual(
                ["/etc/containers/systemd/fortress-immich-server.container", "/etc/containers/systemd/fortress-immich-postgres.container"],
                extra_vars["fortress_owned_quadlet_prune_paths"],
            )
            self.assertEqual("fortress_immich_", extra_vars["fortress_service_secret_prefix"])

    def test_quadlet_deploy_vars_consumes_runtime_intent_identity_facts(self):
        service = {
            "name": "raw-service",
            "backend": {"vm": "media01", "port": 8080},
            "deploy": {
                "type": "quadlet",
                "containers": [
                    {
                        "name": "web",
                        "image": "example/web:1",
                        "depends_on": ["db"],
                        "volumes": [
                            {
                                "service_path": "raw-data",
                                "container": "/data",
                                "access": "read_write",
                            }
                        ],
                    },
                    {
                        "name": "db",
                        "image": "postgres:16",
                    },
                ],
            },
        }
        runtime_intent = ServiceRuntimeIntent(
            backends=(),
            published_ports=(),
            telemetry_targets=(),
            service_secrets=(),
            service_owned_volumes=(
                ServiceOwnedVolumeRuntimeFact(
                    service_name="raw-service",
                    vm_name="media01",
                    container_name="web",
                    container_index=0,
                    volume_index=0,
                    service_path="raw-data",
                    vm_path="/srv/runtime-intent/raw-service/intent-data",
                    container_path="/data",
                    access_mode="rw",
                ),
            ),
            service_data_directories=(
                ServiceDataDirectoryRuntimeFact(
                    service_name="raw-service",
                    vm_name="media01",
                    path="/srv/runtime-intent/raw-service/intent-data",
                    uid=1234,
                    gid=1235,
                ),
            ),
            share_backed_volumes=(),
            native_environment_secrets=(),
            service_network_identities=(
                ServiceNetworkIdentityRuntimeFact(
                    service_name="raw-service",
                    vm_name="media01",
                    declared_service_network=None,
                    podman_name="intent-network",
                    isolated=True,
                ),
            ),
            container_identities=(
                ContainerIdentityRuntimeFact(
                    service_name="raw-service",
                    vm_name="media01",
                    container_name="web",
                    container_index=0,
                    container_alias="intent-web",
                    podman_name="intent-web-container",
                    systemd_unit_name="intent-web-container.service",
                    service_network_podman_name="intent-network",
                ),
                ContainerIdentityRuntimeFact(
                    service_name="raw-service",
                    vm_name="media01",
                    container_name="db",
                    container_index=1,
                    container_alias="intent-db",
                    podman_name="intent-db-container",
                    systemd_unit_name="intent-db-container.service",
                    service_network_podman_name="intent-network",
                ),
            ),
            service_unit_orders=(
                ServiceUnitOrderRuntimeFact(
                    service_name="raw-service",
                    vm_name="media01",
                    start_units=("intent-db-container.service", "intent-web-container.service"),
                    stop_units=("intent-web-container.service", "intent-db-container.service"),
                ),
            ),
            diagnostics=(),
        )

        deploy_vars = quadlet_deploy_vars(
            service,
            {},
            inventory_root=REPO_ROOT / "inventory",
            runtime_intent=runtime_intent,
        )

        self.assertEqual(
            ["intent-network.network", "intent-web-container.container", "intent-db-container.container"],
            [artifact["filename"] for artifact in deploy_vars["fortress_quadlet_artifacts"]],
        )
        self.assertEqual(
            [{"path": "/srv/runtime-intent/raw-service/intent-data", "uid": 1234, "gid": 1235}],
            deploy_vars["fortress_service_data_directories"],
        )
        self.assertEqual(["intent-network-network.service"], deploy_vars["fortress_service_network_units"])
        self.assertEqual(
            ["intent-db-container.service", "intent-web-container.service"],
            deploy_vars["fortress_service_start_units"],
        )
        self.assertEqual(
            ["intent-web-container.service", "intent-db-container.service"],
            deploy_vars["fortress_service_stop_units"],
        )
        self.assertEqual(
            [
                "/etc/containers/systemd/intent-web-container.container",
                "/etc/containers/systemd/intent-db-container.container",
            ],
            deploy_vars["fortress_owned_quadlet_prune_paths"],
        )

    def test_service_backend_vm_name_prefers_runtime_intent_fact(self):
        service = {"name": "raw-service", "backend": {"vm": "raw-vm"}}
        runtime_intent = ServiceRuntimeIntent(
            backends=(
                BackendRuntimeFact(
                    service_name="raw-service",
                    vm_name="intent-vm",
                    port=8080,
                ),
            ),
            published_ports=(),
            telemetry_targets=(),
            service_secrets=(),
            service_owned_volumes=(),
            service_data_directories=(),
            share_backed_volumes=(),
            native_environment_secrets=(),
            diagnostics=(),
        )

        self.assertEqual("intent-vm", service_backend_vm_name(service, runtime_intent=runtime_intent))

    def test_service_backend_vm_name_requires_service_runtime_intent(self):
        service = {"name": "raw-service", "backend": {"vm": "raw-vm"}}

        with self.assertRaisesRegex(
            ValueError,
            "Service Runtime Intent is required to resolve Service Backend VM for Service raw-service",
        ):
            service_backend_vm_name(service)

    def test_deploy_runtime_fact_helpers_require_service_runtime_intent(self):
        service = {"name": "paperless", "deploy": {"type": "quadlet", "containers": []}}

        cases = [
            (
                lambda: share_backed_volume_subpaths(service, {}),
                "build Share-backed Volume deploy subpaths",
            ),
            (
                lambda: service_secret_keys(service),
                "build Service Secret deploy facts",
            ),
            (
                lambda: native_environment_secret_keys(service),
                "build Native Service Environment Secret deploy facts",
            ),
            (
                lambda: quadlet_deploy_vars(service, {}),
                "build Quadlet deploy variables",
            ),
        ]
        for call, action in cases:
            with self.subTest(action=action), self.assertRaisesRegex(
                ValueError,
                f"Service Runtime Intent is required to {action} for Service paperless",
            ):
                call()

    def test_service_deploy_renders_pihole_dnsmasq_d_compatibility_for_ingress_dns_targets(self):
        model = load_inventory_tree(REPO_ROOT)
        cases = [
            ("dns-primary", "dns-primary-vm"),
            ("dns-secondary", "dns-secondary-vm"),
        ]

        for service_name, vm_name in cases:
            with self.subTest(service=service_name):
                service = model.services[service_name]
                vm = model.vms[vm_name]

                deploy_vars = quadlet_deploy_vars(
                    service,
                    vm,
                    inventory_root=REPO_ROOT / "inventory",
                    model=model,
                )
                pihole_artifact = next(
                    artifact
                    for artifact in deploy_vars["fortress_quadlet_artifacts"]
                    if artifact["filename"] == f"fortress-{service_name}-pihole.container"
                )

                self.assertIn("Environment=FTLCONF_misc_etc_dnsmasq_d=true\n", pihole_artifact["content"])
                self.assertIn("Environment=FTLCONF_dns_cache_optimizer=-1\n", pihole_artifact["content"])
                self.assertIn(
                    f"Volume=/srv/services/{service_name}/pihole/etc-dnsmasq.d:/etc/dnsmasq.d:rw\n",
                    pihole_artifact["content"],
                )
                self.assertEqual(
                    [
                        {
                            "path": f"/srv/services/{service_name}/unbound/a-records.conf",
                            "content": "",
                            "mode": "0644",
                            "uid": 1000,
                            "gid": 1000,
                        },
                        {
                            "path": f"/srv/services/{service_name}/unbound/srv-records.conf",
                            "content": "",
                            "mode": "0644",
                            "uid": 1000,
                            "gid": 1000,
                        },
                        {
                            "path": f"/srv/services/{service_name}/unbound/forward-records.conf",
                            "content": "",
                            "mode": "0644",
                            "uid": 1000,
                            "gid": 1000,
                        },
                    ],
                    deploy_vars["fortress_service_data_files"],
                )

    def test_service_deploy_exposes_quadlet_host_groups_for_device_access(self):
        model = load_inventory_tree(REPO_ROOT)
        service = model.services["jellyfin"]
        vm = model.vms["media-vm"]

        deploy_vars = quadlet_deploy_vars(
            service,
            vm,
            inventory_root=REPO_ROOT / "inventory",
            model=model,
        )
        jellyfin_artifact = next(
            artifact
            for artifact in deploy_vars["fortress_quadlet_artifacts"]
            if artifact["filename"] == "fortress-jellyfin-jellyfin.container"
        )

        self.assertEqual(["render"], deploy_vars["fortress_quadlet_host_groups"])
        self.assertIn("AddDevice=/dev/dri\n", jellyfin_artifact["content"])
        self.assertIn("GroupAdd=__FORTRESS_HOST_GROUP_GID_render__\n", jellyfin_artifact["content"])

    def test_internal_ingress_service_deploy_scaffolding_imports_generated_routes(self):
        caddyfile = (REPO_ROOT / "inventory" / "services" / "internal-ingress.native.d" / "Caddyfile.j2").read_text()

        self.assertIn("admin {$CADDY_ADMIN}", caddyfile)
        self.assertIn("import /etc/caddy/fortress/generated-routes.caddy", caddyfile)
        self.assertNotIn("git.fearn.cloud {", caddyfile)
        self.assertNotIn("reverse_proxy 10.", caddyfile)

    def test_internal_ingress_declares_cloudflare_native_environment_secret_for_caddy(self):
        model = load_inventory_tree(REPO_ROOT)
        service = model.services["internal-ingress"]
        caddy_env = (REPO_ROOT / "inventory" / "services" / "internal-ingress.native.d" / "caddy.env.j2").read_text()
        service_sops = (REPO_ROOT / "inventory" / "services" / "internal-ingress.sops.yaml").read_text()

        self.assertEqual(
            [
                {
                    "secret": "secrets.cloudflare_api_token",
                    "env": "CLOUDFLARE_API_TOKEN",
                }
            ],
            service["deploy"]["environment_secrets"],
        )
        self.assertIn(
            {
                "template": "caddy.env.j2",
                "dest": "/etc/default/caddy",
                "mode": "0600",
                "restart_on_change": True,
            },
            service["deploy"]["config_files"],
        )
        self.assertIn(
            {
                "template": "caddy.service.d/fortress-env.conf.j2",
                "dest": "/etc/systemd/system/caddy.service.d/fortress-env.conf",
                "mode": "0644",
                "restart_on_change": True,
            },
            service["deploy"]["config_files"],
        )
        self.assertIn(
            "CLOUDFLARE_API_TOKEN={{ fortress_native_environment_secrets.CLOUDFLARE_API_TOKEN }}",
            caddy_env,
        )
        self.assertIn("cloudflare_api_token:", service_sops)
        self.assertIn("created:", service_sops)
        self.assertIn("version:", service_sops)
        self.assertIn("value:", service_sops)

    def test_internal_ingress_declares_cloudflare_caddy_module_for_service_deploy(self):
        model = load_inventory_tree(REPO_ROOT)
        service = model.services["internal-ingress"]

        deploy_vars = native_deploy_vars(
            service,
            model.globals,
            inventory_root=REPO_ROOT / "inventory",
            runtime_intent=analyze_service_runtime_intent(model),
        )

        self.assertEqual(
            [
                {
                    "package": "github.com/caddy-dns/cloudflare",
                    "module": "dns.providers.cloudflare",
                }
            ],
            service["deploy"]["caddy_modules"],
        )
        self.assertEqual(service["deploy"]["caddy_modules"], deploy_vars["fortress_native_caddy_modules"])

    def test_service_deploy_passes_native_package_repo_unit_and_config_files_to_playbook(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            subprocess.run(["cp", "-R", str(FIXTURES / "inventory_valid") + "/.", str(root)], check=True)
            scripts_dir = root / "scripts"
            scripts_dir.mkdir(exist_ok=True)
            calls_log = root / "calls.log"
            self._fake_decrypt_keys(scripts_dir / "decrypt-keys", calls_log)
            (root / "inventory" / "group_vars" / "all.yaml").write_text(
                "domain: fearn.cloud\n"
                "nas:\n"
                "  default_options:\n"
                "    - nfsvers=4.2\n"
                "apt_repos:\n"
                "  caddy_official:\n"
                "    url: https://dl.cloudsmith.io/public/caddy/stable/deb/debian\n"
                "    disabled_sources:\n"
                "      - /etc/apt/sources.list.d/caddy-stale.list\n"
            )
            (root / "inventory" / "vms" / "media01.sops.yaml").write_text("encrypted vm material\n")
            template_dir = root / "inventory" / "services" / "caddy.native.d"
            template_dir.mkdir()
            (template_dir / "Caddyfile.j2").write_text(":80 { respond \"ok\" }\n")
            (template_dir / "caddy.env.j2").write_text("CADDY_ADMIN=localhost:2019\n")
            (root / "inventory" / "services" / "caddy.yaml").write_text(
                "name: caddy\n"
                "backend:\n"
                "  vm: media01\n"
                "  port: 80\n"
                "deploy:\n"
                "  type: native\n"
                "  package: caddy\n"
                "  apt_repo: caddy_official\n"
                "  service_name: caddy\n"
                "  config_files:\n"
                "    - template: Caddyfile.j2\n"
                "      dest: /etc/caddy/Caddyfile\n"
                "      mode: '0644'\n"
                "      reload_on_change: true\n"
                "    - template: caddy.env.j2\n"
                "      dest: /etc/default/caddy\n"
                "      mode: '0600'\n"
                "      restart_on_change: true\n"
            )
            env = os.environ.copy()
            env["FORTRESS_ROOT"] = str(root)
            env["CALLS_LOG"] = str(calls_log)

            result = subprocess.run(
                [str(REPO_ROOT / "scripts" / "service-deploy"), "caddy"],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            extra_vars = json.loads(calls_log.read_text().split("--extra-vars ", 1)[1])
            self.assertEqual("native", extra_vars["fortress_service_deploy_type"])
            self.assertEqual("caddy", extra_vars["fortress_native_package"])
            self.assertEqual("caddy", extra_vars["fortress_native_systemd_unit"])
            self.assertEqual(
                {
                    "name": "caddy_official",
                    "url": "https://dl.cloudsmith.io/public/caddy/stable/deb/debian",
                    "disabled_sources": ["/etc/apt/sources.list.d/caddy-stale.list"],
                },
                extra_vars["fortress_native_apt_repo"],
            )
            self.assertEqual(
                [
                    {
                        "src": str(template_dir / "Caddyfile.j2"),
                        "dest": "/etc/caddy/Caddyfile",
                        "mode": "0644",
                        "action": "reload",
                    },
                    {
                        "src": str(template_dir / "caddy.env.j2"),
                        "dest": "/etc/default/caddy",
                        "mode": "0600",
                        "action": "restart",
                    },
                ],
                extra_vars["fortress_native_config_files"],
            )
            self.assertNotIn("fortress_quadlet_artifacts", extra_vars)

    def test_service_deploy_playbook_prunes_restarts_and_reports_start_failures(self):
        playbook = (REPO_ROOT / "ansible" / "playbooks" / "service-deploy.yml").read_text()
        start_tasks = (REPO_ROOT / "ansible" / "tasks" / "service-start-unit.yml").read_text()
        deploy_workflow = playbook + "\n" + start_tasks

        self.assertIn("name: Find obsolete fortress-rendered container Quadlets for selected Service", playbook)
        self.assertIn("patterns: \"fortress-{{ deploy_service }}-*.container\"", playbook)
        self.assertIn("fortress_owned_quadlet_prune_paths", playbook)
        self.assertIn("name: List fortress-owned Podman secrets for selected Service", playbook)
        self.assertIn("{{ fortress_service_secret_prefix }}", playbook)
        self.assertLess(
            playbook.index("name: Stop Service containers in reverse dependency order"),
            playbook.index("name: Start Service networks before containers"),
        )
        self.assertLess(
            playbook.index("name: Start Service networks before containers"),
            playbook.index("name: Start Service containers in dependency order"),
        )
        self.assertLess(
            playbook.index("name: Pull Service container images before systemd starts units"),
            playbook.index("name: Stop Service containers in reverse dependency order"),
        )
        self.assertLess(
            playbook.index("name: Pull Service container images before systemd starts units"),
            playbook.index("name: Start Service containers in dependency order"),
        )
        self.assertLess(
            playbook.index("name: Enable Service Quadlet units for boot"),
            playbook.index("name: Start Service networks before containers"),
        )
        self.assertIn("enabled: true", playbook)
        self.assertIn("podman image pull {{ item }}", playbook)
        self.assertIn("systemctl start {{ item }}", deploy_workflow)
        self.assertIn("name: Wait briefly for Service container early exits", deploy_workflow)
        self.assertIn("systemctl is-active --quiet {{ item }}", deploy_workflow)
        self.assertIn("until: fortress_service_unit_active.rc == 0", deploy_workflow)
        self.assertIn("Failed to start or keep {{ item }} active", deploy_workflow)
        self.assertIn("journalctl -u {{ item }}", deploy_workflow)
        self.assertNotIn("/srv/services/{{ deploy_service }}", deploy_workflow)

    def test_service_deploy_playbook_installs_native_packages_templates_configs_and_reloads_or_restarts(self):
        playbook = (REPO_ROOT / "ansible" / "playbooks" / "service-deploy.yml").read_text()

        self.assertIn("name: Configure Native Service apt repository", playbook)
        self.assertIn("name: Disable conflicting Native Service apt sources", playbook)
        self.assertIn("fortress_native_apt_repo.disabled_sources | default([])", playbook)
        self.assertIn("name: Ensure Native Service apt repository tooling is installed", playbook)
        self.assertIn("name: gnupg", playbook)
        self.assertIn("fortress_native_apt_repo", playbook)
        self.assertIn("name: Install Native Service package", playbook)
        self.assertIn("name: Render Native Service config files", playbook)
        self.assertIn("name: Ensure Native Service config parent directories exist", playbook)
        self.assertIn("loop: \"{{ fortress_native_config_files | default([]) }}\"", playbook)
        self.assertIn("src: \"{{ item.src }}\"", playbook)
        self.assertIn("dest: \"{{ item.dest }}\"", playbook)
        self.assertIn("mode: \"{{ item.mode }}\"", playbook)
        self.assertIn("name: Reload systemd after Native Service unit drop-in changes", playbook)
        self.assertIn("daemon_reload: true", playbook)
        self.assertIn("name: Restart Native Service after restart-marked config changes", playbook)
        self.assertIn("name: Reload Native Service after reload-only config changes", playbook)
        self.assertIn("fortress_service_start_units | default([])", playbook)
        self.assertIn("fortress_service_stop_units | default([])", playbook)
        self.assertIn("systemctl restart {{ fortress_native_systemd_unit }}", playbook)
        self.assertIn("systemctl reload {{ fortress_native_systemd_unit }}", playbook)
        self.assertIn("selectattr('item.action', 'equalto', 'restart')", playbook)
        self.assertIn("selectattr('item.action', 'equalto', 'reload')", playbook)
        self.assertLess(
            playbook.index("name: Disable conflicting Native Service apt sources"),
            playbook.index("name: Ensure Native Service apt repository tooling is installed"),
        )
        self.assertLess(
            playbook.index("name: Ensure Native Service apt repository tooling is installed"),
            playbook.index("name: Configure Native Service apt repository"),
        )
        self.assertLess(
            playbook.index("name: Ensure Native Service config parent directories exist"),
            playbook.index("name: Render Native Service config files"),
        )
        self.assertLess(
            playbook.index("name: Reload systemd after Native Service unit drop-in changes"),
            playbook.index("name: Restart Native Service after restart-marked config changes"),
        )
        self.assertLess(
            playbook.index("name: Restart Native Service after restart-marked config changes"),
            playbook.index("name: Reload Native Service after reload-only config changes"),
        )
        self.assertIn("fortress_native_restart_needed | default(false) | bool", playbook)
        self.assertIn("not (fortress_native_restart_needed | default(false) | bool)", playbook)

    def test_service_deploy_playbook_converges_caddy_modules_before_native_config_restart(self):
        playbook = (REPO_ROOT / "ansible" / "playbooks" / "service-deploy.yml").read_text()

        self.assertIn("name: List installed Caddy modules for Native Service package extensions", playbook)
        self.assertIn("caddy list-modules", playbook)
        self.assertIn("name: Install missing Caddy module package extensions", playbook)
        self.assertIn("caddy add-package {{ item.package }}", playbook)
        self.assertIn("item.module not in fortress_installed_caddy_modules.stdout_lines", playbook)
        self.assertIn("name: Verify required Caddy modules are available", playbook)
        self.assertIn("Required Caddy module {{ item.module }} is missing after package extension convergence", playbook)
        self.assertLess(
            playbook.index("name: Install Native Service package"),
            playbook.index("name: List installed Caddy modules for Native Service package extensions"),
        )
        self.assertLess(
            playbook.index("name: Install missing Caddy module package extensions"),
            playbook.index("name: Verify required Caddy modules are available"),
        )
        self.assertLess(
            playbook.index("name: Verify required Caddy modules are available"),
            playbook.index("name: Render Native Service config files"),
        )
        self.assertLess(
            playbook.index("name: Verify required Caddy modules are available"),
            playbook.index("name: Restart Native Service after restart-marked config changes"),
        )

    def _fake_decrypt_keys(self, path, calls_log):
        path.write_text(
            "#!/usr/bin/env bash\n"
            "shift 2\n"
            "printf '%s ' \"$@\" > \"$CALLS_LOG\"\n"
        )
        path.chmod(path.stat().st_mode | stat.S_IXUSR)

    def _fake_sops(self, path, calls_log, decrypted):
        path.parent.mkdir(exist_ok=True)
        path.write_text(
            "#!/usr/bin/env bash\n"
            "printf 'sops %s\\n' \"$*\" >> \"$CALLS_LOG\"\n"
            "if [ \"$1\" = \"--decrypt\" ]; then\n"
            "  cat <<'YAML'\n"
            f"{decrypted}"
            "YAML\n"
            "fi\n"
        )
        path.chmod(path.stat().st_mode | stat.S_IXUSR)


if __name__ == "__main__":
    unittest.main()
