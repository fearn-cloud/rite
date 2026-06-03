# PBS backups

PBS protects Backup Target VM recoverability and VM-local state. A Backup Policy schedules PBS Backup Runs for VM disks; it does not protect NAS-backed Dataset history, and it does not promise point-in-time consistency between a restored VM disk and any Dataset mounted from NAS.

An Unprotected VM is intentionally outside PBS Backup Target coverage. `pbs-vm` is an Unprotected VM because local PBS does not back up itself; PBS is recovered from Inventory, the Primary Datastore, and Recovery Secrets.

Backup Readiness checks whether a Backup Target has the declared PBS substrate, Backup Job, Recovery Secret, and first successful Backup Run needed before operators rely on PBS for VM recoverability. When the Backup Target mounts NAS-backed Datasets, Backup Readiness output must keep saying that NAS-backed Dataset history is not protected by PBS.

Backup Health checks PBS restore-point freshness for Backup Targets. A healthy Backup Health result means a fresh PBS restore point exists for VM-local state; it does not prove point-in-time consistency with NAS-backed Datasets.

PBS Restore and Restore Drill planning must warn when a Backup Target has NAS-backed Datasets. Those Datasets require care during recovery or drills; recovery or drills require care because the restored VM disk may reference NAS-backed state that PBS did not snapshot as Dataset history. Restore Drill planning must avoid production Dataset mutation unless a later issue explicitly adds a controlled recovery path.
