> Historical Canon source — adopted by Rite on 2026-07-31 from `docs/adr/0001-separate-substrate-and-cluster-authority.md`.

# Separate substrate and Cluster authority

Canon owns Cluster Desired State and expresses each required Cluster VM through a Cluster Host Requirement; Rite owns the distinct Substrate Inventory that realizes concrete VMs and the cluster-independent capabilities surrounding Canon. Rite returns Cluster Host Readiness Evidence across the seam, so no infrastructure fact is authoritative in both declarations and Canon does not acquire provider, placement, or VM-lifecycle responsibility.
