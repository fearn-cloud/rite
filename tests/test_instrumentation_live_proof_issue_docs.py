import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


class InstrumentationLiveProofIssueDocsTests(unittest.TestCase):
    def test_live_proof_issue_records_operator_checks_without_claiming_completion(self):
        content = (
            REPO_ROOT
            / ".scratch"
            / "instrumentation"
            / "issues"
            / "08-live-proof-instrumentation-convergence.md"
        ).read_text()

        for phrase in [
            "Live proof checklist",
            "just instrumentation-converge",
            "real ordinary VMs",
            "Prometheus target health",
            "node exporter",
            "Grafana Alloy",
            "Loki",
            "Service Telemetry Target",
            "opted-out VM",
            "Do not mark the live proof acceptance criteria complete",
        ]:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, content)

    def test_live_proof_issue_records_live_only_caveats(self):
        content = (
            REPO_ROOT
            / ".scratch"
            / "instrumentation"
            / "issues"
            / "08-live-proof-instrumentation-convergence.md"
        ).read_text()

        for phrase in [
            "Live-only caveats",
            "firewall",
            "VLAN",
            "operator credentials",
            "Observability Service",
            "scrape interval",
            "safe opt-out candidate",
        ]:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, content)


if __name__ == "__main__":
    unittest.main()
