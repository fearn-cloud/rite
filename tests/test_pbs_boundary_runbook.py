import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


class PbsBoundaryRunbookTests(unittest.TestCase):
    def test_runbook_documents_pbs_boundary_and_restore_drill_dataset_care(self):
        content = (REPO_ROOT / "runbooks" / "pbs-backups.md").read_text()

        for phrase in [
            "PBS",
            "Backup Target",
            "Unprotected VM",
            "Dataset",
            "Backup Readiness",
            "Backup Health",
            "PBS Restore",
            "Restore Drill",
            "VM recoverability and VM-local state",
            "NAS-backed Dataset history is not protected by PBS",
            "Restore Drill planning must warn when a Backup Target has NAS-backed Datasets",
            "recovery or drills require care",
        ]:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, content)


if __name__ == "__main__":
    unittest.main()
