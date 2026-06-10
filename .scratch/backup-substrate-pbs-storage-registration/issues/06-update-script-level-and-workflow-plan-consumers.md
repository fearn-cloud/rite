Status: ready-for-agent

# Update script-level and workflow plan consumers

## Parent

.scratch/backup-substrate-pbs-storage-registration/PRD.md

## What to build

Update script-level Backup Configure plan consumers so text and JSON output preserve the storage registration versus Backup Job distinction end-to-end. The script behavior should remain plan-only for PBS Storage Registration in this first implementation slice, and downstream parsing should not need to guess whether a datastore-shaped field means the PVE storage ID or the PBS Datastore.

## Acceptance criteria

- [ ] Script-level text output shows storage registration actions separately from Backup Job actions.
- [ ] Script-level JSON output includes distinct storage registration and Backup Job structures or fields.
- [ ] Existing plan parsing or workflow tests are updated so consumers can read the new JSON shape.
- [ ] Backup Configure apply behavior does not attempt to create, update, or prune PBS Storage Registration in this slice.
- [ ] Tests cover script-level text and JSON output for the storage/job distinction.

## Blocked by

- .scratch/backup-substrate-pbs-storage-registration/issues/04-plan-pbs-storage-registration-separately.md
- .scratch/backup-substrate-pbs-storage-registration/issues/05-retarget-backup-jobs-to-pbs-storage-registration.md
