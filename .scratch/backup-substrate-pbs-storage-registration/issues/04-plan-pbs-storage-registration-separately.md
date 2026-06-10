Status: ready-for-agent

# Plan PBS Storage Registration separately

## Parent

.scratch/backup-substrate-pbs-storage-registration/PRD.md

## What to build

Teach Backup Configure planning to expose PBS Storage Registration actions separately from Backup Job actions. The plan should show the fortress-owned PVE storage ID `rite-pbs`, the derived PBS server, and the Primary Datastore that `rite-pbs` points at. This slice stops at planning and rendering; it must not add live PVE storage creation, update, prune, or readiness checks.

## Acceptance criteria

- [ ] Backup Configure plans include a separate storage registration action for Hosts with Backup Targets.
- [ ] Storage registration plan text renders the PVE storage ID, PBS server, and PBS Datastore distinctly.
- [ ] Storage registration plan JSON preserves the same distinction for future apply behavior.
- [ ] No live PVE mutation for PBS Storage Registration is added in this slice.
- [ ] Tests prove storage registration actions render separately from Backup Job actions.

## Blocked by

- .scratch/backup-substrate-pbs-storage-registration/issues/01-declare-and-load-backup-substrate.md
- .scratch/backup-substrate-pbs-storage-registration/issues/02-validate-pbs-service-and-primary-datastore-facts.md
- .scratch/backup-substrate-pbs-storage-registration/issues/03-validate-backup-substrate-trust-and-token-references.md
