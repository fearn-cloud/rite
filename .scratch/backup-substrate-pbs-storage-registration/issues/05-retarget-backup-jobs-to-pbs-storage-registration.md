Status: ready-for-agent

# Retarget Backup Jobs to PBS Storage Registration

## Parent

.scratch/backup-substrate-pbs-storage-registration/PRD.md

## What to build

Update Backup Configure so Backup Jobs target the PVE-side PBS Storage Registration `rite-pbs` instead of treating the Primary Datastore as the job target. The plan should continue to preserve Primary Datastore facts for the storage registration action, while Backup Job actions should compare, render, and serialize the PVE storage ID used by PVE.

## Acceptance criteria

- [ ] Desired Backup Job actions target `rite-pbs` as the PVE storage ID.
- [ ] Observed Backup Jobs are compared against the PVE storage ID, not the PBS Datastore name.
- [ ] Backup Job plan text renders VM, policy, PVE storage ID, job name, and schedule.
- [ ] Backup Job plan JSON preserves PVE storage ID separately from Primary Datastore facts.
- [ ] Existing Backup Configure tests that expected `datastore=pbs-datastore` on job actions are updated to prove the new terminology and behavior.

## Blocked by

- .scratch/backup-substrate-pbs-storage-registration/issues/04-plan-pbs-storage-registration-separately.md
