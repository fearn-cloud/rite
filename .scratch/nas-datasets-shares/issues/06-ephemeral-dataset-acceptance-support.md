# Ephemeral Dataset acceptance support

Status: needs-triage

## What to build

Add Acceptance Test support for Ephemeral Datasets so live NAS behavior can be proven without risking adopted data. Ephemeral Datasets may be created and destroyed only inside acceptance-test inventory and workflows, and can be used to verify Dataset validation, derived Share creation, VM Mount access, and Share-backed Service volume behavior end to end.

## Acceptance criteria

- [ ] Acceptance-test inventory can declare `lifecycle: ephemeral` Datasets without weakening ordinary fleet validation.
- [ ] Acceptance workflow creates an Ephemeral Dataset, runs NAS Reconcile, configures a disposable Operational VM Mount, and verifies read/write/delete access according to declared Access Policy.
- [ ] Acceptance workflow verifies `source: /` and safe relative Share-backed Volume subpath behavior.
- [ ] Acceptance workflow destroys Ephemeral Datasets and fortress-owned Shares it created.
- [ ] Failure handling avoids deleting ordinary adopted Datasets or unmanaged Shares.

## Blocked by

- `.scratch/nas-datasets-shares/issues/05-fortress-owned-share-reconciliation.md`
