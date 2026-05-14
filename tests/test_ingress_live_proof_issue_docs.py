import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


class IngressLiveProofIssueDocsTests(unittest.TestCase):
    def test_parent_issue_reconciles_afk_implementation_and_live_human_proof(self):
        content = (
            REPO_ROOT / ".scratch" / "initial-building-blocks" / "issues" / "10-caddy-ingress-ingress-regenerator.md"
        ).read_text()

        for phrase in [
            "Split implementation reconciliation",
            "AFK implementation slices",
            "Live human proof remains in",
            "07-document-and-live-proof-ingress-regeneration-path.md",
            "real Let's Encrypt DNS-01",
            "LAN validation",
            "Trusted source",
        ]:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, content)

    def test_live_proof_issue_records_operator_caveats_without_claiming_completion(self):
        content = (
            REPO_ROOT
            / ".scratch"
            / "ingress-regeneration"
            / "issues"
            / "07-document-and-live-proof-ingress-regeneration-path.md"
        ).read_text()

        for phrase in [
            "Live proof checklist",
            "Cloudflare API token",
            "real Let's Encrypt DNS-01 certificate",
            "LAN client",
            "Trusted source",
            "non-Trusted source",
            "Do not mark the live proof acceptance criteria complete",
        ]:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, content)


if __name__ == "__main__":
    unittest.main()
