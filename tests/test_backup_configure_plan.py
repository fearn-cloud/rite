import datetime as dt
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from fortress_inventory.model import InventoryModel
from fortress_inventory.backup_configure_plan import (
    ObservedBackupJob,
    plan_fleet_backup_configure,
    plan_host_backup_configure,
    render_backup_configure_plan,
)


class BackupConfigurePlanTests(unittest.TestCase):
    def test_just_backup_configure_plan_calls_workflow_script(self):
        justfile = (Path(__file__).resolve().parents[1] / "justfile").read_text()

        self.assertIn("backup-configure-plan host observed_jobs_json=\"\" output=\"text\":", justfile)
        self.assertIn("./scripts/backup-configure-plan {{host}} --output {{output}}", justfile)
        self.assertIn("--observed-jobs-json {{observed_jobs_json}}", justfile)

    def test_staggered_schedule_is_stable_and_inside_policy_band(self):
        model = self._model(
            vms={
                "media-vm": self._backup_target(vmid=1103, host="neuromancer"),
            }
        )

        first_plan = plan_host_backup_configure(model, "neuromancer", observed_jobs=[])
        second_plan = plan_host_backup_configure(model, "neuromancer", observed_jobs=[])

        self.assertEqual(first_plan.actions[0].scheduled_time, second_plan.actions[0].scheduled_time)
        self.assertGreaterEqual(first_plan.actions[0].scheduled_time, dt.time(3, 30))
        self.assertLess(first_plan.actions[0].scheduled_time, dt.time(4, 30))

    def test_host_plan_creates_one_job_per_backup_target_with_operator_fields(self):
        model = self._model(
            vms={
                "media-vm": self._backup_target(vmid=1103, host="neuromancer"),
                "download-vm": self._backup_target(vmid=1104, host="neuromancer"),
                "identity-vm": self._backup_target(vmid=1201, host="straylight"),
                "pbs-vm": {
                    "placement": {"host": "straylight"},
                    "backup": {"enabled": False, "reason": "local PBS instance"},
                    "mounts": [{"dataset": "pbs-datastore"}],
                },
            },
            datasets={"pbs-datastore": {}},
        )

        plan = plan_host_backup_configure(model, "neuromancer", observed_jobs=[])

        self.assertEqual("neuromancer", plan.host_name)
        self.assertEqual(["download-vm", "media-vm"], [action.vm_name for action in plan.actions])
        action = plan.actions[0]
        self.assertEqual("create", action.action)
        self.assertEqual(1104, action.vmid)
        self.assertEqual("default", action.policy_name)
        self.assertEqual("pbs-datastore", action.primary_datastore)
        self.assertEqual("fortress-backup-download-vm-default", action.job_name)
        self.assertIsInstance(action.scheduled_time, dt.time)

    def test_matching_fortress_owned_job_is_no_op(self):
        model = self._model(
            vms={
                "media-vm": self._backup_target(vmid=1103, host="neuromancer"),
                "pbs-vm": {
                    "placement": {"host": "straylight"},
                    "backup": {"enabled": False, "reason": "local PBS instance"},
                    "mounts": [{"dataset": "pbs-datastore"}],
                },
            },
            datasets={"pbs-datastore": {}},
        )
        desired = plan_host_backup_configure(model, "neuromancer", observed_jobs=[]).actions[0]

        plan = plan_host_backup_configure(
            model,
            "neuromancer",
            observed_jobs=[
                ObservedBackupJob(
                    name=desired.job_name,
                    vmid=desired.vmid,
                    datastore=desired.primary_datastore,
                    scheduled_time=desired.scheduled_time,
                    fortress_owned=True,
                )
            ],
        )

        self.assertEqual("no-op", plan.actions[0].action)

    def test_drifted_fortress_owned_job_is_update(self):
        model = self._model(
            vms={
                "media-vm": self._backup_target(vmid=1103, host="neuromancer"),
                "pbs-vm": {
                    "placement": {"host": "straylight"},
                    "backup": {"enabled": False, "reason": "local PBS instance"},
                    "mounts": [{"dataset": "pbs-datastore"}],
                },
            },
            datasets={"pbs-datastore": {}},
        )
        desired = plan_host_backup_configure(model, "neuromancer", observed_jobs=[]).actions[0]

        plan = plan_host_backup_configure(
            model,
            "neuromancer",
            observed_jobs=[
                ObservedBackupJob(
                    name=desired.job_name,
                    vmid=desired.vmid,
                    datastore=desired.primary_datastore,
                    scheduled_time=dt.time(2, 0),
                    fortress_owned=True,
                )
            ],
        )

        self.assertEqual("update", plan.actions[0].action)
        self.assertEqual(desired.scheduled_time, plan.actions[0].scheduled_time)

    def test_obsolete_fortress_owned_job_is_pruned(self):
        model = self._model(
            vms={
                "media-vm": self._backup_target(vmid=1103, host="neuromancer"),
                "old-vm": {
                    "vmid": 1109,
                    "placement": {"host": "neuromancer"},
                    "backup": {"enabled": False, "reason": "retired"},
                },
            }
        )

        plan = plan_host_backup_configure(
            model,
            "neuromancer",
            observed_jobs=[
                ObservedBackupJob(
                    name="fortress-backup-old-vm-default",
                    vmid=1109,
                    datastore="pbs-datastore",
                    scheduled_time=dt.time(3, 45),
                    fortress_owned=True,
                )
            ],
        )

        self.assertEqual(["create", "prune"], [action.action for action in plan.actions])
        self.assertEqual("fortress-backup-old-vm-default", plan.actions[1].job_name)

    def test_manual_pve_jobs_are_preserved_and_ignored(self):
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

        self.assertEqual([], list(plan.actions))

    def test_reports_backup_targets_pending_first_successful_backup_run(self):
        model = self._model(
            vms={
                "media-vm": self._backup_target(vmid=1103, host="neuromancer"),
                "download-vm": self._backup_target(vmid=1104, host="neuromancer"),
            }
        )

        plan = plan_host_backup_configure(
            model,
            "neuromancer",
            observed_jobs=[],
            successful_backup_runs={"download-vm"},
        )

        self.assertEqual(("media-vm",), plan.pending_first_successful_runs)

    def test_fleet_planning_iterates_hosts_as_host_scoped_plans(self):
        model = self._model(
            vms={
                "media-vm": self._backup_target(vmid=1103, host="neuromancer"),
                "identity-vm": self._backup_target(vmid=1201, host="straylight"),
            }
        )

        plans = plan_fleet_backup_configure(model, observed_jobs_by_host={"neuromancer": [], "straylight": []})

        self.assertEqual(["neuromancer", "straylight"], [plan.host_name for plan in plans])
        self.assertEqual(["media-vm"], [action.vm_name for action in plans[0].actions])
        self.assertEqual(["identity-vm"], [action.vm_name for action in plans[1].actions])

    def test_plan_only_rendering_shows_operator_review_fields(self):
        model = self._model(
            vms={
                "media-vm": self._backup_target(vmid=1103, host="neuromancer"),
                "pbs-vm": {
                    "placement": {"host": "straylight"},
                    "backup": {"enabled": False, "reason": "local PBS instance"},
                    "mounts": [{"dataset": "pbs-datastore"}],
                },
            },
            datasets={"pbs-datastore": {}},
        )
        plan = plan_host_backup_configure(model, "neuromancer", observed_jobs=[])

        rendered = render_backup_configure_plan(plan)

        self.assertIn("Backup Configure plan for Host neuromancer", rendered)
        self.assertIn("create media-vm policy=default datastore=pbs-datastore", rendered)
        self.assertIn("job=fortress-backup-media-vm-default", rendered)
        self.assertIn("scheduled=", rendered)
        self.assertIn("Pending first successful Backup Run: media-vm", rendered)
        self.assertIn(
            "Backup Policy boundary: PBS protects VM recoverability and VM-local state only.",
            rendered,
        )

    def test_operator_script_uses_observed_jobs_json_for_host_plan(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            shutil.copytree(
                Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "inventory_valid",
                root,
                dirs_exist_ok=True,
            )
            self._write_pbs_substrate(root)
            observed_path = root / "observed-jobs.json"
            observed_path.write_text(
                json.dumps(
                    {
                        "wintermute": [
                            {
                                "name": "fortress-backup-media01-default",
                                "vmid": 101,
                                "datastore": "pbs-datastore",
                                "scheduled_time": "02:00",
                                "fortress_owned": True,
                            },
                            {
                                "name": "manual-weekend-backup",
                                "vmid": 101,
                                "datastore": "pbs-datastore",
                                "scheduled_time": "01:00",
                                "fortress_owned": False,
                            },
                            {
                                "name": "fortress-backup-old-vm-default",
                                "vmid": 199,
                                "datastore": "pbs-datastore",
                                "scheduled_time": "03:45",
                                "fortress_owned": True,
                            },
                        ]
                    }
                )
            )
            env = os.environ.copy()
            env["FORTRESS_ROOT"] = str(root)

            result = subprocess.run(
                [
                    str(Path(__file__).resolve().parents[1] / "scripts" / "backup-configure-plan"),
                    "host=wintermute",
                    "--observed-jobs-json",
                    str(observed_path),
                ],
                cwd=Path(__file__).resolve().parents[1],
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            self.assertEqual(0, result.returncode, result.stderr)
            self.assertIn("update media01 policy=default datastore=pbs-datastore", result.stdout)
            self.assertIn("prune None policy=default datastore=pbs-datastore job=fortress-backup-old-vm-default", result.stdout)
            self.assertNotIn("manual-weekend-backup", result.stdout)

    def test_operator_script_can_emit_host_plan_json_for_apply(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            shutil.copytree(
                Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "inventory_valid",
                root,
                dirs_exist_ok=True,
            )
            self._write_pbs_substrate(root)
            env = os.environ.copy()
            env["FORTRESS_ROOT"] = str(root)

            result = subprocess.run(
                [
                    str(Path(__file__).resolve().parents[1] / "scripts" / "backup-configure-plan"),
                    "host=wintermute",
                    "--output",
                    "json",
                ],
                cwd=Path(__file__).resolve().parents[1],
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            self.assertEqual(0, result.returncode, result.stderr)
            rendered = json.loads(result.stdout)
            self.assertEqual("wintermute", rendered["host_name"])
            self.assertEqual("create", rendered["actions"][0]["action"])
            self.assertIn("scheduled_time", rendered["actions"][0])

    def test_operator_script_renders_fleet_as_host_scoped_plans(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            shutil.copytree(
                Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "inventory_valid",
                root,
                dirs_exist_ok=True,
            )
            self._write_pbs_substrate(root)
            env = os.environ.copy()
            env["FORTRESS_ROOT"] = str(root)

            result = subprocess.run(
                [str(Path(__file__).resolve().parents[1] / "scripts" / "backup-configure-plan"), "host=all"],
                cwd=Path(__file__).resolve().parents[1],
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            self.assertEqual(0, result.returncode, result.stderr)
            self.assertIn("Backup Configure plan for Host wintermute", result.stdout)

    def _model(self, *, vms, datasets=None):
        return InventoryModel(
            root=None,
            hosts={"neuromancer": {}, "straylight": {}},
            vms=vms,
            services={},
            datasets=datasets or {},
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

    def _backup_target(self, *, vmid, host, policy="default"):
        return {
            "vmid": vmid,
            "placement": {"host": host},
            "backup": {"enabled": True, "policy": policy},
        }

    def _write_pbs_substrate(self, root):
        (root / "inventory" / "datasets" / "pbs-datastore.yaml").write_text(
            "name: pbs-datastore\n"
            "nas: truenas\n"
            "path: /mnt/tank/pbs-datastore\n"
            "lifecycle: adopted\n"
            "owner:\n"
            "  uid: 34\n"
            "  gid: 34\n"
        )
        (root / "inventory" / "vms" / "pbs-vm.yaml").write_text(
            "vmid: 1003\n"
            "placement:\n"
            "  host: wintermute\n"
            "source:\n"
            "  template: debian-13-base\n"
            "hardware:\n"
            "  cores: 2\n"
            "  memory: 4096\n"
            "cloud_init:\n"
            "  hostname: pbs-vm\n"
            "mounts:\n"
            "  - name: pbs-datastore\n"
            "    dataset: pbs-datastore\n"
            "    protocol: nfs\n"
            "    mount_point: /mnt/nas/pbs-datastore\n"
            "    access: read_write\n"
            "backup:\n"
            "  enabled: false\n"
            "  reason: local PBS instance\n"
        )


if __name__ == "__main__":
    unittest.main()
