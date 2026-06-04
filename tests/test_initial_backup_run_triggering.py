import datetime as dt
import json
import os
import subprocess
import tempfile
import unittest
from unittest import mock
from pathlib import Path

from fortress_inventory.backup_configure_apply import apply_backup_configure_plan
from fortress_inventory.backup_configure_plan import BackupConfigureAction, BackupConfigurePlan
from fortress_inventory.initial_backup_run import PveshInitialBackupRunClient, trigger_initial_backup_runs


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
            [
                (
                    "trigger",
                    {
                        "job_name": "fortress-backup-media-vm-default",
                        "vmid": 1103,
                        "datastore": "pbs-datastore",
                        "retention": None,
                    },
                )
            ],
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
                (
                    "trigger",
                    {
                        "job_name": "fortress-backup-download-vm-default",
                        "vmid": 1104,
                        "datastore": "pbs-datastore",
                        "retention": None,
                    },
                ),
                (
                    "trigger",
                    {
                        "job_name": "fortress-backup-media-vm-default",
                        "vmid": 1103,
                        "datastore": "pbs-datastore",
                        "retention": None,
                    },
                ),
            ],
            client.calls,
        )

    def test_host_with_no_pending_first_runs_is_successful_noop(self):
        plan = BackupConfigurePlan(
            host_name="wintermute",
            actions=(),
            pending_first_successful_runs=(),
        )
        client = FakeInitialBackupRunClient()

        result = trigger_initial_backup_runs(plan, client)

        self.assertTrue(result.success)
        self.assertEqual([], client.calls)
        self.assertIn("No pending first successful Backup Runs on Host wintermute", result.render())

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

    def test_output_surfaces_pve_submission_output(self):
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
        client = FakeInitialBackupRunClient(
            outputs=("UPID:neuromancer:00135F3F:vzdump:1103:root@pam:",)
        )

        result = trigger_initial_backup_runs(plan, client, target_name="media-vm")

        rendered = result.render()
        self.assertIn("Submitted initial Backup Run for Backup Target media-vm", rendered)
        self.assertIn(
            "PVE submission output for Backup Target media-vm: "
            "UPID:neuromancer:00135F3F:vzdump:1103:root@pam:",
            rendered,
        )

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
                [
                    {
                        "host": "neuromancer",
                        "job_name": "fortress-backup-media-vm-default",
                        "vmid": 1103,
                        "datastore": "pbs-datastore",
                        "retention": None,
                    }
                ],
                json.loads(calls_path.read_text()),
            )

    def test_operator_script_triggers_pending_targets_from_fleet_plan_json(self):
        plan_json = [
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
                        "retention": None,
                    }
                ],
                "pending_first_successful_runs": ["dns-secondary-vm"],
            },
            {
                "host_name": "neuromancer",
                "actions": [
                    {
                        "action": "create",
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
            },
        ]
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
                ],
                cwd=Path(__file__).resolve().parents[1],
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            self.assertEqual(0, result.returncode, result.stderr)
            self.assertIn("Submitted initial Backup Run for Backup Target dns-secondary-vm", result.stdout)
            self.assertIn("Submitted initial Backup Run for Backup Target media-vm", result.stdout)
            self.assertEqual(
                [
                    {
                        "host": "molly",
                        "job_name": "fortress-backup-dns-secondary-vm-default",
                        "vmid": 1008,
                        "datastore": "pbs-datastore",
                        "retention": None,
                    },
                    {
                        "host": "neuromancer",
                        "job_name": "fortress-backup-media-vm-default",
                        "vmid": 1103,
                        "datastore": "pbs-datastore",
                        "retention": None,
                    },
                ],
                json.loads(calls_path.read_text()),
            )

    def test_pvesh_client_triggers_backup_job_without_sudo(self):
        client = PveshInitialBackupRunClient("neuromancer", repo_root=Path("/repo"))

        with mock.patch("fortress_inventory.initial_backup_run.subprocess.run") as run:
            run.return_value = subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")

            client.trigger_backup_job_now(
                job_name="fortress-backup-media-vm-default",
                vmid=1103,
                datastore="pbs-datastore",
                retention={"daily": 14, "weekly": 8, "monthly": 12},
            )

        run.assert_called_once_with(
            [
                "/repo/scripts/host-shell",
                "neuromancer",
                "--",
                "pvesh",
                "create",
                "/nodes/neuromancer/vzdump",
                "--vmid",
                "1103",
                "--storage",
                "pbs-datastore",
                "--mode",
                "snapshot",
                "--job-id",
                "fortress-backup-media-vm-default",
                "--prune-backups",
                "keep-daily=14,keep-monthly=12,keep-weekly=8",
            ],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

    def test_pvesh_client_returns_successful_submission_output(self):
        client = PveshInitialBackupRunClient("neuromancer", repo_root=Path("/repo"))

        with mock.patch("fortress_inventory.initial_backup_run.subprocess.run") as run:
            run.return_value = subprocess.CompletedProcess(
                args=[],
                returncode=0,
                stdout="UPID:neuromancer:00135F3F:vzdump:1103:root@pam:\n",
                stderr="task accepted\n",
            )

            output = client.trigger_backup_job_now(
                job_name="fortress-backup-media-vm-default",
                vmid=1103,
                datastore="pbs-datastore",
            )

        self.assertEqual(
            "UPID:neuromancer:00135F3F:vzdump:1103:root@pam:\ntask accepted",
            output,
        )


class FakeInitialBackupRunClient:
    def __init__(self, outputs=()):
        self.calls = []
        self.outputs = list(outputs)

    def trigger_backup_job_now(self, *, job_name, vmid, datastore, retention=None):
        self.calls.append(
            (
                "trigger",
                {
                    "job_name": job_name,
                    "vmid": vmid,
                    "datastore": datastore,
                    "retention": retention,
                },
            )
        )
        if self.outputs:
            return self.outputs.pop(0)
        return None


class FakeBackupConfigureClient:
    def __init__(self):
        self.calls = []

    def create_backup_job(self, *, job_name, vmid, datastore, scheduled_time, retention=None):
        self.calls.append(("create", {"job_name": job_name, "vmid": vmid}))

    def update_backup_job(self, *, job_name, vmid, datastore, scheduled_time, retention=None):
        self.calls.append(("update", {"job_name": job_name, "vmid": vmid}))

    def delete_backup_job(self, *, job_name):
        self.calls.append(("delete", {"job_name": job_name}))

    def trigger_backup_job_now(self, *, job_name, vmid, datastore, retention=None):
        self.calls.append(
            (
                "trigger",
                {
                    "job_name": job_name,
                    "vmid": vmid,
                    "datastore": datastore,
                    "retention": retention,
                },
            )
        )


if __name__ == "__main__":
    unittest.main()
