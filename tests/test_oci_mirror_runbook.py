import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


class OciMirrorRunbookTests(unittest.TestCase):
    def test_runbook_covers_lifecycle_verification_and_disposable_cache_recovery(self):
        runbook = (REPO_ROOT / "runbooks" / "oci-mirror.md").read_text()

        for required_text in (
            "scripts/oci-mirror-acceptance",
            "just service-deploy oci-mirror",
            "just service-update oci-mirror",
            "systemctl restart fortress-oci-mirror-zot",
            "cold-cache",
            "https://oci.fearn.cloud/v2/",
            "Zot UI",
            "Grafana",
            "previous pinned image and configuration",
            "cache contents as durable state",
        ):
            self.assertIn(required_text, runbook)

    def test_acceptance_script_checks_retention_refill_and_observability(self):
        script = (REPO_ROOT / "scripts" / "oci-mirror-acceptance").read_text()

        for required_text in (
            "retention",
            "mostRecentlyPulledCount",
            "runbooks/oci-mirror.md",
            "/metrics",
            "curl --fail",
        ):
            self.assertIn(required_text, script)
