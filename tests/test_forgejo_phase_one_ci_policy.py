import re
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


class ForgejoPhaseOneCiPolicyTests(unittest.TestCase):
    def test_first_validation_workflow_runs_on_declared_runner_label(self):
        runner_inventory = (REPO_ROOT / "inventory" / "vms" / "forgejo-runner-vm.yaml").read_text()
        workflow = (REPO_ROOT / ".forgejo" / "workflows" / "validation.yaml").read_text()
        labels_match = re.search(r'labels:\s*\["([^"]+)"\]', runner_inventory)

        self.assertIsNotNone(labels_match)
        self.assertEqual("debian-13:docker://debian:13", labels_match.group(1))
        self.assertIn(f"runs-on: {labels_match.group(1)}", workflow)

    def test_first_validation_workflow_is_meaningful_repo_validation(self):
        workflow = (REPO_ROOT / ".forgejo" / "workflows" / "validation.yaml").read_text()

        self.assertIn("python3 -m fortress_inventory.validate_inventory .", workflow)
        self.assertIn("python3 -m unittest tests.test_forgejo_inventory tests.test_forgejo_phase_one_ci_policy", workflow)

    def test_runbook_explains_how_to_trigger_and_inspect_first_validation_workflow(self):
        runbook = (REPO_ROOT / "runbooks" / "forgejo-runners.md").read_text()

        required_phrases = [
            ".forgejo/workflows/validation.yaml",
            "debian-13:docker://debian:13",
            "Actions",
            "Run workflow",
            "Repository validation",
            "runner registration and service health",
        ]
        for phrase in required_phrases:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, runbook)

    def test_runner_is_not_added_as_sops_age_recipient(self):
        recipient_surfaces = [
            REPO_ROOT / "age" / "recipients.txt",
            REPO_ROOT / ".sops.yaml",
        ]
        recipient_text = "\n".join(path.read_text() for path in recipient_surfaces)
        age_material_paths = [path.relative_to(REPO_ROOT).as_posix() for path in (REPO_ROOT / "age").rglob("*")]
        age_recipients = [
            line.strip()
            for line in (REPO_ROOT / "age" / "recipients.txt").read_text().splitlines()
            if line.strip().startswith("age1")
        ]

        self.assertLessEqual(len(age_recipients), 2)
        self.assertNotRegex(recipient_text.lower(), r"forgejo[-_ ]?runner|ci[-_ ]?runner")
        self.assertNotRegex("\n".join(age_material_paths).lower(), r"forgejo[-_ ]?runner|ci[-_ ]?runner")

    def test_docs_describe_phase_one_validation_boundary_and_later_deployment_design(self):
        docs = "\n".join(
            [
                (REPO_ROOT / "docs" / "adr" / "0045-forgejo-runners-use-a-dedicated-vm-native-runner-and-podman.md").read_text(),
                (REPO_ROOT / "runbooks" / "forgejo-runners.md").read_text(),
                (REPO_ROOT / "docs" / "architecture.md").read_text(),
            ]
        )

        required_phrases = [
            "phase-one Forgejo Actions are limited to non-mutating repository validation",
            "Runner VM is not an age Recipient",
            "does not decrypt Fortress SOPS secrets",
            "Host, VM, NAS, PBS, and Service convergence remains Operator-owned",
            "labels describe validation capabilities only",
            "Deployment runners require a separate later design",
        ]
        for phrase in required_phrases:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, docs)

    def test_phase_one_workflows_do_not_expose_container_runtime_or_management_commands(self):
        workflow_roots = [
            REPO_ROOT / ".forgejo",
            REPO_ROOT / ".gitea",
            REPO_ROOT / ".github" / "workflows",
        ]
        workflow_files = [
            path
            for root in workflow_roots
            if root.exists()
            for path in root.rglob("*")
            if path.is_file() and path.suffix in {".yaml", ".yml"}
        ]
        workflow_text = "\n".join(path.read_text() for path in workflow_files)

        forbidden_patterns = [
            r"/var/run/docker\.sock",
            r"/run/podman/podman\.sock",
            r"podman\.sock",
            r"docker\.sock",
            r"\bjust\s+(host|vm|service|nas|backup|instrumentation)-",
            r"\bscripts/(host|vm|service|nas|backup|instrumentation)-",
            r"\bsops\s+--decrypt\b",
            r"\bsops\s+-d\b",
        ]
        for pattern in forbidden_patterns:
            with self.subTest(pattern=pattern):
                self.assertIsNone(re.search(pattern, workflow_text))


if __name__ == "__main__":
    unittest.main()
