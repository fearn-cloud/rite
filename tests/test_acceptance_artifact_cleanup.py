import os
import subprocess
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


class AcceptanceArtifactCleanupTests(unittest.TestCase):
    def test_auto_confirm_cleans_nfs_generated_vm_artifacts_from_policy_names(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._fixture(tmp)
            primary_yaml = root / "inventory" / "vms" / "tmp-nfs-primary.yaml"
            primary_sops = root / "inventory" / "vms" / "tmp-nfs-primary.sops.yaml"
            peer_yaml = root / "inventory" / "vms" / "tmp-nfs-peer.yaml"
            ordinary_vm = root / "inventory" / "vms" / "ordinary.yaml"
            primary_yaml.write_text(self._generated_vm("nfs-shared-mount-acceptance"))
            primary_sops.write_text("sops: generated\n")
            peer_yaml.write_text(self._generated_vm("nfs-shared-mount-acceptance"))
            ordinary_vm.write_text("name: ordinary\n")

            result = subprocess.run(
                [
                    str(REPO_ROOT / "scripts" / "acceptance-clean-generated-artifacts"),
                    "workflow=nfs-shared-mount",
                    "auto_confirm=true",
                ],
                cwd=REPO_ROOT,
                env={**os.environ, "FORTRESS_ROOT": str(root)},
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse(primary_yaml.exists())
            self.assertFalse(primary_sops.exists())
            self.assertFalse(peer_yaml.exists())
            self.assertTrue(ordinary_vm.exists())
            self.assertIn("deleted: 3", result.stdout)
            self.assertIn("absent: 2", result.stdout)

    def test_all_workflows_auto_confirm_cleans_service_layer_artifacts_and_generated_dataset_yaml(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._fixture(tmp)
            self._add_service_layer_policy(root)
            generated_paths = [
                root / "inventory" / "vms" / "tmp-service-primary.yaml",
                root / "inventory" / "vms" / "tmp-service-primary.sops.yaml",
                root / "inventory" / "vms" / "tmp-service-peer.yaml",
                root / "inventory" / "services" / "tmp-service-layer.yaml",
                root / "inventory" / "services" / "tmp-service-layer.sops.yaml",
                root / "inventory" / "services" / "tmp-service-layer-native.yaml",
                root / "inventory" / "datasets" / "acceptance-service-layer.yaml",
            ]
            for path in generated_paths:
                path.write_text(self._generated_content(path, "service-layer-acceptance"))
            quadlet_dir = root / "inventory" / "services" / "tmp-service-layer.quadlet.d"
            native_dir = root / "inventory" / "services" / "tmp-service-layer-native.native.d"
            quadlet_dir.mkdir()
            native_dir.mkdir()
            (quadlet_dir / "web.container").write_text("[Container]\n")
            (native_dir / "Caddyfile.j2").write_text(":18080\n")
            nfs_vm = root / "inventory" / "vms" / "tmp-nfs-primary.yaml"
            nfs_vm.write_text(self._generated_vm("nfs-shared-mount-acceptance"))

            result = subprocess.run(
                [
                    str(REPO_ROOT / "scripts" / "acceptance-clean-generated-artifacts"),
                    "workflow=all",
                    "auto_confirm=true",
                ],
                cwd=REPO_ROOT,
                env={**os.environ, "FORTRESS_ROOT": str(root)},
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            for path in [*generated_paths, quadlet_dir, native_dir, nfs_vm]:
                self.assertFalse(path.exists(), path)
            self.assertIn("deleted: 10", result.stdout)

    def test_default_mode_prints_plan_and_requires_confirmation_without_deleting(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._fixture(tmp)
            primary_yaml = root / "inventory" / "vms" / "tmp-nfs-primary.yaml"
            primary_yaml.write_text(self._generated_vm("nfs-shared-mount-acceptance"))

            result = subprocess.run(
                [
                    str(REPO_ROOT / "scripts" / "acceptance-clean-generated-artifacts"),
                    "workflow=nfs-shared-mount",
                ],
                cwd=REPO_ROOT,
                env={**os.environ, "FORTRESS_ROOT": str(root)},
                input="no\n",
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            self.assertEqual(result.returncode, 1)
            self.assertTrue(primary_yaml.exists())
            self.assertIn("delete: VM YAML", result.stdout)
            self.assertIn("cancelled", result.stdout)

    def test_default_mode_without_deletable_artifacts_summarizes_without_prompting(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._fixture(tmp)

            result = subprocess.run(
                [
                    str(REPO_ROOT / "scripts" / "acceptance-clean-generated-artifacts"),
                    "workflow=nfs-shared-mount",
                ],
                cwd=REPO_ROOT,
                env={**os.environ, "FORTRESS_ROOT": str(root)},
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("deleted: 0", result.stdout)
            self.assertIn("refused: 0", result.stdout)
            self.assertNotIn("cancelled", result.stdout)

    def test_default_mode_cancels_cleanly_when_confirmation_input_is_unavailable(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._fixture(tmp)
            primary_yaml = root / "inventory" / "vms" / "tmp-nfs-primary.yaml"
            primary_yaml.write_text(self._generated_vm("nfs-shared-mount-acceptance"))

            result = subprocess.run(
                [
                    str(REPO_ROOT / "scripts" / "acceptance-clean-generated-artifacts"),
                    "workflow=nfs-shared-mount",
                ],
                cwd=REPO_ROOT,
                env={**os.environ, "FORTRESS_ROOT": str(root)},
                stdin=subprocess.DEVNULL,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            self.assertEqual(result.returncode, 1)
            self.assertTrue(primary_yaml.exists())
            self.assertIn("cancelled", result.stdout)
            self.assertNotIn("Traceback", result.stderr)

    def test_refuses_expected_path_when_yaml_is_not_generated_acceptance_inventory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._fixture(tmp)
            primary_yaml = root / "inventory" / "vms" / "tmp-nfs-primary.yaml"
            primary_sops = root / "inventory" / "vms" / "tmp-nfs-primary.sops.yaml"
            dataset_yaml = root / "inventory" / "datasets" / "acceptance-nfs-demo.yaml"
            primary_yaml.write_text("lifecycle:\n  kind: ordinary\n")
            primary_sops.write_text("ordinary secret\n")
            dataset_yaml.write_text("name: acceptance-nfs-demo\nlifecycle: ephemeral\n")

            result = subprocess.run(
                [
                    str(REPO_ROOT / "scripts" / "acceptance-clean-generated-artifacts"),
                    "workflow=nfs-shared-mount",
                    "auto_confirm=true",
                ],
                cwd=REPO_ROOT,
                env={**os.environ, "FORTRESS_ROOT": str(root)},
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(primary_yaml.exists())
            self.assertTrue(primary_sops.exists())
            self.assertIn("refuse: VM YAML", result.stdout)
            self.assertIn("refuse: VM Sibling SOPS File", result.stdout)
            self.assertIn("refused: 3", result.stdout)

    def test_just_recipe_and_runbooks_document_generated_artifact_cleanup(self):
        justfile = (REPO_ROOT / "justfile").read_text()
        service_runbook = (REPO_ROOT / "runbooks" / "new-service.md").read_text()
        nas_runbook = (REPO_ROOT / "runbooks" / "nas-truenas.md").read_text()

        self.assertIn('acceptance-clean-generated-artifacts workflow auto_confirm="false":', justfile)
        self.assertIn("./scripts/acceptance-clean-generated-artifacts", justfile)
        self.assertIn("workflow=${workflow#workflow=}", justfile)
        self.assertIn("auto_confirm=${auto_confirm#auto_confirm=}", justfile)
        self.assertIn("just acceptance-clean-generated-artifacts workflow=service-layer", service_runbook)
        self.assertIn("just acceptance-clean-generated-artifacts workflow=all", service_runbook)
        self.assertIn("just acceptance-clean-generated-artifacts workflow=nfs-shared-mount", nas_runbook)
        self.assertIn("just acceptance-clean-generated-artifacts workflow=all", nas_runbook)

    def _fixture(self, tmp):
        root = Path(tmp)
        inventory = root / "inventory"
        for subdir in ["acceptance", "vms", "services", "datasets"]:
            (inventory / subdir).mkdir(parents=True, exist_ok=True)
        (inventory / "acceptance" / "nfs-shared-mount.yaml").write_text(
            "dataset: acceptance-nfs-demo\n"
            "vms:\n"
            "  primary:\n"
            "    name: tmp-nfs-primary\n"
            "  peer:\n"
            "    name: tmp-nfs-peer\n"
        )
        return root

    def _add_service_layer_policy(self, root):
        (root / "inventory" / "acceptance" / "service-layer.yaml").write_text(
            "dataset: acceptance-service-layer\n"
            "vms:\n"
            "  primary:\n"
            "    name: tmp-service-primary\n"
            "  peer:\n"
            "    name: tmp-service-peer\n"
        )

    def _generated_vm(self, purpose):
        return (
            "description: Generated Acceptance VM. Do not edit by hand.\n"
            "lifecycle:\n"
            "  kind: operational\n"
            f"  purpose: {purpose}\n"
            "  generated: true\n"
        )

    def _generated_content(self, path, purpose):
        if path.parts[-2] == "vms":
            return self._generated_vm(purpose)
        if path.parts[-2] == "datasets":
            marker = (
                "# Generated Service-layer Acceptance Dataset. Do not edit by hand.\n"
                if purpose == "service-layer-acceptance"
                else "# Generated NFS shared-mount Acceptance Dataset. Do not edit by hand.\n"
            )
            return (
                marker +
                f"name: {path.stem}\n"
                "nas: truenas\n"
                f"path: /mnt/tank/fortress-acceptance/{path.stem.removeprefix('acceptance-')}\n"
                "lifecycle: ephemeral\n"
            )
        return (
            f"name: {path.stem.removesuffix('.sops')}\n"
            "generated: true\n"
            f"generated_by: {purpose}\n"
        )
