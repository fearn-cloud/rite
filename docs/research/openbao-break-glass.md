# OpenBao break-glass and recovery path

**Decision framing.** An OpenBao emergency has two distinct meanings.  Do not
use one ceremony for both:

1. **Recovery / availability:** OpenBao is sealed, restarted, or its normal
   auth path is unavailable.  The immediate goal is to restore a trusted,
   usable service.
2. **Emergency access to a healthy instance:** the service is running and
   reachable, but ordinary administrator access is unavailable or insufficient.
   The goal is a very short, observed, narrowly scoped administrative session.

This is a conceptual runbook design, deliberately not a production command
sequence and containing no secret values. It applies to a future Rite OpenBao
deployment; it does not change the present SOPS + age recovery model.

## First decision: contain or recover?

Treat a suspected compromise differently from a plain outage. A privileged
operator can seal a running OpenBao instance, which discards the root key held
in memory and blocks data access until it is unsealed again. This may limit
damage, but it is an availability-impacting containment action and should be
made only under the incident authority defined by the runbook. The seal,
unseal, init, and health paths are specifically *not* audit-logged, so preserve
independent incident notes and infrastructure logs for this part of an event.
[Seal/unseal](https://openbao.org/docs/concepts/seal/)
[Audit devices](https://openbao.org/docs/audit/)

For any event, first establish from a separate, trusted management environment:

- whether the service is sealed, merely unreachable, or serving but denying
  normal authentication;
- whether storage, TLS/networking, the configured auth provider, and (for auto
  unseal) the seal provider are healthy; and
- whether the event could be a compromise. If so, preserve evidence and avoid
  treating restored access as proof the system is trustworthy.

OpenBao cannot authenticate clients or manage mounts while sealed; at that
point the meaningful operations are status and unseal. A storage backup is
only one recovery input: OpenBao also calls out server configuration and
management scripts, and recommends considering HA alongside backups. Offline
or atomic, consistent snapshots matter for a reliable restore.
[Seal/unseal](https://openbao.org/docs/concepts/seal/)
[Storage and backups](https://openbao.org/docs/concepts/storage/)

## Recovery path: sealed, restarted, or restored service

### Shamir seal

With OpenBao's default Shamir seal, the initialization ceremony splits the
unseal key into shares and defines a threshold. A designated quorum of share
holders supplies their distinct shares to each sealed node until the threshold
is met. The shares authorize reconstruction of the unseal key, allowing the
server to decrypt the root key and then its data keyring. A restart, an
explicit seal, or an unrecoverable storage error returns a node to the sealed
state; in a multi-node deployment each node needs its own threshold unseal.
[Seal/unseal](https://openbao.org/docs/concepts/seal/)

The break-glass artifact is therefore not an always-online administrator token.
It is a threshold-governed set of offline unseal shares, held separately from
the OpenBao service and from one another. The ceremony should require an
identified incident, a quorum, a trusted console/network path, a recorded
reason, and post-event review. It should never place all shares in one SOPS
file, one workstation, one automation system, or the OpenBao cluster itself:
that removes the quorum and makes a common outage or compromise decisive.

### Auto unseal

Auto unseal changes *startup* recovery, not the need for emergency governance.
On startup, OpenBao asks its configured KMS, HSM, or other seal service to
decrypt the root key it read from storage. Initialization produces **recovery
keys**, which are threshold shares used to authorize sensitive operations such
as generating a root token. They are not unseal keys: recovery keys cannot
decrypt the root key. If the external seal mechanism or its key is unavailable,
the cluster cannot be recovered until it is available; if it is permanently
deleted, the cluster cannot be recovered even from a backup.
[Seal/unseal](https://openbao.org/docs/concepts/seal/)

Thus an auto-unseal break-glass plan has two independent branches:

- Restore the underlying seal provider and the OpenBao identity/configuration
  needed to use it, then bring OpenBao back through its normal auto-unseal
  path.
- Use the recovery-key quorum only for the separate privileged authorization
  operations it supports; do not mistake those shares for an escape hatch from
  a lost KMS/HSM.

Before choosing auto unseal, explicitly test losing the application identity,
network path, and policy access to the seal provider. Protect the provider and
its key as critical recovery infrastructure, and maintain a supported seal
migration plan. Seal migration has downtime, needs a backup beforehand, and
requires both old and new seal mechanisms during migration.
[Seal configuration](https://openbao.org/docs/configuration/seal/)
[Seal migration](https://openbao.org/docs/concepts/seal/)

## Emergency access to a healthy OpenBao

If OpenBao is healthy but normal administrator login is broken, do **not** use
unseal shares/recovery keys as a routine login method. Their intended emergency
role is to authorize a quorum-protected generation of a new root token. A root
token has the `root` policy and can do anything; OpenBao recommends using it
only for initial setup or emergencies, then revoking it immediately. The
generation workflow can protect delivery using a one-time pad or an operator's
public PGP key, so no long-lived root token needs to be stored as a break-glass
credential.
[Tokens and root-token guidance](https://openbao.org/docs/concepts/tokens/)
[Generate root](https://openbao.org/docs/commands/operator/generate-root/)

Proposed healthy-service ceremony:

1. Declare the incident and name an incident lead and independent observer.
   Confirm the target cluster and explain why normal auth cannot be used.
2. Obtain the required Shamir-unseal-share or auto-unseal-recovery-key quorum,
   according to the selected seal type. Create a *new*, protected emergency
   root token through the quorum process; never retrieve a pre-stored,
   non-expiring root token.
3. With two people observing, make only the minimum repair: e.g. restore a
   deliberately pre-reviewed emergency operator policy/auth mapping, correct a
   failed policy configuration, or issue a short-lived, narrow administrator
   token. Policies are path based and deny by default, so a predefined
   break-glass policy should grant only the paths and operations required for
   this repair—not broad secret reads.
4. Verify normal login via the repaired, least-privilege path; then revoke the
   emergency root token immediately. Where a temporary service token was
   issued, set a short non-renewed lifetime and revoke it after the repair.

Tokens carry policies, and non-root tokens have TTLs and can be revoked along
with their associated leases. Token accessors allow a suitably authorized
operator to look up or revoke a token without handling its token value. These
features are useful for an emergency design, but access to list/revoke
accessors itself is sensitive and must remain tightly controlled.
[Policies](https://openbao.org/docs/concepts/policies/)
[Tokens, TTLs, revocation, and accessors](https://openbao.org/docs/concepts/tokens/)

## Audit and after-action recovery

Enable and protect multiple audit sinks before an incident. OpenBao audit
devices record API requests/responses (including errors), normally HMAC-hashing
string data, but they do not cover seal/unseal operations and are not enabled
by default. Multiple audit devices improve resilience, though OpenBao may block
requests when audit delivery fails; design and test both the log pipeline and
the operational consequence. Audit records are sensitive even when strings are
hashed: non-string data can be logged in plaintext and audit HMAC comparison is
an additional privileged capability.
[Audit devices](https://openbao.org/docs/audit/)

Close the incident only after:

- reviewing audit records, server/storage/seal-provider logs, and the manual
  record for non-audited sealing actions;
- revoking the emergency root token and every temporary token/credential;
- rotating or replacing credentials implicated by the incident (including
  external auth/seal-provider credentials as appropriate), and rotating
  unseal/recovery shares when their custody or threshold membership is no
  longer acceptable;
- restoring ordinary auth and confirming its least-privilege policies from a
  separate test identity; and
- taking and validating a fresh, consistent backup after the repair. Keep
  configuration and management artifacts with the recovery set; OpenBao's
  stored data alone is not its whole recovery picture.

OpenBao supports rotation of the barrier/unseal key and, for auto unseal, the
recovery key shares/threshold. Treat those documented operations as planned,
tested maintenance rather than improvising them mid-incident unless their
compromise is the incident itself.
[Seal/recovery-key rotation](https://openbao.org/docs/concepts/seal/)
[Storage and backups](https://openbao.org/docs/concepts/storage/)

## Rite-compatible offline design

Rite already has two age recipients: an operator-workstation identity and an
offline physical backup identity. Its stated recovery ceremony is: recover a
checkout, restore an authorized age identity, and decrypt locally—without
requiring a running secret server. Preserve that property.
[Rite SOPS + age ADR](../adr/0005-sops-age-two-recipients.md)
[Rite initial setup](../../runbooks/initial-setup.md)

For a future OpenBao pilot, use SOPS + age for the **offline recovery envelope**
rather than putting all break-glass material in OpenBao:

```text
offline / SOPS + age envelope
  - approved recovery runbook and contact/custody map
  - OpenBao server and storage configuration, TLS recovery material as needed
  - backup locations and restore-validation instructions
  - Shamir share custody references, OR recovery-key custody references
  - auto-unseal provider recovery procedure and its separate owner/control path
  - a sealed, time-bounded rollback copy only where a migrated workload truly
    cannot tolerate Bao outage

OpenBao
  - runtime and dynamic workload secrets
  - policies, auth mappings, audited short-lived tokens
  - never the sole holder of the materials needed to restore/unseal itself
```

Do not store actual Shamir shares, auto-unseal provider master credentials, and
the only copy of the encrypted data/configuration together in the same SOPS
object or on the same workstation. With the current two-recipient model, a
single operator can decrypt either recipient envelope; that is suitable for
Rite's present single-operator recovery but does **not** implement a genuine
multi-person Shamir quorum. If quorum separation is a requirement, assign
shares to independent custodians and use separately controlled offline storage;
do not claim two age recipients alone create that separation.

The first acceptance drill should be a disposable, isolated OpenBao instance:
recover a checked-out configuration and a storage snapshot, exercise the
chosen seal-provider or share-quorum path, prove a normal limited admin login,
and destroy the test secrets afterwards. Record the recovery time, missing
dependencies, and whether any artifact would make the process circular. Do not
move an irreplaceable production secret class until this drill and the
after-action token/share rotation have both succeeded.

## Sources

- [OpenBao: Seal/Unseal](https://openbao.org/docs/concepts/seal/)
- [OpenBao: Tokens](https://openbao.org/docs/concepts/tokens/)
- [OpenBao: Policies](https://openbao.org/docs/concepts/policies/)
- [OpenBao: Audit devices](https://openbao.org/docs/audit/)
- [OpenBao: Storage and backups](https://openbao.org/docs/concepts/storage/)
- [OpenBao: `operator generate-root`](https://openbao.org/docs/commands/operator/generate-root/)
- [OpenBao: seal configuration](https://openbao.org/docs/configuration/seal/)
