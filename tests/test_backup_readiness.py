import datetime as dt
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from fortress_inventory.backup_configure_plan import ObservedBackupJob, plan_host_backup_configure
from fortress_inventory.backup_readiness import evaluate_backup_readiness, render_backup_readiness_report
from fortress_inventory.model import InventoryModel


REPO_ROOT = Path(__file__).resolve().parents[1]


class BackupReadinessTests(unittest.TestCase):
    def test_backup_target_passes_when_all_live_prerequisites_are_satisfied(self):
        with tempfile.TemporaryDirectory() as tmp:
            model = self._model(Path(tmp))
            desired = plan_host_backup_configure(model, "neuromancer", observed_jobs=[]).actions[0]

            report = evaluate_backup_readiness(
                model,
                observed_jobs_by_host={
                    "neuromancer": [
                        ObservedBackupJob(
                            name=desired.job_name,
                            vmid=desired.vmid,
                            datastore=desired.primary_datastore,
                            scheduled_time=desired.scheduled_time,
                            fortress_owned=True,
                        )
                    ]
                },
                successful_backup_runs_by_host={"neuromancer": {"media-vm"}},
            )

            self.assertTrue(report.ready)
            self.assertEqual("ready", report.results_by_vm["media-vm"].status)
            self.assertEqual((), report.results_by_vm["media-vm"].reasons)

    def test_operator_report_warns_that_nas_backed_dataset_history_is_outside_pbs(self):
        with tempfile.TemporaryDirectory() as tmp:
            model = self._model(
                Path(tmp),
                vms={
                    "photos-vm": {
                        "vmid": 1104,
                        "placement": {"host": "neuromancer"},
                        "mounts": [
                            {"name": "library", "dataset": "photos", "mount_point": "/mnt/photos", "access": "read_write"}
                        ],
                        "backup": {"enabled": True, "policy": "default"},
                    }
                },
                datasets={
                    "pbs-datastore": {"path": "/mnt/tank/pbs-datastore"},
                    "photos": {"path": "/mnt/tank/photos"},
                },
            )
            observed = self._matching_observed_job(model, "neuromancer", "photos-vm")

            report = evaluate_backup_readiness(
                model,
                observed_jobs_by_host={"neuromancer": [observed]},
                successful_backup_runs_by_host={"neuromancer": {"photos-vm"}},
            )

        rendered = render_backup_readiness_report(report, target="photos-vm")

        self.assertIn(
            "Boundary: PBS protects VM recoverability and VM-local state only; "
            "NAS-backed Dataset history is not protected by PBS: photos.",
            rendered,
        )

    def test_unprotected_vm_is_excluded_with_operator_reason_visible(self):
        with tempfile.TemporaryDirectory() as tmp:
            model = self._model(
                Path(tmp),
                include_default_target=False,
                vms={
                    "docs-vm": {
                        "vmid": 1104,
                        "placement": {"host": "neuromancer"},
                        "backup": {"enabled": False, "reason": "ephemeral documentation mirror"},
                    }
                },
            )

            report = evaluate_backup_readiness(model)

            self.assertTrue(report.ready)
            self.assertEqual("excluded", report.results_by_vm["docs-vm"].status)
            self.assertEqual(("ephemeral documentation mirror",), report.results_by_vm["docs-vm"].reasons)

    def test_backup_target_fails_when_selected_backup_policy_is_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            model = self._model(
                Path(tmp),
                vms={
                    "media-vm": {
                        "vmid": 1103,
                        "placement": {"host": "neuromancer"},
                        "backup": {"enabled": True, "policy": "archive"},
                    }
                },
            )

            report = evaluate_backup_readiness(model)

            self.assertFalse(report.ready)
            self.assertEqual("blocked", report.results_by_vm["media-vm"].status)
            self.assertIn("Backup Policy archive is not valid", report.results_by_vm["media-vm"].reasons)

    def test_backup_target_fails_when_selected_backup_policy_is_malformed(self):
        with tempfile.TemporaryDirectory() as tmp:
            model = self._model(
                Path(tmp),
                backup_policies={"default": {"schedule": {"cadence": "weekly"}, "retention": {}}},
            )

            report = evaluate_backup_readiness(model)

            self.assertFalse(report.ready)
            self.assertIn("Backup Policy default is not valid", report.results_by_vm["media-vm"].reasons)

    def test_backup_target_fails_when_primary_datastore_path_is_not_usable(self):
        with tempfile.TemporaryDirectory() as tmp:
            model = self._model(
                Path(tmp),
                pbs_mount={
                    "dataset": "pbs-datastore",
                    "mount_point": "relative/pbs-datastore",
                    "access": "read_write",
                },
            )
            observed = self._matching_observed_job(model, "neuromancer", "media-vm")

            report = evaluate_backup_readiness(
                model,
                observed_jobs_by_host={"neuromancer": [observed]},
                successful_backup_runs_by_host={"neuromancer": {"media-vm"}},
            )

            self.assertFalse(report.ready)
            self.assertIn("Primary Datastore path is not usable for Backup Runs", report.results_by_vm["media-vm"].reasons)

    def test_backup_target_fails_when_pbs_recovery_secret_is_unavailable(self):
        with tempfile.TemporaryDirectory() as tmp:
            model = self._model(Path(tmp), write_recovery_secret=False)
            observed = self._matching_observed_job(model, "neuromancer", "media-vm")

            report = evaluate_backup_readiness(
                model,
                observed_jobs_by_host={"neuromancer": [observed]},
                successful_backup_runs_by_host={"neuromancer": {"media-vm"}},
            )

            self.assertFalse(report.ready)
            self.assertIn("PBS encryption Recovery Secret is not available", report.results_by_vm["media-vm"].reasons)

    def test_backup_target_fails_when_expected_backup_job_is_absent(self):
        with tempfile.TemporaryDirectory() as tmp:
            model = self._model(Path(tmp))

            report = evaluate_backup_readiness(
                model,
                observed_jobs_by_host={"neuromancer": []},
                successful_backup_runs_by_host={"neuromancer": {"media-vm"}},
            )

            self.assertFalse(report.ready)
            self.assertIn("Expected Backup Job is not present", report.results_by_vm["media-vm"].reasons)

    def test_backup_target_fails_until_one_successful_backup_run_exists(self):
        with tempfile.TemporaryDirectory() as tmp:
            model = self._model(Path(tmp))
            observed = self._matching_observed_job(model, "neuromancer", "media-vm")

            report = evaluate_backup_readiness(
                model,
                observed_jobs_by_host={"neuromancer": [observed]},
                successful_backup_runs_by_host={"neuromancer": set()},
            )

            self.assertFalse(report.ready)
            self.assertIn("No successful Backup Run has completed", report.results_by_vm["media-vm"].reasons)

    def test_backup_targets_are_evaluated_independently(self):
        with tempfile.TemporaryDirectory() as tmp:
            model = self._model(
                Path(tmp),
                vms={
                    "download-vm": {
                        "vmid": 1104,
                        "placement": {"host": "neuromancer"},
                        "backup": {"enabled": True, "policy": "default"},
                    }
                },
            )
            observed = self._matching_observed_job(model, "neuromancer", "media-vm")

            report = evaluate_backup_readiness(
                model,
                observed_jobs_by_host={"neuromancer": [observed]},
                successful_backup_runs_by_host={"neuromancer": {"media-vm"}},
            )

            self.assertFalse(report.ready)
            self.assertEqual("ready", report.results_by_vm["media-vm"].status)
            self.assertEqual("blocked", report.results_by_vm["download-vm"].status)
            self.assertIn("Expected Backup Job is not present", report.results_by_vm["download-vm"].reasons)

    def test_operator_script_blocks_target_that_fails_backup_readiness(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            model = self._model(root)
            observed = self._matching_observed_job(model, "neuromancer", "media-vm")
            observed_path = root / "observed-jobs.json"
            observed_path.write_text(
                json.dumps(
                    {
                        "neuromancer": [
                            {
                                "name": observed.name,
                                "vmid": observed.vmid,
                                "datastore": observed.datastore,
                                "scheduled_time": observed.scheduled_time.isoformat(timespec="minutes"),
                                "fortress_owned": observed.fortress_owned,
                            }
                        ]
                    }
                )
            )
            successful_runs_path = root / "successful-runs.json"
            successful_runs_path.write_text(json.dumps({"neuromancer": []}))
            self._write_inventory_files(root)
            env = os.environ.copy()
            env["FORTRESS_ROOT"] = str(root)

            result = subprocess.run(
                [
                    str(REPO_ROOT / "scripts" / "backup-readiness"),
                    "--target",
                    "media-vm",
                    "--observed-jobs-json",
                    str(observed_path),
                    "--successful-runs-json",
                    str(successful_runs_path),
                ],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            self.assertEqual(1, result.returncode)
            self.assertIn("Backup Readiness blocked media-vm", result.stdout)
            self.assertIn("No successful Backup Run has completed", result.stdout)

    def _model(
        self,
        root,
        vms=None,
        include_default_target=True,
        backup_policies=None,
        pbs_mount=None,
        write_recovery_secret=True,
        datasets=None,
    ):
        (root / "inventory" / "vms").mkdir(parents=True)
        if write_recovery_secret:
            (root / "inventory" / "vms" / "pbs-vm.sops.yaml").write_text(
                "recovery_secrets:\n"
                "  pbs_encryption_key:\n"
                "    value: encrypted\n"
            )
        return InventoryModel(
            root=root,
            hosts={"neuromancer": {}, "straylight": {}},
            vms={
                **({
                    "media-vm": {
                        "vmid": 1103,
                        "placement": {"host": "neuromancer"},
                        "backup": {"enabled": True, "policy": "default"},
                    },
                } if include_default_target else {}),
                **(vms or {}),
                "pbs-vm": {
                    "vmid": 1003,
                    "placement": {"host": "straylight"},
                    "mounts": [
                        pbs_mount or {
                            "dataset": "pbs-datastore",
                            "mount_point": "/mnt/nas/pbs-datastore",
                            "access": "read_write",
                        }
                    ],
                    "backup": {"enabled": False, "reason": "local PBS instance"},
                },
            },
            services={},
            datasets=datasets or {"pbs-datastore": {"path": "/mnt/tank/pbs-datastore"}},
            nas_endpoints={},
            templates={},
            template_verification_policy={},
            acceptance_policies={},
            globals={},
            backup_policy_file_exists=True,
            backup_policies=backup_policies or {
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

    def _matching_observed_job(self, model, host_name, vm_name):
        desired = [
            action
            for action in plan_host_backup_configure(model, host_name, observed_jobs=[]).actions
            if action.vm_name == vm_name
        ][0]
        return ObservedBackupJob(
            name=desired.job_name,
            vmid=desired.vmid,
            datastore=desired.primary_datastore,
            scheduled_time=desired.scheduled_time,
            fortress_owned=True,
        )

    def _write_inventory_files(self, root):
        (root / "inventory" / "vms").mkdir(parents=True, exist_ok=True)
        (root / "inventory" / "datasets").mkdir(parents=True, exist_ok=True)
        (root / "inventory").mkdir(exist_ok=True)
        (root / "inventory" / "backup-policies.yaml").write_text(
            "policies:\n"
            "  default:\n"
            "    schedule:\n"
            "      cadence: daily\n"
            "      time: \"03:30\"\n"
            "      timezone: America/Denver\n"
            "      stagger: 60m\n"
            "    retention:\n"
            "      daily: 14\n"
            "      weekly: 8\n"
            "      monthly: 12\n"
        )
        (root / "inventory" / "vms" / "media-vm.yaml").write_text(
            "vmid: 1103\n"
            "placement:\n"
            "  host: neuromancer\n"
            "backup:\n"
            "  enabled: true\n"
        )
        (root / "inventory" / "vms" / "pbs-vm.yaml").write_text(
            "vmid: 1003\n"
            "placement:\n"
            "  host: straylight\n"
            "mounts:\n"
            "  - dataset: pbs-datastore\n"
            "    mount_point: /mnt/nas/pbs-datastore\n"
            "    access: read_write\n"
            "backup:\n"
            "  enabled: false\n"
            "  reason: local PBS instance\n"
        )
        (root / "inventory" / "datasets" / "pbs-datastore.yaml").write_text(
            "path: /mnt/tank/pbs-datastore\n"
        )


if __name__ == "__main__":
    unittest.main()
