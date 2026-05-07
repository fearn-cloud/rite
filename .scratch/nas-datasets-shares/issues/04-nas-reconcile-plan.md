# NAS Reconcile Plan

Status: needs-triage

## What to build

Introduce a read-only NAS Reconcile Plan that compares declared Dataset and derived Share intent with TrueNAS reality without mutating TrueNAS. The plan validates adopted Dataset existence and root owner UID/GID, derives desired NFS Shares from VM Mount and Service consumption declarations, and reports unmanaged Shares that could expose the same Dataset.

## Acceptance criteria

- [ ] A `nas-reconcile` or `nas-reconcile-plan` operator command loads inventory and produces a read-only plan.
- [ ] TrueNAS connection settings and credentials are represented without exposing secrets in logs or plans.
- [ ] The plan validates each adopted Dataset exists at its declared TrueNAS path.
- [ ] The plan validates each adopted Dataset root owner UID/GID and reports drift without repairing it.
- [ ] Desired NFS Shares are derived deterministically from Dataset, protocol, compatible Access Policies, and Mount-bearing VM static IP addresses.
- [ ] Unmanaged Shares that could expose the same Dataset as desired fortress-owned Share intent block the plan.
- [ ] Unit tests cover plan output with missing Dataset, owner drift, missing Share, stale fortress-owned Share, and unmanaged overlap.

## Blocked by

- `.scratch/nas-datasets-shares/issues/02-vm-mounts-reference-datasets.md`
- `.scratch/nas-datasets-shares/issues/03-share-backed-service-volumes.md`
