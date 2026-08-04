"""Cluster-owned host requirements and the narrow readiness-consumer interface."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True)
class ClusterHostRequirement:
    """A Cluster capability declaration, independent of its realization."""

    name: str
    revision: str
    role: str
    admits_workloads: bool
    lan_address: str
    vlan: int
    pod_cidr: str
    service_cidr: str
    ingress_domain: str


@dataclass(frozen=True)
class ClusterHostReadinessAttestation:
    """A substrate-issued, time-bounded admission proof for one requirement."""

    requirement_name: str
    requirement_revision: str
    substrate_inventory_revision: str
    concrete_vm_identity: str
    consumer_purpose: str
    issued_at: datetime
    expires_at: datetime

    def is_current_at(self, instant: datetime) -> bool:
        return self.issued_at <= instant < self.expires_at


class ClusterHostReadiness(Protocol):
    """The only substrate operation Cluster code may consume for host admission."""

    def check(self, requirement: ClusterHostRequirement) -> ClusterHostReadinessAttestation: ...


@dataclass(frozen=True)
class ObservationCluster:
    """The first Cluster declaration, intentionally absent any realization details."""

    requirement: ClusterHostRequirement

    def check_host_readiness(
        self, readiness: ClusterHostReadiness
    ) -> ClusterHostReadinessAttestation:
        """Consume the substrate seam without learning how the VM is realized."""

        return readiness.check(self.requirement)


def observation_cluster_host_requirement(*, desired_state_revision: str) -> ClusterHostRequirement:
    """Return the Observation Cluster's stable server requirement."""

    return ClusterHostRequirement(
        name="observation-server",
        revision=desired_state_revision,
        role="k3s-server",
        admits_workloads=True,
        lan_address="10.80.0.11",
        vlan=80,
        pod_cidr="10.42.0.0/16",
        service_cidr="10.43.0.0/16",
        ingress_domain="observation.fearn.cloud",
    )
