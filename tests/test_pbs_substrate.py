import shutil
import tempfile
import unittest
from pathlib import Path

from fortress_inventory.model import load_inventory_tree
from fortress_inventory.pbs_substrate import inspect_pbs_substrate
from fortress_inventory.validate import validate_inventory_tree


REPO_ROOT = Path(__file__).resolve().parents[1]


class PbsSubstrateTests(unittest.TestCase):
    def test_repo_inventory_identifies_pbs_vm_and_declared_host(self):
        substrate = inspect_pbs_substrate(load_inventory_tree(REPO_ROOT))

        self.assertEqual("pbs-vm", substrate.vm_name)
        self.assertEqual("straylight", substrate.host_name)

    def test_repo_inventory_represents_pbs_service_that_runs_on_pbs_vm(self):
        substrate = inspect_pbs_substrate(load_inventory_tree(REPO_ROOT))

        self.assertEqual("pbs", substrate.service_name)
        self.assertEqual("pbs-vm", substrate.service_vm_name)
        self.assertEqual("proxmox-backup-server", substrate.service_package)
        self.assertEqual("proxmox-backup-proxy", substrate.systemd_service_name)

    def test_repo_inventory_discovers_primary_datastore_for_backup_runs(self):
        substrate = inspect_pbs_substrate(load_inventory_tree(REPO_ROOT))

        self.assertEqual("pbs-datastore", substrate.primary_datastore_name)
        self.assertEqual("/mnt/tank/pbs-datastore", substrate.primary_datastore_dataset_path)
        self.assertEqual("/mnt/nas/pbs-datastore", substrate.primary_datastore_backup_run_path)
        self.assertTrue(substrate.primary_datastore_usable_for_backup_runs)

    def test_recovery_secret_availability_is_reported_without_secret_material(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            shutil.copytree(REPO_ROOT / "inventory", root / "inventory")
            (root / "inventory" / "vms" / "pbs-vm.sops.yaml").write_text(
                "recovery_secrets:\n"
                "  pbs_encryption_key:\n"
                "    value: super-secret-material\n"
            )

            substrate = inspect_pbs_substrate(load_inventory_tree(root))

        self.assertTrue(substrate.recovery_secret_available)
        self.assertIn("Recovery Secret: available", substrate.operator_summary())
        self.assertNotIn("super-secret-material", substrate.operator_summary())

    def test_pbs_vm_is_unprotected_exception_and_summary_separates_target_readiness(self):
        substrate = inspect_pbs_substrate(load_inventory_tree(REPO_ROOT))

        self.assertEqual("pbs-vm", substrate.unprotected_vm_name)
        self.assertIn("local PBS instance", substrate.unprotected_reason)
        summary = substrate.operator_summary()
        self.assertIn("PBS substrate readiness", summary)
        self.assertIn("Boundary: local PBS does not back up itself.", summary)
        self.assertIn("Backup Target readiness: not evaluated in substrate check", summary)

    def test_inventory_validation_requires_pbs_vm(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            shutil.copytree(REPO_ROOT / "inventory", root / "inventory")
            (root / "inventory" / "vms" / "pbs-vm.yaml").unlink()

            codes = {error.code for error in validate_inventory_tree(root)}

        self.assertIn("missing_pbs_vm", codes)

    def test_inventory_validation_requires_pbs_service_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            shutil.copytree(REPO_ROOT / "inventory", root / "inventory")
            (root / "inventory" / "services" / "pbs.yaml").write_text(
                "name: pbs\n"
                "backend:\n"
                "  vm: media-vm\n"
                "  port: 8007\n"
                "deploy:\n"
                "  type: native\n"
                "  package: nginx\n"
                "  service_name: nginx\n"
                "  config_files:\n"
                "    - template: datastore.cfg.j2\n"
                "      dest: /etc/proxmox-backup/datastore.cfg\n"
                "      mode: \"0640\"\n"
                "      restart_on_change: true\n"
            )

            codes = {error.code for error in validate_inventory_tree(root)}

        self.assertIn("invalid_pbs_service", codes)

    def test_inventory_validation_requires_usable_primary_datastore(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            shutil.copytree(REPO_ROOT / "inventory", root / "inventory")
            vm_path = root / "inventory" / "vms" / "pbs-vm.yaml"
            vm_path.write_text(vm_path.read_text().replace("    access: read_write\n", "    access: read_only\n"))

            codes = {error.code for error in validate_inventory_tree(root)}

        self.assertIn("unusable_pbs_primary_datastore", codes)

    def test_inventory_validation_requires_recovery_secret_availability(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            shutil.copytree(REPO_ROOT / "inventory", root / "inventory")
            (root / "inventory" / "vms" / "pbs-vm.sops.yaml").unlink(missing_ok=True)

            codes = {error.code for error in validate_inventory_tree(root)}

        self.assertIn("missing_pbs_recovery_secret", codes)

    def test_inventory_validation_requires_pbs_vm_unprotected_exception(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            shutil.copytree(REPO_ROOT / "inventory", root / "inventory")
            vm_path = root / "inventory" / "vms" / "pbs-vm.yaml"
            vm_path.write_text(
                vm_path.read_text().replace(
                    "backup:\n"
                    "  enabled: false\n"
                    "  reason: PBS itself is recovered from Inventory, the Primary Datastore, and Recovery Secrets, not from the local PBS instance.\n",
                    "backup:\n"
                    "  enabled: true\n",
                )
            )

            codes = {error.code for error in validate_inventory_tree(root)}

        self.assertIn("pbs_vm_must_be_unprotected", codes)
