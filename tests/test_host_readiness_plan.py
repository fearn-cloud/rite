import tempfile
import unittest
from pathlib import Path

from fortress_workflows import FailurePolicy
from fortress_workflows.host_readiness import build_host_readiness_plan


class HostReadinessPlanTests(unittest.TestCase):
    def test_builds_ordered_plan_with_expanded_acceptance_matrix(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._fixture(tmp)

            resolved = build_host_readiness_plan(
                repo_root=root,
                host_name="wintermute",
                endpoint_arg="all",
                auto_confirm=True,
                keep_on_fail=False,
            )

            self.assertEqual(
                [
                    "bootstrap-satisfied",
                    "host-shell",
                    "configure",
                    "templates-build",
                    "template-verify debian-13-base",
                    "template-verify ubuntu-2404-base",
                    "acceptance nfs-shared-mount debian-13-base@backup",
                    "acceptance service-layer debian-13-base@backup",
                    "acceptance nfs-shared-mount ubuntu-2404-base@backup",
                    "acceptance service-layer ubuntu-2404-base@backup",
                    "acceptance nfs-shared-mount debian-13-base@truenas",
                    "acceptance service-layer debian-13-base@truenas",
                    "acceptance nfs-shared-mount ubuntu-2404-base@truenas",
                    "acceptance service-layer ubuntu-2404-base@truenas",
                ],
                [step.id for step in resolved.plan.steps],
            )
            acceptance_steps = [step for step in resolved.plan.steps if step.id.startswith("acceptance ")]
            self.assertTrue(all(step.failure_policy == FailurePolicy.CONTINUE for step in acceptance_steps))
            self.assertIn("auto_confirm=true", " ".join(resolved.plan.steps[-1].command))
            self.assertIn("keep_on_fail=false", " ".join(resolved.plan.steps[-1].command))

    def test_keep_on_fail_makes_acceptance_cells_stop_on_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._fixture(tmp)

            resolved = build_host_readiness_plan(
                repo_root=root,
                host_name="wintermute",
                endpoint_arg="truenas",
                auto_confirm=False,
                keep_on_fail=True,
            )

            acceptance_steps = [step for step in resolved.plan.steps if step.id.startswith("acceptance ")]
            self.assertEqual(4, len(acceptance_steps))
            self.assertTrue(all(step.failure_policy == FailurePolicy.STOP for step in acceptance_steps))
            self.assertIn("endpoint=truenas", " ".join(acceptance_steps[0].command))
            self.assertIn("keep_on_fail=true", " ".join(acceptance_steps[0].command))

    def _fixture(self, tmp):
        root = Path(tmp)
        (root / "inventory" / "hosts").mkdir(parents=True)
        (root / "inventory" / "nas").mkdir(parents=True)
        (root / "inventory" / "templates").mkdir(parents=True)
        (root / "scripts").mkdir()
        (root / "inventory" / "hosts" / "wintermute.yaml").write_text(
            "proxmox:\n"
            "  templates: [debian-13-base, ubuntu-2404-base]\n"
        )
        (root / "inventory" / "hosts" / "wintermute.sops.yaml").write_text("encrypted\n")
        (root / "inventory" / "nas" / "backup.yaml").write_text("management_address: 10.10.0.12\n")
        (root / "inventory" / "nas" / "truenas.yaml").write_text("management_address: 10.10.0.10\n")
        (root / "inventory" / "templates" / "debian-13-base.yaml").write_text("vmid: 9001\n")
        (root / "inventory" / "templates" / "ubuntu-2404-base.yaml").write_text("vmid: 9002\n")
        return root


if __name__ == "__main__":
    unittest.main()
