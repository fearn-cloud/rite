import datetime as dt
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from fortress_restore_drill.execute import execute_restore_drill
from fortress_restore_drill.plan import (
    RestoredDrillVmPlan,
    RestoreDrillPlan,
    SelectedRestorePoint,
    restore_drill_plan_to_dict,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


class RestoreDrillExecutionTests(unittest.TestCase):
    def test_executes_approved_plan_restores_verifies_and_cleans_up_by_default(self):
        plan = self._plan()
        client = FakeRestoreDrillClient()

        result = execute_restore_drill(plan, client)

        self.assertTrue(result.success)
        self.assertEqual(
            [
                (
                    "restore",
                    {
                        "snapshot_id": "pbs:vm/1103/2026-06-03T03:30:00Z",
                        "vm_name": "restored-drill-media-vm",
                        "placement": {"host": "wintermute", "storage": "local-zfs"},
                        "network": "drill-network",
                        "preserve_production_secrets": True,
                        "access": "operator_only",
                    },
                ),
                ("verify", {"vm_name": "restored-drill-media-vm"}),
                ("destroy", {"vm_name": "restored-drill-media-vm"}),
            ],
            client.calls,
        )
        self.assertIn("Restore Drill verification passed", result.render())
        self.assertIn("not production Service health", result.render())

    def test_successful_restore_drill_cleanup_can_be_kept_only_by_explicit_request(self):
        plan = self._plan()
        client = FakeRestoreDrillClient()

        result = execute_restore_drill(plan, client, keep_on_success=True)

        self.assertTrue(result.success)
        self.assertNotIn(("destroy", {"vm_name": "restored-drill-media-vm"}), client.calls)
        self.assertIn("Restored Drill VM preserved by explicit request", result.render())

    def test_failed_restore_drill_cleans_up_by_default(self):
        plan = self._plan()
        client = FakeRestoreDrillClient(fail_on="verify")

        result = execute_restore_drill(plan, client)

        self.assertFalse(result.success)
        self.assertEqual(
            [
                (
                    "restore",
                    {
                        "snapshot_id": "pbs:vm/1103/2026-06-03T03:30:00Z",
                        "vm_name": "restored-drill-media-vm",
                        "placement": {"host": "wintermute", "storage": "local-zfs"},
                        "network": "drill-network",
                        "preserve_production_secrets": True,
                        "access": "operator_only",
                    },
                ),
                ("verify", {"vm_name": "restored-drill-media-vm"}),
                ("destroy", {"vm_name": "restored-drill-media-vm"}),
            ],
            client.calls,
        )
        self.assertIn("Restore Drill failed during verification", result.render())
        self.assertIn("Restored Drill VM destroyed", result.render())

    def test_failed_restore_drill_keep_on_fail_preserves_artifacts(self):
        plan = self._plan()
        client = FakeRestoreDrillClient(fail_on="verify")

        result = execute_restore_drill(plan, client, keep_on_fail=True)

        self.assertFalse(result.success)
        self.assertNotIn(("destroy", {"vm_name": "restored-drill-media-vm"}), client.calls)
        self.assertIn("keep-on-fail preserved Restored Drill VM", result.render())

    def test_execution_fails_closed_when_plan_would_expose_production_boundaries(self):
        scenarios = [
            ("production_ingress", "enabled"),
            ("production_dns", "enabled"),
            ("production_nas_mutation", "enabled"),
        ]
        for field, value in scenarios:
            with self.subTest(field=field):
                plan = self._plan(**{field: value})
                client = FakeRestoreDrillClient()

                result = execute_restore_drill(plan, client)

                self.assertFalse(result.success)
                self.assertEqual([], client.calls)
                self.assertIn("Restore Drill containment refused", result.render())

    def test_execution_requires_operator_only_access_for_restored_secrets(self):
        plan = self._plan(access="lan")
        client = FakeRestoreDrillClient()

        result = execute_restore_drill(plan, client)

        self.assertFalse(result.success)
        self.assertEqual([], client.calls)
        self.assertIn("operator-only access", result.render())

    def test_operator_script_executes_plan_json_with_fake_client_and_keep_on_fail(self):
        plan = self._plan()
        with tempfile.TemporaryDirectory() as tmp:
            plan_path = Path(tmp) / "plan.json"
            log_path = Path(tmp) / "calls.json"
            plan_path.write_text(json.dumps(restore_drill_plan_to_dict(plan)))
            env = os.environ.copy()
            env["FORTRESS_TEST_RESTORE_DRILL_LOG"] = str(log_path)
            env["FORTRESS_TEST_RESTORE_DRILL_FAIL_ON"] = "verify"

            result = subprocess.run(
                [
                    str(REPO_ROOT / "scripts" / "restore-drill-execute"),
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
            self.assertIn("keep-on-fail preserved Restored Drill VM", result.stdout)
            self.assertEqual(["restore", "verify"], [call["method"] for call in json.loads(log_path.read_text())])

    def test_just_restore_drill_execute_calls_workflow_script(self):
        justfile = (REPO_ROOT / "justfile").read_text()

        self.assertIn("restore-drill-execute plan_json keep_on_fail=\"false\":", justfile)
        self.assertIn("./scripts/restore-drill-execute --plan-json {{plan_json}}", justfile)
        self.assertIn("--keep-on-fail", justfile)

    def _plan(self, **overrides):
        values = {
            "workflow_family": "restore-drill",
            "backup_target_vm_name": "media-vm",
            "restore_point": SelectedRestorePoint(
                backup_target_vm_name="media-vm",
                snapshot_id="pbs:vm/1103/2026-06-03T03:30:00Z",
                completed_at=dt.datetime(2026, 6, 3, 3, 30, tzinfo=dt.timezone.utc),
            ),
            "restored_vm": RestoredDrillVmPlan(
                name="restored-drill-media-vm",
                lifecycle="generated_disposable",
                placement={"host": "wintermute", "storage": "local-zfs"},
                network="drill-network",
            ),
            "production_ingress": "disabled",
            "production_dns": "disabled",
            "production_nas_mutation": "disabled",
            "protected_nas_datasets": ("media",),
            "access": "operator_only",
            "access_reason": "restored production secrets may be present",
        }
        values.update(overrides)
        return RestoreDrillPlan(**values)


class FakeRestoreDrillClient:
    def __init__(self, fail_on=None):
        self.calls = []
        self.fail_on = fail_on

    def restore_drill_vm(self, **kwargs):
        if self.fail_on == "restore":
            raise RuntimeError("restore failed")
        self.calls.append(("restore", kwargs))

    def verify_drill_vm(self, *, vm_name):
        self.calls.append(("verify", {"vm_name": vm_name}))
        if self.fail_on == "verify":
            raise RuntimeError("verification failed")

    def destroy_drill_vm(self, *, vm_name):
        self.calls.append(("destroy", {"vm_name": vm_name}))
        if self.fail_on == "destroy":
            raise RuntimeError("destroy failed")


if __name__ == "__main__":
    unittest.main()
