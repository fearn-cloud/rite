"""Substrate-side realization declarations for Cluster host requirements."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta

from fortress_cluster.hosts import ClusterHostReadinessAttestation, ClusterHostRequirement


@dataclass(frozen=True)
class ClusterHostRealization:
    """A substrate-owned concrete realization selected for a requirement identity."""

    requirement_name: str
    concrete_vm_identity: str
    host: str


@dataclass(frozen=True)
class ClusterHostReadinessObservation:
    """Non-authoritative substrate facts observed when checking one realization."""

    realization: ClusterHostRealization
    role: str
    admits_workloads: bool
    lan_address: str
    vlan: int
    pod_cidr: str
    service_cidr: str
    ingress_domain: str

    def satisfies(self, requirement: ClusterHostRequirement) -> bool:
        return (
            self.realization.requirement_name == requirement.name
            and self.role == requirement.role
            and self.admits_workloads == requirement.admits_workloads
            and self.lan_address == requirement.lan_address
            and self.vlan == requirement.vlan
            and self.pod_cidr == requirement.pod_cidr
            and self.service_cidr == requirement.service_cidr
            and self.ingress_domain == requirement.ingress_domain
        )


OBSERVATION_CLUSTER_REALIZATION = ClusterHostRealization(
    requirement_name="observation-server",
    concrete_vm_identity="observation-cluster-vm",
    host="wintermute",
)


@dataclass(frozen=True)
class FixtureClusterHostReadiness:
    """Hermetic readiness adapter used until the Rite Command workflow exists."""

    inventory_revision: str
    observations: Mapping[str, ClusterHostReadinessObservation]
    now: Callable[[], datetime]

    def check(self, requirement: ClusterHostRequirement) -> ClusterHostReadinessAttestation:
        observation = self.observations[requirement.name]
        if not observation.satisfies(requirement):
            raise ValueError(f"Cluster Host Requirement {requirement.name} is not ready")
        issued_at = self.now()
        return ClusterHostReadinessAttestation(
            requirement_name=requirement.name,
            requirement_revision=requirement.revision,
            substrate_inventory_revision=self.inventory_revision,
            concrete_vm_identity=observation.realization.concrete_vm_identity,
            consumer_purpose="cluster-bootstrap",
            issued_at=issued_at,
            expires_at=issued_at + timedelta(hours=1),
        )
