import unittest
from datetime import UTC, datetime
from pathlib import Path

from fortress_cluster.hosts import (
    ClusterHostReadinessAttestation,
    ObservationCluster,
    observation_cluster_host_requirement,
)
from fortress_substrate.cluster_hosts import (
    ClusterHostReadinessObservation,
    OBSERVATION_CLUSTER_REALIZATION,
    FixtureClusterHostReadiness,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


class ObservationClusterSubstrateSeamTests(unittest.TestCase):
    def test_observation_requirement_declares_the_cluster_owned_network_contract(self):
        requirement = observation_cluster_host_requirement(
            desired_state_revision="a" * 40,
        )

        self.assertEqual("observation-server", requirement.name)
        self.assertEqual("k3s-server", requirement.role)
        self.assertTrue(requirement.admits_workloads)
        self.assertEqual("10.80.0.11", requirement.lan_address)
        self.assertEqual(80, requirement.vlan)
        self.assertEqual("10.42.0.0/16", requirement.pod_cidr)
        self.assertEqual("10.43.0.0/16", requirement.service_cidr)
        self.assertEqual("observation.fearn.cloud", requirement.ingress_domain)

    def test_fixture_readiness_binds_cluster_and_substrate_revisions_without_exposing_realization(self):
        requirement = observation_cluster_host_requirement(
            desired_state_revision="b" * 40,
        )
        observation = ObservationCluster(requirement=requirement)
        attestation = observation.check_host_readiness(FixtureClusterHostReadiness(
            inventory_revision="c" * 40,
            observations={
                "observation-server": self._ready_observation(requirement),
            },
            now=lambda: datetime(2026, 8, 4, 21, 0, tzinfo=UTC),
        ))

        self.assertIsInstance(attestation, ClusterHostReadinessAttestation)
        self.assertEqual(requirement.revision, attestation.requirement_revision)
        self.assertEqual("c" * 40, attestation.substrate_inventory_revision)
        self.assertEqual("observation-cluster-vm", attestation.concrete_vm_identity)
        self.assertEqual(datetime(2026, 8, 4, 22, 0, tzinfo=UTC), attestation.expires_at)
        self.assertEqual("cluster-bootstrap", attestation.consumer_purpose)

    def test_fixture_refuses_an_observation_that_does_not_match_the_requirement(self):
        requirement = observation_cluster_host_requirement(desired_state_revision="e" * 40)
        incompatible = ClusterHostReadinessObservation(
            realization=OBSERVATION_CLUSTER_REALIZATION,
            role="k3s-server",
            admits_workloads=True,
            lan_address="10.80.0.12",
            vlan=80,
            pod_cidr="10.42.0.0/16",
            service_cidr="10.43.0.0/16",
            ingress_domain="observation.fearn.cloud",
        )

        with self.assertRaisesRegex(ValueError, "not ready"):
            FixtureClusterHostReadiness(
                inventory_revision="f" * 40,
                observations={"observation-server": incompatible},
                now=lambda: datetime(2026, 8, 4, 21, 0, tzinfo=UTC),
            ).check(requirement)

    def test_observation_cluster_names_one_requirement_without_substrate_placement(self):
        observation = ObservationCluster(
            requirement=observation_cluster_host_requirement(desired_state_revision="d" * 40),
        )

        self.assertEqual("observation-server", observation.requirement.name)
        self.assertFalse(hasattr(observation, "host"))
        self.assertFalse(hasattr(observation, "provider"))
        self.assertFalse(hasattr(observation, "vmid"))

    def test_firewall_matrix_declares_only_the_eight_observation_cluster_paths(self):
        matrix = (REPO_ROOT / "docs" / "firewall-matrix.md").read_text()

        self.assertIn("| 80 | Observation Cluster | `10.80.0.0/24` | `10.80.0.1`", matrix)
        self.assertIn("| `observation-cluster-vm` | `10.80.0.11` | `wintermute`", matrix)
        for rule_id in range(1, 9):
            self.assertIn(f"`OBSCL-{rule_id:03d}`", matrix)
        self.assertIn("Host must not be `wintermute`", matrix)
        self.assertIn("direct OCI Mirror access", matrix)
        self.assertIn("Kubernetes API access", matrix)

    def test_cluster_code_has_no_raw_substrate_import(self):
        forbidden = (
            "fortress_inventory",
            "fortress_services",
            "fortress_substrate",
            "fortress_tofu",
            "proxmox",
            "pulumi",
        )
        for source in (REPO_ROOT / "fortress_cluster").rglob("*.py"):
            content = source.read_text()
            self.assertFalse(
                any(f"import {package}" in content or f"from {package}" in content for package in forbidden),
                source,
            )

    @staticmethod
    def _ready_observation(requirement):
        return ClusterHostReadinessObservation(
            realization=OBSERVATION_CLUSTER_REALIZATION,
            role=requirement.role,
            admits_workloads=requirement.admits_workloads,
            lan_address=requirement.lan_address,
            vlan=requirement.vlan,
            pod_cidr=requirement.pod_cidr,
            service_cidr=requirement.service_cidr,
            ingress_domain=requirement.ingress_domain,
        )


if __name__ == "__main__":
    unittest.main()
