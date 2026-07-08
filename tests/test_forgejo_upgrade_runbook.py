import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


class ForgejoUpgradeRunbookTests(unittest.TestCase):
    def test_runbook_documents_current_to_latest_upgrade_path(self):
        content = (REPO_ROOT / "runbooks" / "forgejo-upgrade.md").read_text()

        for phrase in [
            "codeberg.org/forgejo/forgejo:11.0.1",
            "15.0.3",
            "2026-07-08",
            "Upgrade, not a routine Service Update",
            "upgrade directly from `11.0.1` to `15.0.3`",
            "Fallback path",
            "customized templates, CSS, or public content",
            "configuration tab in the Forgejo Site administration panel",
            "Git `>= 2.34.1`",
            "Forgejo Actions",
            "URL query API authentication",
            "`POST /repos/{owner}/{repo}/contents` now requires the documented `sha`",
            "`GET /api/v1/admin/hooks` is paginated",
            "repository access failures from `403` to `404`",
            "DISABLE_QUERY_AUTH_TOKEN",
            "rootless",
            "`forgejo docs`",
            "CLI errors from stdout to",
            "authorized_keys",
            "forked `.profile` repositories",
            "ADD_CO_COMMITTER_TRAILERS",
            "gitea_incredible",
            "doctor avatar-strip-exif",
            "forgejo manager flush-queues",
            "Backup Gate",
            "just service-update forgejo",
            "fortress-forgejo-server.service",
            "forgejo doctor check --all",
            "https://git.fearn.cloud/",
            "port `2222`",
            "restore the pre-upgrade VM snapshot",
        ]:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, content)

    def test_runbook_links_primary_sources(self):
        content = (REPO_ROOT / "runbooks" / "forgejo-upgrade.md").read_text()

        for url in [
            "https://forgejo.org/releases/",
            "https://forgejo.org/releases/15.x/",
            "https://forgejo.org/docs/v15.0/admin/upgrade/",
            "https://forgejo.org/2026-04-release-v15-0/",
            "release-notes-published/12.0.0.md",
            "release-notes-published/13.0.0.md",
            "release-notes-published/14.0.0.md",
            "release-notes-published/15.0.0.md",
        ]:
            with self.subTest(url=url):
                self.assertIn(url, content)


if __name__ == "__main__":
    unittest.main()
