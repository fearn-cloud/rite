import datetime as dt
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from fortress_inventory.backup_configure_apply import apply_backup_configure_plan
from fortress_inventory.backup_configure_plan import BackupConfigureAction, BackupConfigurePlan
from fortress_inventory.initial_backup_run import trigger_initial_backup_runs


class InitialBackupRunTriggeringTests(unittest.TestCase):
    def test_just_initial_backup_run_calls_workflow_script(self):
        justfile = (Path(__file__).resolve().parents[1] / "justfile").read_text()

        self.assertIn("backup-initial-run plan_json target=\"\":", justfile)
        self.assertIn("./scripts/backup-initial-run --plan-json {{plan_json}}", justfile)
        self.assertIn("--target {{target}}", justfile)

    def test_operator_can_trigger_one_initial_backup_run_for_one_backup_target(self):
        plan = BackupConfigurePlan(
            host_name="neuromancer",
            actions=(
                BackupConfigureAction(
                    action="no-op",
                    vm_name="media-vm",
                    vmid=1103,
                    policy_name="default",
                    primary_datastore="pbs-datastore",
                    job_name="fortress-backup-media-vm-default",
                    scheduled_time=dt.time(3, 42),
                ),
            ),
            pending_first_successful_runs=("media-vm",),
        )
        client = FakeInitialBackupRunClient()

        result = trigger_initial_backup_runs(plan, client, target_name="media-vm")

        self.assertTrue(result.success)
        self.assertEqual(
            [("trigger", {"job_name": "fortress-backup-media-vm-default", "vmid": 1103})],
            client.calls,
        )
        self.assertIn("Submitted initial Backup Run for Backup Target media-vm", result.render())

    def test_operator_can_trigger_host_scoped_initial_backup_runs(self):
        plan = BackupConfigurePlan(
            host_name="neuromancer",
            actions=(
                BackupConfigureAction(
                    action="no-op",
                    vm_name="download-vm",
                    vmid=1104,
                    policy_name="default",
                    primary_datastore="pbs-datastore",
                    job_name="fortress-backup-download-vm-default",
                    scheduled_time=dt.time(3, 55),
                ),
                BackupConfigureAction(
                    action="no-op",
                    vm_name="media-vm",
                    vmid=1103,
                    policy_name="default",
                    primary_datastore="pbs-datastore",
                    job_name="fortress-backup-media-vm-default",
                    scheduled_time=dt.time(3, 42),
                ),
            ),
            pending_first_successful_runs=("download-vm", "media-vm"),
        )
        client = FakeInitialBackupRunClient()

        result = trigger_initial_backup_runs(plan, client)

        self.assertTrue(result.success)
        self.assertEqual(
            [
                ("trigger", {"job_name": "fortress-backup-download-vm-default", "vmid": 1104}),
                ("trigger", {"job_name": "fortress-backup-media-vm-default", "vmid": 1103}),
            ],
            client.calls,
        )

    def test_normal_backup_configure_apply_never_triggers_initial_backup_runs(self):
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
            pending_first_successful_runs=("media-vm",),
        )
        client = FakeBackupConfigureClient()

        result = apply_backup_configure_plan(plan, client)

        self.assertTrue(result.success)
        self.assertEqual(
            [("create", {"job_name": "fortress-backup-media-vm-default", "vmid": 1103})],
            client.calls,
        )

    def test_explicit_initial_trigger_bypasses_scheduled_stagger(self):
        plan = BackupConfigurePlan(
            host_name="neuromancer",
            actions=(
                BackupConfigureAction(
                    action="no-op",
                    vm_name="media-vm",
                    vmid=1103,
                    policy_name="default",
                    primary_datastore="pbs-datastore",
                    job_name="fortress-backup-media-vm-default",
                    scheduled_time=dt.time(3, 42),
                ),
            ),
            pending_first_successful_runs=("media-vm",),
        )
        client = FakeInitialBackupRunClient()

        result = trigger_initial_backup_runs(plan, client, target_name="media-vm")

        self.assertIn("submitted now", result.render())
        self.assertNotIn("03:42", result.render())

    def test_output_reports_pending_first_runs_and_does_not_claim_protection(self):
        plan = BackupConfigurePlan(
            host_name="neuromancer",
            actions=(
                BackupConfigureAction(
                    action="no-op",
                    vm_name="download-vm",
                    vmid=1104,
                    policy_name="default",
                    primary_datastore="pbs-datastore",
                    job_name="fortress-backup-download-vm-default",
                    scheduled_time=dt.time(3, 55),
                ),
                BackupConfigureAction(
                    action="no-op",
                    vm_name="media-vm",
                    vmid=1103,
                    policy_name="default",
                    primary_datastore="pbs-datastore",
                    job_name="fortress-backup-media-vm-default",
                    scheduled_time=dt.time(3, 42),
                ),
            ),
            pending_first_successful_runs=("download-vm", "media-vm"),
        )
        client = FakeInitialBackupRunClient()

        result = trigger_initial_backup_runs(plan, client, target_name="media-vm")

        rendered = result.render()
        self.assertIn("Submitted initial Backup Run for Backup Target media-vm", rendered)
        self.assertIn("Pending first successful Backup Run: download-vm, media-vm", rendered)
        self.assertIn("Trigger submission is not proven backup protection", rendered)

    def test_named_target_must_be_pending_first_successful_run(self):
        plan = BackupConfigurePlan(
            host_name="neuromancer",
            actions=(
                BackupConfigureAction(
                    action="no-op",
                    vm_name="media-vm",
                    vmid=1103,
                    policy_name="default",
                    primary_datastore="pbs-datastore",
                    job_name="fortress-backup-media-vm-default",
                    scheduled_time=dt.time(3, 42),
                ),
            ),
            pending_first_successful_runs=(),
        )
        client = FakeInitialBackupRunClient()

        result = trigger_initial_backup_runs(plan, client, target_name="media-vm")

        self.assertFalse(result.success)
        self.assertEqual([], client.calls)
        self.assertIn("does not have a pending first successful Backup Run", result.render())

    def test_operator_script_triggers_one_target_from_plan_json(self):
        plan_json = {
            "host_name": "neuromancer",
            "actions": [
                {
                    "action": "no-op",
                    "vm_name": "media-vm",
                    "vmid": 1103,
                    "policy_name": "default",
                    "primary_datastore": "pbs-datastore",
                    "job_name": "fortress-backup-media-vm-default",
                    "scheduled_time": "03:42",
                    "retention": None,
                }
            ],
            "pending_first_successful_runs": ["media-vm"],
        }
        with tempfile.TemporaryDirectory() as tmp:
            plan_path = Path(tmp) / "plan.json"
            calls_path = Path(tmp) / "calls.json"
            plan_path.write_text(json.dumps(plan_json))
            env = os.environ.copy()
            env["FORTRESS_TEST_INITIAL_BACKUP_RUN_LOG"] = str(calls_path)

            result = subprocess.run(
                [
                    str(Path(__file__).resolve().parents[1] / "scripts" / "backup-initial-run"),
                    "--plan-json",
                    str(plan_path),
                    "--target",
                    "media-vm",
                ],
                cwd=Path(__file__).resolve().parents[1],
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            self.assertEqual(0, result.returncode, result.stderr)
            self.assertIn("Submitted initial Backup Run for Backup Target media-vm", result.stdout)
            self.assertIn("Trigger submission is not proven backup protection", result.stdout)
            self.assertEqual(
                [{"host": "neuromancer", "job_name": "fortress-backup-media-vm-default", "vmid": 1103}],
                json.loads(calls_path.read_text()),
            )


class FakeInitialBackupRunClient:
    def __init__(self):
        self.calls = []

    def trigger_backup_job_now(self, *, job_name, vmid):
        self.calls.append(("trigger", {"job_name": job_name, "vmid": vmid}))


class FakeBackupConfigureClient:
    def __init__(self):
        self.calls = []

    def create_backup_job(self, *, job_name, vmid, datastore, scheduled_time, retention=None):
        self.calls.append(("create", {"job_name": job_name, "vmid": vmid}))

    def update_backup_job(self, *, job_name, vmid, datastore, scheduled_time, retention=None):
        self.calls.append(("update", {"job_name": job_name, "vmid": vmid}))

    def delete_backup_job(self, *, job_name):
        self.calls.append(("delete", {"job_name": job_name}))

    def trigger_backup_job_now(self, *, job_name, vmid):
        self.calls.append(("trigger", {"job_name": job_name, "vmid": vmid}))


if __name__ == "__main__":
    unittest.main()
