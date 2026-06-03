Status: ready-for-human

# Backup Readiness Gate

## What to build

Add live Backup Readiness for Backup Targets. A Backup Target is not production-ready until its selected Backup Policy is valid, its Primary Datastore path is usable, its PBS encryption Recovery Secret is available, its expected Backup Job exists, and at least one successful Backup Run has completed.

Service Launch treats Backup Readiness as a prerequisite for Backup Targets without running Backup Configure or mutating backup state.

## Acceptance criteria

- [x] Backup Readiness evaluates each Backup Target independently.
- [x] Backup Readiness includes selected Backup Policy validity.
- [x] Backup Readiness includes usable Primary Datastore path verification.
- [x] Backup Readiness includes PBS encryption Recovery Secret availability.
- [x] Backup Readiness includes expected Backup Job presence.
- [x] Backup Readiness requires at least one successful Backup Run.
- [x] Unprotected VMs are excluded from Backup Readiness gating with their reason visible.
- [x] Service Launch blocks production readiness for Backup Targets that fail Backup Readiness.
- [x] Service Launch does not run Backup Configure or trigger Backup Runs as part of the gate.
- [x] Tests cover passing readiness, each failed prerequisite, Unprotected VM exclusion, and Service Launch gating behavior.

## Blocked by

- `.scratch/pbs-backups/issues/02-pbs-availability-and-configuration.md`
- `.scratch/pbs-backups/issues/04-backup-configure-apply.md`
- `.scratch/pbs-backups/issues/05-initial-backup-run-triggering.md`
