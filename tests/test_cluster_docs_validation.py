import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = REPO_ROOT / "scripts" / "validate-cluster-docs"


class ClusterDocsValidationTests(unittest.TestCase):
    def test_migration_keeps_canon_material_and_declared_authority_boundary_available(self):
        overview = (REPO_ROOT / "docs" / "cluster" / "README.md").read_text()
        glossary = (REPO_ROOT / "CONTEXT.md").read_text()
        adr = (
            REPO_ROOT
            / "docs"
            / "adr"
            / "0046-canon-cluster-authority-is-separate-from-substrate-authority.md"
        ).read_text()

        for path in [
            "research/cluster-supply-manifest-standards.md",
            "research/forgejo-issue-driven-coding-agent-options.md",
            "research/rite-canon-synergy.md",
            "research/rite-controlled-lan-time-service-options.md",
            "research/single-server-k3s-datastore-recovery.md",
            "research/stateful-example-application.md",
        ]:
            with self.subTest(path=path):
                self.assertTrue((REPO_ROOT / "docs" / "cluster" / path).is_file())

        for phrase in [
            "historical [Canon repository]",
            "[glossary](../../CONTEXT.md)",
            "Cluster Desired State",
            "Substrate Inventory",
            "must not traverse provider-specific substrate implementation or raw Substrate Inventory",
            "No Cluster is required to recover itself",
            "New Cluster work is planned and tracked in [Rite]",
        ]:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, overview)

        self.assertIn("Cluster Host Requirement", glossary)
        self.assertIn("Rite owns the distinct Substrate Inventory", adr)

    def test_repository_cluster_docs_and_dependency_boundary_validate(self):
        result = subprocess.run(
            [str(VALIDATOR), "--root", str(REPO_ROOT)],
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(0, result.returncode, result.stderr)

    def test_validator_rejects_missing_migrated_document_link(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            shutil.copytree(REPO_ROOT / "docs" / "cluster", root / "docs" / "cluster")
            (root / "docs" / "cluster" / "README.md").write_text(
                "[missing research](research/not-present.md)\n"
            )

            result = subprocess.run(
                [str(VALIDATOR), "--root", str(root)],
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertNotEqual(0, result.returncode)
        self.assertIn("missing local Markdown target", result.stderr)

    def test_validator_rejects_cluster_code_reading_raw_substrate_inventory(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "docs" / "cluster").mkdir(parents=True)
            (root / "fortress_cluster").mkdir()
            (root / "fortress_cluster" / "workflow.py").write_text(
                "from fortress_inventory import load_inventory\n"
            )

            result = subprocess.run(
                [str(VALIDATOR), "--root", str(root)],
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertNotEqual(0, result.returncode)
        self.assertIn("forbidden substrate dependency", result.stderr)


if __name__ == "__main__":
    unittest.main()
