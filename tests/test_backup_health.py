import datetime as dt
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from fortress_inventory.backup_health import (
    RestorePointFact,
    evaluate_backup_health,
    render_backup_health_report,
)
from fortress_inventory.model import InventoryModel


REPO_ROOT = Path(__file__).resolve().parents[1]


class BackupHealthTests(unittest.TestCase):
    def test_just_backup_health_calls_workflow_script(self):
        justfile = (REPO_ROOT / "justfile").read_text()

        self.assertIn("backup-health restore_points_json now target=\"\":", justfile)
        self.assertIn("./scripts/backup-health --restore-points-json {{restore_points_json}} --now {{now}}", justfile)
        self.assertIn("--target {{target}}", justfile)

    def test_backup_target_is_healthy_when_restore_point_is_fresh(self):
        now = dt.datetime(2026, 6, 3, 12, 0, tzinfo=dt.timezone.utc)
        model = self._model(Path(tempfile.mkdtemp()))

        report = evaluate_backup_health(
            model,
            restore_points=[
                RestorePointFact(
                    vm_name="media-vm",
                    completed_at=now - dt.timedelta(hours=12),
                    successful=True,
                )
            ],
            now=now,
        )

        self.assertEqual("healthy", report.targets_by_vm["media-vm"].status)
        self.assertEqual((), report.targets_by_vm["media-vm"].reasons)

    def test_operator_report_warns_health_does_not_prove_dataset_point_in_time_consistency(self):
        now = dt.datetime(2026, 6, 3, 12, 0, tzinfo=dt.timezone.utc)
        model = self._model(
            Path(tempfile.mkdtemp()),
            include_default_target=False,
            vms={
                "app-vm": {
                    "vmid": 1104,
                    "placement": {"host": "neuromancer"},
                    "mounts": [
                        {"name": "data", "dataset": "app-data", "mount_point": "/mnt/app-data", "access": "read_write"}
                    ],
                    "backup": {"enabled": True, "policy": "default"},
                }
            },
            datasets={"app-data": {"path": "/mnt/tank/app-data"}},
        )

        report = evaluate_backup_health(
            model,
            restore_points=[
                RestorePointFact(
                    vm_name="app-vm",
                    completed_at=now - dt.timedelta(hours=2),
                    successful=True,
                )
            ],
            now=now,
        )

        rendered = render_backup_health_report(report, target="app-vm")

        self.assertIn(
            "Boundary: Backup Health checks PBS restore-point freshness only; "
            "it does not prove point-in-time consistency with NAS-backed Datasets: app-data.",
            rendered,
        )

    def test_default_backup_target_is_unhealthy_after_36_hours_without_fresh_restore_point(self):
        now = dt.datetime(2026, 6, 3, 12, 0, tzinfo=dt.timezone.utc)
        model = self._model(Path(tempfile.mkdtemp()))

        report = evaluate_backup_health(
            model,
            restore_points=[
                RestorePointFact(
                    vm_name="media-vm",
                    completed_at=now - dt.timedelta(hours=37),
                    successful=True,
                )
            ],
            now=now,
        )

        self.assertEqual("unhealthy", report.targets_by_vm["media-vm"].status)
        self.assertEqual(
            ("Latest successful restore point is older than 36 hours",),
            report.targets_by_vm["media-vm"].reasons,
        )

    def test_backup_target_is_unhealthy_when_restore_point_is_missing(self):
        now = dt.datetime(2026, 6, 3, 12, 0, tzinfo=dt.timezone.utc)
        model = self._model(Path(tempfile.mkdtemp()))

        report = evaluate_backup_health(model, restore_points=[], now=now)

        self.assertEqual("unhealthy", report.targets_by_vm["media-vm"].status)
        self.assertEqual(
            ("No successful restore point found",),
            report.targets_by_vm["media-vm"].reasons,
        )

    def test_host_rollup_summarizes_backup_target_statuses(self):
        now = dt.datetime(2026, 6, 3, 12, 0, tzinfo=dt.timezone.utc)
        model = self._model(
            Path(tempfile.mkdtemp()),
            vms={
                "download-vm": {
                    "vmid": 1104,
                    "placement": {"host": "neuromancer"},
                    "backup": {"enabled": True, "policy": "default"},
                }
            },
        )

        report = evaluate_backup_health(
            model,
            restore_points=[
                RestorePointFact(
                    vm_name="media-vm",
                    completed_at=now - dt.timedelta(hours=12),
                    successful=True,
                )
            ],
            now=now,
        )

        rollup = report.hosts_by_name["neuromancer"]
        self.assertEqual("unhealthy", rollup.status)
        self.assertEqual(1, rollup.healthy_count)
        self.assertEqual(1, rollup.unhealthy_count)
        self.assertEqual(0, rollup.excluded_count)

    def test_fleet_rollup_summarizes_all_hosts(self):
        now = dt.datetime(2026, 6, 3, 12, 0, tzinfo=dt.timezone.utc)
        model = self._model(
            Path(tempfile.mkdtemp()),
            hosts={"neuromancer": {}, "straylight": {}},
            vms={
                "identity-vm": {
                    "vmid": 1105,
                    "placement": {"host": "straylight"},
                    "backup": {"enabled": True, "policy": "default"},
                }
            },
        )

        report = evaluate_backup_health(
            model,
            restore_points=[
                RestorePointFact(
                    vm_name="media-vm",
                    completed_at=now - dt.timedelta(hours=12),
                    successful=True,
                )
            ],
            now=now,
        )

        self.assertEqual("unhealthy", report.fleet.status)
        self.assertEqual(1, report.fleet.healthy_count)
        self.assertEqual(1, report.fleet.unhealthy_count)
        self.assertEqual(0, report.fleet.excluded_count)

    def test_unprotected_vm_is_excluded_with_reason_visible(self):
        now = dt.datetime(2026, 6, 3, 12, 0, tzinfo=dt.timezone.utc)
        model = self._model(
            Path(tempfile.mkdtemp()),
            include_default_target=False,
            vms={
                "pbs-vm": {
                    "vmid": 1003,
                    "placement": {"host": "neuromancer"},
                    "backup": {
                        "enabled": False,
                        "reason": "local PBS instance is rebuilt from Inventory and Recovery Secrets",
                    },
                }
            },
        )

        report = evaluate_backup_health(model, restore_points=[], now=now)

        self.assertEqual("excluded", report.targets_by_vm["pbs-vm"].status)
        self.assertEqual(
            ("local PBS instance is rebuilt from Inventory and Recovery Secrets",),
            report.targets_by_vm["pbs-vm"].reasons,
        )
        self.assertEqual(1, report.hosts_by_name["neuromancer"].excluded_count)
        self.assertEqual(1, report.fleet.excluded_count)

    def test_operator_report_renders_target_host_and_fleet_health(self):
        now = dt.datetime(2026, 6, 3, 12, 0, tzinfo=dt.timezone.utc)
        model = self._model(
            Path(tempfile.mkdtemp()),
            vms={
                "download-vm": {
                    "vmid": 1104,
                    "placement": {"host": "neuromancer"},
                    "backup": {"enabled": False, "reason": "scratch VM"},
                }
            },
        )
        report = evaluate_backup_health(model, restore_points=[], now=now)

        rendered = render_backup_health_report(report)

        self.assertIn("Fleet Backup Health unhealthy healthy=0 unhealthy=1 excluded=1", rendered)
        self.assertIn("Host neuromancer unhealthy healthy=0 unhealthy=1 excluded=1", rendered)
        self.assertIn("Backup Target media-vm unhealthy", rendered)
        self.assertIn("- No successful restore point found", rendered)
        self.assertIn("Unprotected VM download-vm excluded: scratch VM", rendered)

    def test_operator_script_reports_unhealthy_target_from_restore_point_facts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_inventory_files(root)
            restore_points_path = root / "restore-points.json"
            restore_points_path.write_text(
                json.dumps(
                    [
                        {
                            "vm_name": "media-vm",
                            "completed_at": "2026-06-01T12:00:00+00:00",
                            "successful": True,
                        }
                    ]
                )
            )
            env = os.environ.copy()
            env["FORTRESS_ROOT"] = str(root)

            result = subprocess.run(
                [
                    str(REPO_ROOT / "scripts" / "backup-health"),
                    "--target",
                    "media-vm",
                    "--restore-points-json",
                    str(restore_points_path),
                    "--now",
                    "2026-06-03T12:00:00+00:00",
                ],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            self.assertEqual(1, result.returncode)
            self.assertIn("Backup Target media-vm unhealthy", result.stdout)
            self.assertIn("Latest successful restore point is older than 36 hours", result.stdout)

    def _model(self, root, hosts=None, vms=None, include_default_target=True, datasets=None):
        return InventoryModel(
            root=root,
            hosts=hosts or {"neuromancer": {}},
            vms={
                **({
                    "media-vm": {
                        "vmid": 1103,
                        "placement": {"host": "neuromancer"},
                        "backup": {"enabled": True, "policy": "default"},
                    },
                } if include_default_target else {}),
                **(vms or {}),
            },
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

    def _write_inventory_files(self, root):
        (root / "inventory" / "vms").mkdir(parents=True)
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
        (root / "inventory" / "hosts").mkdir()
        (root / "inventory" / "hosts" / "neuromancer.yaml").write_text("hostname: neuromancer\n")
        (root / "inventory" / "vms" / "media-vm.yaml").write_text(
            "vmid: 1103\n"
            "placement:\n"
            "  host: neuromancer\n"
            "backup:\n"
            "  enabled: true\n"
        )


if __name__ == "__main__":
    unittest.main()
