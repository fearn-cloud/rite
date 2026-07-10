import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


class FirewallMatrixTests(unittest.TestCase):
    def test_forgejo_runner_phase_one_network_policy_is_narrow(self):
        content = (REPO_ROOT / "docs" / "firewall-matrix.md").read_text()

        required_phrases = [
            "| `10.40.0.20` | `forgejo-runner-vm` | Infrastructure | Stateless Forgejo Runner VM |",
            "| `forgejo-runner-vm` | `10.40.0.20` | `neuromancer` | Forgejo Runner | VM-local disposable state |",
            "Forgejo runners must not run on `forgejo-vm`.",
            "The phase-one Runner VM is an Infrastructure workload with narrow egress, not a Trusted client.",
            "`GIT-002-ALLOW-RUNNER-FORGEJO`",
            "| `ADMIN-004-ALLOW-TRUSTED-INFRA` | Trusted | Infrastructure VMs except `forgejo-runner-vm` | TCP | 22, service admin ports | Yes | Direct service administration during bootstrap and incidents |",
            "| `ADMIN-006-ALLOW-RUNNER-SSH` | Trusted, tailnet-routed Operator workstations | `forgejo-runner-vm` | TCP | 22 | Yes | Operator SSH is the only intended inbound management path to the Runner VM |",
            "For `forgejo-runner-vm`, DNS and time access is limited to `DNS-001-ALLOW-INTERNAL-RESOLUTION` and `NTP-001-ALLOW-TIME-SYNC`; those baseline rules do not imply general Trusted VLAN behavior.",
            "| `GIT-002-ALLOW-RUNNER-FORGEJO` | `forgejo-runner-vm` | `internal-ingress-vm` Forgejo HTTP and SSH ingress addresses | TCP | 443, 22 | Yes | Runner registration, polling, repository checkout, and job execution against the Forgejo service |",
            "`RUNNER-001-ALLOW-DEPENDENCY-EGRESS`",
            "| `RUNNER-001-ALLOW-DEPENDENCY-EGRESS` | `forgejo-runner-vm` | Internet | TCP | 80, 443 | Yes | Package installs, base image pulls, and public dependency downloads for validation jobs |",
            "`RUNNER-002-DENY-MANAGEMENT-REACHABILITY`",
            "| `RUNNER-002-DENY-MANAGEMENT-REACHABILITY` | `forgejo-runner-vm` | Proxmox Hosts, NAS management address, `pbs-vm`, ordinary Service Backend ports | Any | Any | Yes | Phase-one CI is not a deployment or management principal |",
            "`RUNNER-003-DENY-TRUSTED-CLIENT-BEHAVIOR`",
            "| `RUNNER-003-DENY-TRUSTED-CLIENT-BEHAVIOR` | `forgejo-runner-vm` | Trusted-only client/admin surfaces | Any | Any | Yes | The Runner VM does not inherit Trusted VLAN bypass or recovery access |",
        ]

        for phrase in required_phrases:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, content)

        self.assertNotIn("GIT-002-ALLOW-FUTURE-RUNNERS", content)
        self.assertNotIn("Runner registration and job execution after runner placement is defined", content)


if __name__ == "__main__":
    unittest.main()
