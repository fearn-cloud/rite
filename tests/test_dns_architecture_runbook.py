import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


class DNSArchitectureRunbookTests(unittest.TestCase):
    def test_runbook_documents_dns_architecture_and_operator_validation(self):
        runbook = REPO_ROOT / "runbooks" / "dns-architecture.md"

        self.assertTrue(runbook.is_file())
        content = runbook.read_text()
        expected_phrases = [
            "Pi-hole + Unbound DNS architecture",
            "two-container Quadlet Service",
            "dns-primary-vm",
            "10.40.0.11",
            "VLAN 40",
            "inventory/vms/dns-primary-vm.yaml",
            "inventory/services/dns-primary.yaml",
            "scripts/vm-up dns-primary-vm",
            "scripts/service-deploy dns-primary",
            "TCP and UDP port 53",
            "FTLCONF_dns_upstreams: unbound",
            "FTLCONF_dns_listeningMode: all",
            "/srv/services/dns-primary/pihole/etc-pihole",
            "/srv/services/dns-primary/unbound",
            "dig @10.40.0.11 example.com A",
            "just acceptance-dns-primary internal=internal-ingress.fearn.cloud",
            "Guest must not use internal DNS",
            "DNS-001-ALLOW-INTERNAL-RESOLUTION",
            "DNS-003-ALLOW-DNS-UPSTREAM",
        ]

        for phrase in expected_phrases:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, content)

    def test_runbook_names_the_generated_quadlet_artifacts(self):
        content = (REPO_ROOT / "runbooks" / "dns-architecture.md").read_text()

        self.assertIn("fortress-group-dns-primary.network", content)
        self.assertIn("fortress-dns-primary-pihole.container", content)
        self.assertIn("fortress-dns-primary-unbound.container", content)
        self.assertIn("fortress-dns-primary-pihole.service", content)
        self.assertIn("fortress-dns-primary-unbound.service", content)


if __name__ == "__main__":
    unittest.main()
