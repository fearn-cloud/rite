import datetime as dt
import unittest
from pathlib import Path

from fortress_inventory.backup_configure_apply import apply_backup_configure_plan
from fortress_inventory.backup_configure_plan import (
    BackupConfigureAction,
    BackupConfigurePlan,
    ObservedBackupJob,
    plan_host_backup_configure,
)
from fortress_inventory.model import InventoryModel


class BackupConfigureApplyTests(unittest.TestCase):
    def test_just_backup_configure_apply_calls_workflow_script(self):
        justfile = (Path(__file__).resolve().parents[1] / "justfile").read_text()

        self.assertIn("backup-configure-apply plan_json auto_confirm_prune=\"false\":", justfile)
        self.assertIn("./scripts/backup-configure-apply --plan-json {{plan_json}}", justfile)
        self.assertIn("--auto-confirm-prune", justfile)

    def test_apply_creates_missing_fortress_owned_backup_jobs(self):
        plan = BackupConfigurePlan(
            host_name="neuromancer",
            actions=(
                BackupConfigureAction(
                    action="create",
                    vm_name="media-vm",
                    vmid=1103,
                    policy_name="default",
                    primary_datastore="pbs-datastore",
                    job_name="fortress-backup-media-vm-default",
                    scheduled_time=dt.time(3, 42),
                    retention={"daily": 14, "weekly": 8},
                ),
            ),
        )
        client = FakeBackupJobClient()

        result = apply_backup_configure_plan(plan, client)

        self.assertTrue(result.success)
        self.assertEqual(
            [
                (
                    "create",
                    {
                        "job_name": "fortress-backup-media-vm-default",
                        "vmid": 1103,
                        "datastore": "pbs-datastore",
                        "scheduled_time": dt.time(3, 42),
                        "retention": {"daily": 14, "weekly": 8},
                    },
                )
            ],
            client.calls,
        )

    def test_apply_updates_drifted_fortress_owned_backup_jobs(self):
        plan = BackupConfigurePlan(
            host_name="neuromancer",
            actions=(
                BackupConfigureAction(
                    action="update",
                    vm_name="media-vm",
                    vmid=1103,
                    policy_name="default",
                    primary_datastore="pbs-datastore",
                    job_name="fortress-backup-media-vm-default",
                    scheduled_time=dt.time(3, 42),
                    retention={"daily": 14, "weekly": 8},
                ),
            ),
        )
        client = FakeBackupJobClient()

        result = apply_backup_configure_plan(plan, client)

        self.assertTrue(result.success)
        self.assertEqual(
            [
                (
                    "update",
                    {
                        "job_name": "fortress-backup-media-vm-default",
                        "vmid": 1103,
                        "datastore": "pbs-datastore",
                        "scheduled_time": dt.time(3, 42),
                        "retention": {"daily": 14, "weekly": 8},
                    },
                )
            ],
            client.calls,
        )

    def test_apply_prunes_obsolete_fortress_owned_backup_jobs_after_confirmation(self):
        plan = BackupConfigurePlan(
            host_name="neuromancer",
            actions=(
                BackupConfigureAction(
                    action="prune",
                    vm_name="old-vm",
                    vmid=1109,
                    policy_name="default",
                    primary_datastore="pbs-datastore",
                    job_name="fortress-backup-old-vm-default",
                    scheduled_time=dt.time(3, 45),
                ),
            ),
        )
        client = FakeBackupJobClient()

        result = apply_backup_configure_plan(plan, client, confirm_prune=lambda plan, actions: True)

        self.assertTrue(result.success)
        self.assertEqual(
            [
                (
                    "delete",
                    {
                        "job_name": "fortress-backup-old-vm-default",
                    },
                )
            ],
            client.calls,
        )

    def test_apply_refuses_pruning_without_confirmation(self):
        plan = BackupConfigurePlan(
            host_name="neuromancer",
            actions=(
                BackupConfigureAction(
                    action="prune",
                    vm_name="old-vm",
                    vmid=1109,
                    policy_name="default",
                    primary_datastore="pbs-datastore",
                    job_name="fortress-backup-old-vm-default",
                    scheduled_time=dt.time(3, 45),
                ),
            ),
        )
        client = FakeBackupJobClient()

        result = apply_backup_configure_plan(plan, client, confirm_prune=lambda plan, actions: False)

        self.assertFalse(result.success)
        self.assertEqual([], client.calls)

    def test_apply_supports_explicit_auto_confirm_pruning(self):
        plan = BackupConfigurePlan(
            host_name="neuromancer",
            actions=(
                BackupConfigureAction(
                    action="prune",
                    vm_name="old-vm",
                    vmid=1109,
                    policy_name="default",
                    primary_datastore="pbs-datastore",
                    job_name="fortress-backup-old-vm-default",
                    scheduled_time=dt.time(3, 45),
                ),
            ),
        )
        client = FakeBackupJobClient()

        result = apply_backup_configure_plan(
            plan,
            client,
            auto_confirm_prune=True,
            confirm_prune=lambda plan, actions: self.fail("auto-confirm should not prompt"),
        )

        self.assertTrue(result.success)
        self.assertEqual([("delete", {"job_name": "fortress-backup-old-vm-default"})], client.calls)

    def test_apply_preserves_manual_pve_jobs_ignored_by_the_plan(self):
        model = self._model(vms={})
        plan = plan_host_backup_configure(
            model,
            "neuromancer",
            observed_jobs=[
                ObservedBackupJob(
                    name="manual-weekend-backup",
                    vmid=1103,
                    datastore="pbs-datastore",
                    scheduled_time=dt.time(1, 0),
                    fortress_owned=False,
                )
            ],
        )
        client = FakeBackupJobClient()

        result = apply_backup_configure_plan(plan, client)

        self.assertTrue(result.success)
        self.assertEqual((), result.applied_actions)
        self.assertEqual([], client.calls)

    def test_apply_failure_reports_host_backup_target_backup_job_and_action_context(self):
        plan = BackupConfigurePlan(
            host_name="neuromancer",
            actions=(
                BackupConfigureAction(
                    action="create",
                    vm_name="media-vm",
                    vmid=1103,
                    policy_name="default",
                    primary_datastore="pbs-datastore",
                    job_name="fortress-backup-media-vm-default",
                    scheduled_time=dt.time(3, 42),
                ),
            ),
        )
        client = FakeBackupJobClient(fail_on="create")

        result = apply_backup_configure_plan(plan, client)

        self.assertFalse(result.success)
        self.assertIn("Host neuromancer", result.message)
        self.assertIn("Backup Target media-vm", result.message)
        self.assertIn("Backup Job fortress-backup-media-vm-default", result.message)
        self.assertIn("action create", result.message)
        self.assertIn("pve create failed", result.message)

    def _model(self, *, vms):
        return InventoryModel(
            root=None,
            hosts={"neuromancer": {}},
            vms=vms,
            services={},
            datasets={},
            nas_endpoints={},
            templates={},
            template_verification_policy={},
            acceptance_policies={},
            globals={},
            backup_policy_file_exists=True,
            backup_policies={
                "default": {
                    "schedule": {
                        "cadence": "daily",
                        "time": "03:30",
                        "timezone": "America/Denver",
                        "stagger": "60m",
                    },
                    "retention": {"daily": 14, "weekly": 8, "monthly": 12},
                }
            },
        )


class FakeBackupJobClient:
    def __init__(self, fail_on=None):
        self.calls = []
        self.fail_on = fail_on

    def create_backup_job(self, *, job_name, vmid, datastore, scheduled_time, retention=None):
        if self.fail_on == "create":
            raise RuntimeError("pve create failed")
        self.calls.append(
            (
                "create",
                {
                    "job_name": job_name,
                    "vmid": vmid,
                    "datastore": datastore,
                    "scheduled_time": scheduled_time,
                    "retention": retention,
                },
            )
        )

    def update_backup_job(self, *, job_name, vmid, datastore, scheduled_time, retention=None):
        if self.fail_on == "update":
            raise RuntimeError("pve update failed")
        self.calls.append(
            (
                "update",
                {
                    "job_name": job_name,
                    "vmid": vmid,
                    "datastore": datastore,
                    "scheduled_time": scheduled_time,
                    "retention": retention,
                },
            )
        )

    def delete_backup_job(self, *, job_name):
        if self.fail_on == "delete":
            raise RuntimeError("pve delete failed")
        self.calls.append(
            (
                "delete",
                {
                    "job_name": job_name,
                },
            )
        )


if __name__ == "__main__":
    unittest.main()
