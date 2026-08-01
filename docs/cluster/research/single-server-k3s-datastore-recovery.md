> Historical Canon source — migrated to Rite on 2026-07-31 from `docs/research/single-server-k3s-datastore-recovery.md`. See [migration status](../README.md).

# Single-server K3s datastore and recovery facts

Research date: 2026-07-26. Sources are limited to the current official K3s documentation.

## Recommendation

Use **single-member embedded etcd**, initialized with `--cluster-init`, for Canon's first Cluster. This does not make the single-server Cluster highly available, but it gives the secondary recovery path K3s's built-in scheduled snapshots, retention, integrity checking, and direct upload to and restore from S3-compatible storage. Keep the already-agreed **Git-based rebuild plus application-data restore** as the primary total-loss path.

Pin the complete K3s release in declared bootstrap configuration. Store the original server token and snapshot-store recovery credentials in the External Recovery Substrate. Treat etcd snapshots as highly sensitive disaster-recovery artifacts, not as the backup for application volumes.

## Supported datastore choices

- Embedded SQLite is the default when no datastore is configured. It is supported for one server only. Its K3s-supported backup is a copy of `/var/lib/rancher/k3s/server/db/`; restore replaces that directory and also requires the original server token. ([Cluster Datastore](https://docs.k3s.io/datastore), [Backup and Restore](https://docs.k3s.io/datastore/backup-restore))
- Embedded etcd is selected when K3s initializes or joins an etcd Cluster, or finds etcd data on disk. An existing single-node SQLite installation can be converted by restarting with `--cluster-init`. K3s documents three or more odd-numbered servers for **HA** embedded etcd, so one member is supported as a datastore choice but supplies no quorum redundancy. ([Cluster Datastore](https://docs.k3s.io/datastore), [High Availability Embedded etcd](https://docs.k3s.io/datastore/ha-embedded#existing-single-node-clusters))
- External etcd, MySQL/MariaDB, and PostgreSQL are also supported. K3s delegates their backup and restore to the database operator. For Canon's one-VM learning milestone, this would add an external availability and recovery dependency without improving the single K3s server's availability. ([Cluster Datastore](https://docs.k3s.io/datastore), [Backup and Restore](https://docs.k3s.io/datastore/backup-restore#backup-and-restore-with-external-datastore))

SQLite is the smallest runtime choice. Embedded etcd is recommended here specifically because Canon wants a separately exercised datastore-snapshot path stored outside the lost Cluster VM. If that path is dropped, SQLite should be reconsidered.

## Embedded-etcd snapshot and restore facts

- Scheduled snapshots are enabled by default at midnight and noon, with five retained. They default to `${data-dir}/db/snapshots` (`data-dir` defaults to `/var/lib/rancher/k3s`), so the defaults alone are lost with the VM. Schedule, compression, local retention, directory, and S3 retention are configurable. On-demand snapshots have no automatic retention. ([etcd-snapshot: creating snapshots](https://docs.k3s.io/cli/etcd-snapshot#creating-snapshots))
- K3s can send scheduled and on-demand snapshots to S3-compatible object storage and restore directly from it. The external store therefore needs its own access controls, encryption, retention policy, monitoring, and recovery credentials. ([etcd-snapshot: S3 support](https://docs.k3s.io/cli/etcd-snapshot#s3-compatible-object-store-support))
- An in-Cluster Secret may supply S3 configuration during normal operation, but cannot supply it during restore because the API server is unavailable. The recovery procedure must supply S3 configuration outside Kubernetes, for example through protected CLI/config inputs available to the recovery operator. ([etcd-snapshot: S3 configuration Secret](https://docs.k3s.io/cli/etcd-snapshot#s3-configuration-secret-support))
- A single-server restore stops K3s, runs `k3s server --cluster-reset --cluster-reset-restore-path=...`, then starts K3s normally. Restore verifies the snapshot checksum, resets etcd membership to the restoring member, and extracts CA certificates and other confidential bootstrap data. ([etcd-snapshot: restoring snapshots](https://docs.k3s.io/cli/etcd-snapshot#restoring-snapshots))
- Restoring on a replacement host requires the server token that existed when the snapshot was taken. If config also declares a token, it must match. Old Node resources are included and may need manual removal when host identities change. ([etcd-snapshot: restoring to new hosts](https://docs.k3s.io/cli/etcd-snapshot#restoring-to-new-hosts))
- K3s says an etcd snapshot may be restored with the version that created it or a higher minor version. It does not promise restoration into an older minor version. Separately, rollback to an older Kubernetes minor requires a datastore backup made on that older minor. The conservative recovery rule is therefore to install the exact recorded K3s release first, restore and verify, and perform upgrades only as a separate operation. The installer supports an explicit `INSTALL_K3S_VERSION`. ([etcd-snapshot: restoring snapshots](https://docs.k3s.io/cli/etcd-snapshot#restoring-snapshots), [Rolling Back K3s](https://docs.k3s.io/upgrades/roll-back), [Environment Variables](https://docs.k3s.io/reference/env-variables))

An etcd snapshot is a copy of the Kubernetes datastore. It does **not** constitute an application-volume backup; that data is outside etcd and still needs the separately planned persistent-volume or application-native restore path. This is a direct architectural implication of what K3s says the snapshot contains, rather than a claim that K3s backs up storage. ([etcd-snapshot: security](https://docs.k3s.io/cli/etcd-snapshot#security))

## Token and certificate requirements

The server token is both a powerful join credential and the PBKDF2 passphrase protecting confidential bootstrap data in the datastore. It is written to `/var/lib/rancher/k3s/server/token` and must be backed up with the datastore. Possession grants effective Cluster-administrator capability. ([token: server](https://docs.k3s.io/cli/token#server))

Etcd snapshots contain the full datastore plus Cluster CA certificates and private keys; when Kubernetes secrets encryption is enabled, the encryption configuration and keys are also present. K3s derives the snapshot/bootstrap encryption key from the server token. Snapshot and token must therefore be protected separately where practical: either one is sensitive, and together they expose encrypted resources and CA private keys. ([etcd-snapshot: security](https://docs.k3s.io/cli/etcd-snapshot#security))

K3s client and server leaf certificates are valid for 365 days and are automatically renewed at startup when expired or within 120 days of expiry. A restored Cluster should explicitly verify certificate status after starting, especially from an old snapshot. If Canon later adopts custom CAs, K3s separately recommends retaining the custom root/intermediate material for future CA rotation. ([certificate: client and server certificates](https://docs.k3s.io/cli/certificate#client-and-server-certificates), [certificate: custom CAs](https://docs.k3s.io/cli/certificate#using-custom-ca-certificates))

## Implications for Canon's two recovery paths

### Primary: rebuild from Git after complete Cluster-VM loss

1. Recreate a blank Cluster VM through the infrastructure boundary.
2. Install the exact declared K3s release and initialize fresh embedded etcd.
3. Bootstrap GitOps using credentials held outside the Cluster; reconciliation recreates declarative Kubernetes state.
4. Restore non-declarative secrets/identity only where the design explicitly requires continuity, then restore application data through its own backup mechanism.
5. Verify the application through its normal `home.arpa` hostname.

This path intentionally does not consume an etcd snapshot. With default self-signed CAs it creates a new Cluster identity, so external kubeconfigs and any trust pinned to the old CA must be replaced. That identity change is an inference from K3s creating its CA on first-server initialization and restoring the old CA only from datastore bootstrap data. ([token: server](https://docs.k3s.io/cli/token#server), [etcd-snapshot: restoring snapshots](https://docs.k3s.io/cli/etcd-snapshot#restoring-snapshots))

### Secondary: restore the Cluster datastore snapshot

1. Recreate the VM and install the exact K3s release recorded with the snapshot, without beginning a fresh operational bootstrap.
2. Retrieve a selected external snapshot, its original server token, and S3 connection credentials through the recovery authority.
3. Run the documented single-server `--cluster-reset` restore and then start K3s normally.
4. Remove stale Node objects if identity changed; verify certificates, API health, GitOps reconciliation, secrets, and workload state.
5. Restore application volumes separately if they were also lost.

This is a faster preservation path for Cluster identity and non-Git Kubernetes state. It must not quietly become the prerequisite for proving the declarative primary path.

## Decisions newly exposed

1. Choose the External Recovery Substrate's S3-compatible provider/location and define access control, server-side encryption, immutability or deletion protection, and independent availability.
2. Set measurable datastore RPO, snapshot schedule, local/S3 retention, failure alerting, and restore-test cadence; K3s defaults are mechanics, not an adequate policy.
3. Decide whether a fresh CA and new Cluster identity are explicitly acceptable on the Git-based full rebuild path, and enumerate every external client or integration that must be reissued.
4. Define how the original server token and restore-time S3 credentials are escrowed, separated, audited, and made available when Kubernetes and the Cluster VM do not exist.
5. Define the version manifest stored with or discoverable from each snapshot, and the upgrade rule that keeps a tested restore version obtainable.
6. Decide whether the first milestone must execute both paths or only the Git rebuild, with datastore restore documented and scheduled for a later drill.
