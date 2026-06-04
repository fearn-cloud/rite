import datetime as dt
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch

from fortress_inventory.backup_configure_apply import (
    PveshBackupJobClient,
    apply_backup_configure_plan,
    backup_configure_plans_from_dict,
)
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
        logs = []

        result = apply_backup_configure_plan(plan, client, reporter=logs.append)

        self.assertTrue(result.success)
        self.assertEqual(
            [
                "Applying Backup Configure plan for Host neuromancer (1 action(s))",
                (
                    "Host neuromancer: create Backup Target media-vm; "
                    "Backup Job fortress-backup-media-vm-default; "
                    "datastore=pbs-datastore; schedule=03:42"
                ),
                "Host neuromancer: create complete for Backup Job fortress-backup-media-vm-default",
                "Backup Configure apply complete for Host neuromancer",
            ],
            logs,
        )
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

    def test_fleet_plan_json_deserializes_as_host_scoped_apply_plans(self):
        plans = backup_configure_plans_from_dict(
            [
                {
                    "host_name": "molly",
                    "actions": [
                        {
                            "action": "create",
                            "vm_name": "dns-secondary-vm",
                            "vmid": 1008,
                            "policy_name": "default",
                            "primary_datastore": "pbs-datastore",
                            "job_name": "fortress-backup-dns-secondary-vm-default",
                            "scheduled_time": "03:50",
                            "retention": {"daily": 14, "weekly": 8},
                        }
                    ],
                    "pending_first_successful_runs": ["dns-secondary-vm"],
                },
                {
                    "host_name": "neuromancer",
                    "actions": [],
                    "pending_first_successful_runs": [],
                },
            ]
        )

        self.assertEqual(("molly", "neuromancer"), tuple(plan.host_name for plan in plans))
        self.assertEqual("dns-secondary-vm", plans[0].actions[0].vm_name)
        self.assertEqual(dt.time(3, 50), plans[0].actions[0].scheduled_time)
        self.assertEqual(("dns-secondary-vm",), plans[0].pending_first_successful_runs)

    def test_pvesh_client_runs_pvesh_directly_through_host_shell(self):
        with patch("fortress_inventory.backup_configure_apply.subprocess.run") as run:
            run.return_value = subprocess.CompletedProcess(args=[], returncode=0)

            PveshBackupJobClient("molly", repo_root=Path("/repo")).create_backup_job(
                job_name="fortress-backup-dns-secondary-vm-default",
                vmid=1008,
                datastore="pbs-datastore",
                scheduled_time=dt.time(3, 50),
                retention={"daily": 14},
            )

        command = run.call_args.args[0]
        self.assertEqual(
            [
                "/repo/scripts/host-shell",
                "molly",
                "--",
                "pvesh",
                "create",
                "/cluster/backup",
            ],
            command[:6],
        )
        self.assertNotIn("sudo", command)
        self.assertEqual("03:50", command[command.index("--schedule") + 1])

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

    def test_apply_converges_create_when_fortress_owned_backup_job_already_exists(self):
        plan = BackupConfigurePlan(
            host_name="molly",
            actions=(
                BackupConfigureAction(
                    action="create",
                    vm_name="dns-secondary-vm",
                    vmid=1008,
                    policy_name="default",
                    primary_datastore="pbs-datastore",
                    job_name="fortress-backup-dns-secondary-vm-default",
                    scheduled_time=dt.time(3, 50),
                    retention={"daily": 14, "weekly": 8},
                ),
            ),
        )
        client = FakeBackupJobClient(fail_on="create_already_exists")
        logs = []

        result = apply_backup_configure_plan(plan, client, reporter=logs.append)

        self.assertTrue(result.success)
        self.assertEqual(("update",), result.applied_actions)
        self.assertIn(
            "Host molly: Backup Job fortress-backup-dns-secondary-vm-default already exists; updating instead",
            logs,
        )
        self.assertIn(
            "Host molly: update complete for Backup Job fortress-backup-dns-secondary-vm-default",
            logs,
        )
        self.assertEqual(
            [
                (
                    "update",
                    {
                        "job_name": "fortress-backup-dns-secondary-vm-default",
                        "vmid": 1008,
                        "datastore": "pbs-datastore",
                        "scheduled_time": dt.time(3, 50),
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
        if self.fail_on == "create_already_exists":
            raise RuntimeError(f"Job '{job_name}' already exists")
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
