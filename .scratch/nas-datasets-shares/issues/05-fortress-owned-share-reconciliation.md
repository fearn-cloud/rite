# Fortress-owned Share reconciliation

Status: needs-triage

## What to build

Extend NAS Reconcile from read-only planning to API-backed writes for fortress-owned derived NFS Shares. Reconcile may create, update, or destroy only Shares carrying a durable fortress ownership marker. Mount removals, Mount access changes, and Mount point changes require operator confirmation before reconciliation continues.

## Acceptance criteria

- [ ] Created NFS Shares carry a durable fortress ownership marker and deterministic identity.
- [ ] NAS Reconcile updates only fortress-owned Shares and refuses to mutate unmanaged Shares.
- [ ] NAS Reconcile destroys stale fortress-owned Shares only when no VM or Service declaration still requires them.
- [ ] Mount removal, `access` change, and `mount_point` change are surfaced in preflight output and require explicit operator confirmation.
- [ ] NAS Reconcile does not roll back Shares after downstream VM Configure or Service deployment failures.
- [ ] Tests cover create, update, stale delete, unmanaged conflict refusal, and confirmation-gated changes.

## Blocked by

- `.scratch/nas-datasets-shares/issues/04-nas-reconcile-plan.md`
