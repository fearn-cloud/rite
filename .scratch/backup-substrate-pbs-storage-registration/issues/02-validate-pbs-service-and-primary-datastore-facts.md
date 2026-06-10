Status: ready-for-agent

# Validate PBS Service and Primary Datastore facts

## Parent

.scratch/backup-substrate-pbs-storage-registration/PRD.md

## What to build

Deepen Backup Substrate derivation and validation so the declared substrate proves the local PBS Service, backend PBS VM, server address and port, Primary Datastore, NAS-backed storage path, read-write PBS VM mount, and Unprotected VM recovery boundary. The validation should use declared Inventory facts only and should preserve the distinction between the PBS Datastore and the PVE-side PBS Storage Registration.

## Acceptance criteria

- [ ] Static validation rejects a missing, malformed, ambiguous, or incorrectly backed PBS Service for the declared Backup Substrate.
- [ ] The PBS server address is derived from the PBS Service backend VM's declared static interface, and validation rejects a PBS VM without a usable static address.
- [ ] The PBS server port is derived from the PBS Service backend port.
- [ ] Static validation rejects a Primary Datastore that is not NAS-backed or is not mounted read-write by the PBS VM.
- [ ] Static validation requires the local PBS backend VM to be an Unprotected VM with an operator-facing reason.
- [ ] Tests cover valid derivation and the malformed Service, missing static address, non-NAS Primary Datastore, non-read-write mount, and protected PBS VM failure cases.

## Blocked by

- .scratch/backup-substrate-pbs-storage-registration/issues/01-declare-and-load-backup-substrate.md
