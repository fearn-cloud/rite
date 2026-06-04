import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from fortress_acceptance.pbs_backup_restore import (
    AcceptanceVmPlan,
    PbsBackupRestoreAcceptancePlan,
    execute_pbs_backup_restore_acceptance,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


class AcceptancePbsBackupRestoreWorkflowTests(unittest.TestCase):
    def test_fake_live_client_proves_backup_restore_marker_and_cleans_up_by_default(self):
        plan = self._plan()
        client = FakePbsAcceptanceClient()

        result = execute_pbs_backup_restore_acceptance(plan, client)

        self.assertTrue(result.success)
        self.assertEqual(
            [
                ("create_source_vm", {"vm_name": "tmp-pbs-source", "vmid": 8931, "template": "debian-13-base"}),
                ("write_marker", {"vm_name": "tmp-pbs-source", "path": "/var/lib/fortress/pbs-acceptance-marker.txt", "value": "fortress-pbs-acceptance:tmp-pbs-source:8931"}),
                ("reconcile_backup_job", {"job_name": "fortress-backup-tmp-pbs-source-acceptance", "vmid": 8931, "datastore": "pbs-datastore"}),
                ("trigger_backup_run", {"job_name": "fortress-backup-tmp-pbs-source-acceptance", "vmid": 8931}),
                ("wait_successful_restore_point", {"vm_name": "tmp-pbs-source", "vmid": 8931}),
                ("restore_vm", {"snapshot_id": "pbs:vm/8931/2026-06-04T03:30:00Z", "vm_name": "tmp-pbs-restored", "vmid": 8932, "access": "operator_only"}),
                ("verify_marker", {"vm_name": "tmp-pbs-restored", "path": "/var/lib/fortress/pbs-acceptance-marker.txt", "value": "fortress-pbs-acceptance:tmp-pbs-source:8931"}),
                ("destroy_vm", {"vm_name": "tmp-pbs-restored"}),
                ("delete_backup_job", {"job_name": "fortress-backup-tmp-pbs-source-acceptance"}),
                ("destroy_vm", {"vm_name": "tmp-pbs-source"}),
                ("cleanup_generated_inventory", {"artifact_names": ["tmp-pbs-restored", "tmp-pbs-source"]}),
            ],
            client.calls,
        )
        rendered = result.render()
        self.assertIn("PBS backup/restore Acceptance Test passed", rendered)
        self.assertIn("Trigger submission is not proven backup protection", rendered)
        self.assertIn("not Backup Readiness, Backup Health, or production Restore Drill", rendered)

    def test_failed_marker_verification_cleans_up_by_default_or_preserves_on_keep_on_fail(self):
        for keep_on_fail, expected_cleanup, expected_message in [
            (False, ["destroy_vm", "delete_backup_job", "destroy_vm", "cleanup_generated_inventory"], "cleanup completed"),
            (True, [], "keep-on-fail preserved generated PBS acceptance artifacts"),
        ]:
            with self.subTest(keep_on_fail=keep_on_fail):
                client = FakePbsAcceptanceClient(fail_on="verify_marker")

                result = execute_pbs_backup_restore_acceptance(self._plan(), client, keep_on_fail=keep_on_fail)

                self.assertFalse(result.success)
                self.assertEqual(expected_cleanup, [method for method, _ in client.calls[7:]])
                self.assertIn(expected_message, result.render())

    def test_refuses_to_collide_with_production_vm_identity_or_backup_job(self):
        scenarios = [
            {"production_vm_names": ("tmp-pbs-restored",)},
            {"production_backup_job_names": ("fortress-backup-tmp-pbs-source-acceptance",)},
        ]
        for overrides in scenarios:
            with self.subTest(overrides=overrides):
                client = FakePbsAcceptanceClient()
                result = execute_pbs_backup_restore_acceptance(self._plan(**overrides), client)

                self.assertFalse(result.success)
                self.assertEqual([], client.calls)
                self.assertIn("PBS backup/restore Acceptance containment refused", result.render())

    def test_operator_script_executes_fake_client_and_keep_on_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            plan_path = Path(tmp) / "plan.json"
            log_path = Path(tmp) / "calls.json"
            plan_path.write_text(json.dumps(self._plan().to_dict()))
            env = os.environ.copy()
            env["FORTRESS_TEST_PBS_ACCEPTANCE_LOG"] = str(log_path)
            env["FORTRESS_TEST_PBS_ACCEPTANCE_FAIL_ON"] = "verify_marker"

            result = subprocess.run(
                [
                    str(REPO_ROOT / "scripts" / "acceptance-pbs-backup-restore"),
                    "--plan-json",
                    str(plan_path),
                    "--keep-on-fail",
                ],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            self.assertEqual(1, result.returncode)
            self.assertIn("keep-on-fail preserved generated PBS acceptance artifacts", result.stdout)
            self.assertEqual(
                ["create_source_vm", "write_marker", "reconcile_backup_job", "trigger_backup_run", "wait_successful_restore_point", "restore_vm", "verify_marker"],
                [call["method"] for call in json.loads(log_path.read_text())],
            )

    def test_operator_script_without_fake_client_fails_closed_until_live_backend_exists(self):
        with tempfile.TemporaryDirectory() as tmp:
            plan_path = Path(tmp) / "plan.json"
            plan_path.write_text(json.dumps(self._plan().to_dict()))

            result = subprocess.run(
                [
                    str(REPO_ROOT / "scripts" / "acceptance-pbs-backup-restore"),
                    "--plan-json",
                    str(plan_path),
                ],
                cwd=REPO_ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            self.assertEqual(1, result.returncode)
            self.assertIn("live PBS acceptance backend is not implemented", result.stdout)
            self.assertIn("Trigger submission is not proven backup protection", result.stdout)

    def test_just_recipe_and_acceptance_policy_are_declared(self):
        justfile = (REPO_ROOT / "justfile").read_text()
        policy = (REPO_ROOT / "inventory" / "acceptance" / "pbs-backup-restore.yaml").read_text()

        self.assertIn("acceptance-pbs-backup-restore host template auto_confirm=\"false\" keep_on_fail=\"false\":", justfile)
        self.assertIn("./scripts/acceptance-pbs-backup-restore host=", justfile)
        self.assertIn("tmp-pbs-source", policy)
        self.assertIn("tmp-pbs-restored", policy)

    def _plan(self, **overrides):
        values = {
            "host": "wintermute",
            "template": "debian-13-base",
            "source_vm": AcceptanceVmPlan("tmp-pbs-source", 8931, {"host": "wintermute", "storage": "fast"}, "10.10.0.241/24"),
            "restored_vm": AcceptanceVmPlan("tmp-pbs-restored", 8932, {"host": "wintermute", "storage": "fast"}, "isolated-acceptance"),
            "backup_job_name": "fortress-backup-tmp-pbs-source-acceptance",
            "datastore": "pbs-datastore",
            "marker_path": "/var/lib/fortress/pbs-acceptance-marker.txt",
            "marker_value": "fortress-pbs-acceptance:tmp-pbs-source:8931",
            "production_vm_names": (),
            "production_backup_job_names": (),
        }
        values.update(overrides)
        return PbsBackupRestoreAcceptancePlan(**values)


class FakePbsAcceptanceClient:
    def __init__(self, fail_on=None):
        self.calls = []
        self.fail_on = fail_on

    def create_source_vm(self, **kwargs):
        self._call("create_source_vm", kwargs)

    def write_marker(self, **kwargs):
        self._call("write_marker", kwargs)

    def reconcile_backup_job(self, **kwargs):
        self._call("reconcile_backup_job", kwargs)

    def trigger_backup_run(self, **kwargs):
        self._call("trigger_backup_run", kwargs)

    def wait_successful_restore_point(self, **kwargs):
        self._call("wait_successful_restore_point", kwargs)
        return "pbs:vm/8931/2026-06-04T03:30:00Z"

    def restore_vm(self, **kwargs):
        self._call("restore_vm", kwargs)

    def verify_marker(self, **kwargs):
        self._call("verify_marker", kwargs)

    def destroy_vm(self, **kwargs):
        self._call("destroy_vm", kwargs)

    def delete_backup_job(self, **kwargs):
        self._call("delete_backup_job", kwargs)

    def cleanup_generated_inventory(self, **kwargs):
        self._call("cleanup_generated_inventory", kwargs)

    def _call(self, method, kwargs):
        self.calls.append((method, kwargs))
        if self.fail_on == method:
            raise RuntimeError(f"{method} failed")


if __name__ == "__main__":
    unittest.main()
