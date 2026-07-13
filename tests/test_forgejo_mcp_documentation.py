from pathlib import Path
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]


class ForgejoMcpDocumentationTests(unittest.TestCase):
    def test_runbook_documents_endpoint_per_client_tokens_and_runner_boundary(self):
        runbook = (REPO_ROOT / "runbooks" / "forgejo-mcp.md").read_text()
        normalized_runbook = " ".join(runbook.split())

        for phrase in (
            "https://mcp.git.fearn.cloud/mcp",
            "Streamable HTTP",
            "no global Forgejo token",
            "separate least-privilege token for each repository/client pair",
            ".env/forgejo-mcp/<repository>.env",
            "The Forgejo Runner is not the MCP runtime.",
            "does not give the Runner a Forgejo API token, deployment credentials, SOPS access",
            "not in the Service Directory",
        ):
            self.assertIn(" ".join(phrase.split()), normalized_runbook)

    def test_firewall_matrix_matches_forgejo_client_reachability(self):
        matrix = (REPO_ROOT / "docs" / "firewall-matrix.md").read_text()

        self.assertIn("MCP-001-ALLOW-TRUSTED-FORGEJO-MCP", matrix)
        self.assertIn("reachability matches Forgejo clients", matrix)
