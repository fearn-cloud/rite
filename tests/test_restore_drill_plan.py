import datetime as dt
import os
import subprocess
import unittest
from pathlib import Path

from fortress_inventory.model import InventoryModel
from fortress_restore_drill.plan import (
    SelectedRestorePoint,
    plan_restore_drill,
    render_restore_drill_plan,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


class RestoreDrillPlanTests(unittest.TestCase):
    def test_just_restore_drill_plan_calls_workflow_script(self):
        justfile = (REPO_ROOT / "justfile").read_text()

        self.assertIn("restore-drill-plan target snapshot_id completed_at host storage:", justfile)
        self.assertIn("./scripts/restore-drill-plan --target {{target}}", justfile)
        self.assertIn("--snapshot-id {{snapshot_id}}", justfile)

    def test_restore_drill_plan_targets_selected_backup_restore_point_and_generated_disposable_vm(self):
        restore_point = SelectedRestorePoint(
            backup_target_vm_name="media-vm",
            snapshot_id="pbs:vm/1103/2026-06-03T03:30:00Z",
            completed_at=dt.datetime(2026, 6, 3, 3, 30, tzinfo=dt.timezone.utc),
        )

        plan = plan_restore_drill(
            self._model(Path("/repo")),
            restore_point,
            placement={"host": "wintermute", "storage": "local-zfs"},
        )

        self.assertEqual("restore-drill", plan.workflow_family)
        self.assertEqual("media-vm", plan.backup_target_vm_name)
        self.assertEqual("pbs:vm/1103/2026-06-03T03:30:00Z", plan.restore_point.snapshot_id)
        self.assertEqual("wintermute", plan.restored_vm.placement["host"])
        self.assertEqual("local-zfs", plan.restored_vm.placement["storage"])
        self.assertEqual("restored-drill-media-vm", plan.restored_vm.name)
        self.assertEqual("generated_disposable", plan.restored_vm.lifecycle)
        self.assertEqual("drill-network", plan.restored_vm.network)

        rendered = render_restore_drill_plan(plan)

        self.assertIn("Restore Drill plan for Backup Target media-vm", rendered)
        self.assertIn("Selected restore point: pbs:vm/1103/2026-06-03T03:30:00Z", rendered)
        self.assertNotIn("Acceptance Test", rendered)

    def test_restore_drill_plan_refuses_restore_point_for_non_backup_target(self):
        restore_point = SelectedRestorePoint(
            backup_target_vm_name="scratch-vm",
            snapshot_id="pbs:vm/1104/2026-06-03T03:30:00Z",
            completed_at=dt.datetime(2026, 6, 3, 3, 30, tzinfo=dt.timezone.utc),
        )

        with self.assertRaisesRegex(ValueError, "Restore Drill requires a Backup Target restore point"):
            plan_restore_drill(
                self._model(
                    Path("/repo"),
                    vms={
                        "scratch-vm": {
                            "vmid": 1104,
                            "placement": {"host": "neuromancer"},
                            "backup": {"enabled": False, "reason": "scratch VM"},
                        }
                    },
                    include_default_target=False,
                ),
                restore_point,
                placement={"host": "wintermute", "storage": "local-zfs"},
            )

    def test_restore_drill_plan_requires_selected_drill_placement_host(self):
        restore_point = SelectedRestorePoint(
            backup_target_vm_name="media-vm",
            snapshot_id="pbs:vm/1103/2026-06-03T03:30:00Z",
            completed_at=dt.datetime(2026, 6, 3, 3, 30, tzinfo=dt.timezone.utc),
        )

        with self.assertRaisesRegex(ValueError, "Restore Drill placement.host must select an Inventory Host"):
            plan_restore_drill(
                self._model(Path("/repo")),
                restore_point,
                placement={"host": "missing-host", "storage": "local-zfs"},
            )

    def test_restore_drill_plan_rejects_generated_vm_name_collision(self):
        restore_point = SelectedRestorePoint(
            backup_target_vm_name="media-vm",
            snapshot_id="pbs:vm/1103/2026-06-03T03:30:00Z",
            completed_at=dt.datetime(2026, 6, 3, 3, 30, tzinfo=dt.timezone.utc),
        )

        with self.assertRaisesRegex(ValueError, "Restored Drill VM identity collides with production VM"):
            plan_restore_drill(
                self._model(
                    Path("/repo"),
                    vms={
                        "restored-drill-media-vm": {
                            "vmid": 1200,
                            "placement": {"host": "wintermute"},
                            "backup": {"enabled": False, "reason": "manual test VM"},
                        }
                    },
                ),
                restore_point,
                placement={"host": "wintermute", "storage": "local-zfs"},
            )

    def test_restore_drill_plan_avoids_production_ingress_and_dns_exposure(self):
        restore_point = SelectedRestorePoint(
            backup_target_vm_name="media-vm",
            snapshot_id="pbs:vm/1103/2026-06-03T03:30:00Z",
            completed_at=dt.datetime(2026, 6, 3, 3, 30, tzinfo=dt.timezone.utc),
        )

        plan = plan_restore_drill(
            self._model(
                Path("/repo"),
                services={
                    "jellyfin": {
                        "backend": {"vm": "media-vm", "port": 8096},
                        "ingress": {"enabled": True, "hostname": "jellyfin.fearn.cloud"},
                    }
                },
            ),
            restore_point,
            placement={"host": "wintermute", "storage": "local-zfs"},
        )

        self.assertEqual("disabled", plan.production_ingress)
        self.assertEqual("disabled", plan.production_dns)
        rendered = render_restore_drill_plan(plan)
        self.assertIn("Production ingress: disabled", rendered)
        self.assertIn("Production DNS: disabled", rendered)

    def test_restore_drill_plan_avoids_mutating_production_nas_backed_datasets(self):
        restore_point = SelectedRestorePoint(
            backup_target_vm_name="media-vm",
            snapshot_id="pbs:vm/1103/2026-06-03T03:30:00Z",
            completed_at=dt.datetime(2026, 6, 3, 3, 30, tzinfo=dt.timezone.utc),
        )

        plan = plan_restore_drill(
            self._model(
                Path("/repo"),
                vms={
                    "media-vm": {
                        "vmid": 1103,
                        "placement": {"host": "neuromancer"},
                        "backup": {"enabled": True, "policy": "default"},
                        "mounts": [
                            {
                                "name": "media",
                                "dataset": "media",
                                "protocol": "nfs",
                                "mount_point": "/mnt/media",
                                "access": "read_write",
                            }
                        ],
                    }
                },
                datasets={"media": {"name": "media", "nas": "truenas", "path": "/mnt/tank/media"}},
            ),
            restore_point,
            placement={"host": "wintermute", "storage": "local-zfs"},
        )

        self.assertEqual(("media",), plan.protected_nas_datasets)
        self.assertEqual("disabled", plan.production_nas_mutation)
        self.assertIn(
            "Production NAS-backed Dataset media is not mutated by Restore Drill planning",
            plan.warnings,
        )

    def test_restore_drill_plan_warns_about_service_share_backed_volume_usage(self):
        restore_point = SelectedRestorePoint(
            backup_target_vm_name="media-vm",
            snapshot_id="pbs:vm/1103/2026-06-03T03:30:00Z",
            completed_at=dt.datetime(2026, 6, 3, 3, 30, tzinfo=dt.timezone.utc),
        )

        plan = plan_restore_drill(
            self._model(
                Path("/repo"),
                vms={
                    "media-vm": {
                        "vmid": 1103,
                        "placement": {"host": "neuromancer"},
                        "backup": {"enabled": True, "policy": "default"},
                        "mounts": [
                            {
                                "name": "media",
                                "dataset": "media",
                                "protocol": "nfs",
                                "mount_point": "/mnt/media",
                                "access": "read_write",
                            }
                        ],
                    }
                },
                services={
                    "jellyfin": {
                        "backend": {"vm": "media-vm", "port": 8096},
                        "deploy": {
                            "containers": [
                                {
                                    "name": "jellyfin",
                                    "volumes": [
                                        {"mount": "media", "source": "movies", "container": "/movies"}
                                    ],
                                }
                            ]
                        },
                    }
                },
                datasets={"media": {"name": "media", "nas": "truenas", "path": "/mnt/tank/media"}},
            ),
            restore_point,
            placement={"host": "wintermute", "storage": "local-zfs"},
        )

        self.assertEqual(("jellyfin uses Dataset media through Mount media",), plan.service_volume_warnings)
        self.assertIn(
            "Service jellyfin uses Dataset media through Mount media; Restore Drill planning does not grant write access",
            render_restore_drill_plan(plan),
        )

    def test_restore_drill_plan_makes_operator_only_access_explicit(self):
        restore_point = SelectedRestorePoint(
            backup_target_vm_name="media-vm",
            snapshot_id="pbs:vm/1103/2026-06-03T03:30:00Z",
            completed_at=dt.datetime(2026, 6, 3, 3, 30, tzinfo=dt.timezone.utc),
        )

        plan = plan_restore_drill(
            self._model(Path("/repo")),
            restore_point,
            placement={"host": "wintermute", "storage": "local-zfs"},
        )

        self.assertEqual("operator_only", plan.access)
        self.assertEqual("restored production secrets may be present", plan.access_reason)
        self.assertIn(
            "Access: operator_only because restored production secrets may be present",
            render_restore_drill_plan(plan),
        )

    def test_operator_script_renders_read_only_restore_drill_plan(self):
        with self._inventory_fixture() as root:
            env = os.environ.copy()
            env["FORTRESS_ROOT"] = str(root)

            result = subprocess.run(
                [
                    str(REPO_ROOT / "scripts" / "restore-drill-plan"),
                    "--target",
                    "media-vm",
                    "--snapshot-id",
                    "pbs:vm/1103/2026-06-03T03:30:00Z",
                    "--completed-at",
                    "2026-06-03T03:30:00+00:00",
                    "--host",
                    "wintermute",
                    "--storage",
                    "local-zfs",
                ],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            self.assertEqual(0, result.returncode, result.stderr)
            self.assertIn("Restore Drill plan for Backup Target media-vm", result.stdout)
            self.assertIn("Selected restore point: pbs:vm/1103/2026-06-03T03:30:00Z", result.stdout)
            self.assertNotIn("restore execution", result.stdout.lower())

    def _model(self, root, vms=None, include_default_target=True, services=None, datasets=None):
        return InventoryModel(
            root=root,
            hosts={"wintermute": {}},
            vms={
                **({
                    "media-vm": {
                        "vmid": 1103,
                        "placement": {"host": "neuromancer"},
                        "backup": {"enabled": True, "policy": "default"},
                    }
                } if include_default_target else {}),
                **(vms or {}),
            },
            services=services or {},
            datasets=datasets or {},
            nas_endpoints={},
            templates={},
            template_verification_policy={},
            acceptance_policies={},
            globals={},
            backup_policy_file_exists=True,
            backup_policies={"default": {}},
        )

    def _inventory_fixture(self):
        import tempfile

        class Fixture:
            def __enter__(fixture_self):
                fixture_self.tmp = tempfile.TemporaryDirectory()
                root = Path(fixture_self.tmp.name)
                (root / "inventory" / "hosts").mkdir(parents=True)
                (root / "inventory" / "vms").mkdir()
                (root / "inventory" / "hosts" / "wintermute.yaml").write_text("hostname: wintermute\n")
                (root / "inventory" / "vms" / "media-vm.yaml").write_text(
                    "vmid: 1103\n"
                    "placement:\n"
                    "  host: wintermute\n"
                    "backup:\n"
                    "  enabled: true\n"
                )
                return root

            def __exit__(fixture_self, exc_type, exc, traceback):
                fixture_self.tmp.cleanup()

        return Fixture()


if __name__ == "__main__":
    unittest.main()
