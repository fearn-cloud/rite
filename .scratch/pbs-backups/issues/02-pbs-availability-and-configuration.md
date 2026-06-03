Status: ready-for-human

# PBS Availability And Configuration

## What to build

Make `pbs-vm` and the PBS Service an explicit, verifiable backup substrate before Backup Configure and live Backup Readiness depend on them. The operator can prove that PBS is reachable, that the Primary Datastore is configured for Backup Targets, that PBS encryption Recovery Secret material is available, and that `pbs-vm` remains intentionally unprotected by local PBS.

This slice owns substrate availability and configuration, not per-VM Backup Job reconciliation and not per-Backup Target readiness.

## Acceptance criteria

- [x] The operator has a workflow or validation path that verifies `pbs-vm` exists in Inventory as the PBS VM and is placed on its declared Host.
- [x] The PBS Service is represented as the service that configures and runs Proxmox Backup Server on `pbs-vm`.
- [x] The Primary Datastore used by Backup Targets is discoverable from Inventory or derived model state.
- [x] PBS configuration verifies that the Primary Datastore path is present and usable for Backup Runs.
- [x] PBS encryption Recovery Secret availability is verified without exposing secret material in normal output.
- [x] `pbs-vm` is explicitly treated as an Unprotected VM because local PBS does not back up itself.
- [x] Operator output clearly distinguishes PBS substrate readiness from Backup Target readiness.
- [x] Tests cover PBS VM identity, PBS Service configuration expectations, Primary Datastore discovery, Recovery Secret availability, and the `pbs-vm` unprotected exception.

## Blocked by

- `.scratch/pbs-backups/issues/01-inventory-backup-policy-contract.md`
