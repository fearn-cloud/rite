# What OpenBao is

**Scope.** This is a practical description of OpenBao from its own
documentation and source repository. It distinguishes the product's roles from
guarantees that still belong to its operator or to external systems.

## Short answer

OpenBao is a self-hosted, open-source, community-governed **identity-based
secrets and encryption management system**.  In everyday terms, it is a server
and HTTP API through which people and workloads can authenticate, receive a
policy-limited token, and then read, generate, lease, revoke, or use sensitive
material.  It is not merely an encrypted file format or a password manager:
it can be the control plane for stored secrets, dynamically-issued credentials,
and cryptographic operations.

OpenBao is a fork of HashiCorp Vault.  The project describes itself as managed
under the Linux Foundation's OpenSSF; its source repository is MPL-2.0 and says
that the community intends open governance.  “Fork” is the important factual
relationship: the systems have common lineage and OpenBao documents API
compatibility goals in places, but OpenBao is an independently developed project,
so compatibility must be checked against the particular OpenBao version and
feature in use.

## What it manages

OpenBao's pluggable **secrets engines**, mounted at paths, can do three broad
things:

- **Store secrets:** for example, encrypted arbitrary key/value values.
- **Generate and manage secrets:** for example, a database engine can create a
  unique database username/password on request, return it with a lease, and
  revoke it when that lease expires.
- **Perform cryptography without retaining the caller's payload:** the Transit
  engine encrypts/decrypts application data and can sign/verify, hash/HMAC, and
  generate random bytes.  It stores its named cryptographic keys and metadata,
  but explicitly does *not* store data submitted for Transit operations.

Thus “secrets manager” is only part of the picture.  With a KV engine, OpenBao
is a protected secret store.  With a database, PKI, cloud, or similar engine,
it is also a broker which needs enough authority in that external system to
create or revoke credentials.  With Transit, it is centralized key management
and cryptography-as-a-service; application ciphertext normally remains in the
application's primary datastore.

## Request and security model

The usual request path is:

```text
client --TLS/API--> auth method --> token + policies --> secrets engine
                                               |              |
                                            ACL decision    secret / lease
```

An auth method verifies supplied user or workload information against an
internal or external identity system.  On success it issues a token associated
with policies.  Policies are path-and-operation ACL rules and are deny by
default; the core uses them to decide whether a token may perform the requested
operation.  Leased tokens and generated secrets can be renewed or revoked, and
the expiration manager revokes a secret whose lease expires.

The API is the product boundary: the CLI uses the same HTTP API, and the API is
intended to be accessed over TLS.  Audit devices can record requests and
responses, but audit logging must be configured; it is not a substitute for
external log retention, alerting, or a review process.

## Storage, encryption, and sealing

OpenBao persists its own state—stored-secret values, engine/auth/audit
configuration, policies, tokens and related metadata—in a configured storage
backend.  That backend is deliberately treated as untrusted: OpenBao's
**barrier** encrypts data before it leaves the server for storage, and verifies
the GCM authentication tag when decrypting it.  A raw backend snapshot therefore
does not by itself disclose the encrypted contents, although it can reveal that
material exists and an attacker able to control the backend can delete, corrupt,
or roll back data.

At startup OpenBao is normally **sealed**: it knows how to reach storage but
cannot decrypt it.  Unsealing obtains the root key needed to recover the
keyring/data-encryption key.  The default Shamir seal splits the unseal key into
a configured threshold of shares.  Alternatively, Auto Unseal delegates
protection of the root key to a configured KMS, HSM, or other seal service.  It
reduces manual startup work but creates an availability and lifecycle dependency
on that seal mechanism; deleting or permanently losing that mechanism/key can
make the cluster unrecoverable, including from backups.

## Operational boundaries and cautions

OpenBao provides encryption, authentication/authorization, leasing, and optional
auditing inside its boundary.  It does **not** make these surrounding risks go
away:

- A compromise of a running server's memory can expose confidential material.
- A storage attacker can cause availability/integrity failures even though the
  stored contents are encrypted; OpenBao does not claim to protect against
  arbitrary control of its backend.
- An external identity provider, database, cloud, KMS/HSM, or plugin remains a
  separate trust and availability dependency.  For dynamic secrets, OpenBao's
  external-system credentials and permissions must be protected and narrowly
  scoped.
- OpenBao configuration and deployment artifacts can themselves be sensitive:
  a backup of encrypted storage differs from a backup that also contains, for
  example, a Transit Auto Unseal token or TLS private key.

So OpenBao is best understood as a sensitive, highly privileged security
service—not a way to eliminate secret-management design.  Its deployment still
needs network protection, TLS and identity design, carefully scoped policies,
durable backups/restore testing, audit handling, and an explicit plan for the
seal and every external system it can control.

## Sources

- [OpenBao homepage — project definition, Vault fork, OpenSSF stewardship, and principal use cases](https://openbao.org/)
- [OpenBao source README — sensitive-data purpose, open-governance intent, and source license](https://github.com/openbao/openbao#readme)
- [Project roadmap post — the project describes itself as a fork](https://openbao.org/blog/roadmap/)
- [Architecture — barrier, request flow, auth/policies/tokens, leases, audit, and auto-unseal overview](https://openbao.org/docs/next/internals/architecture/)
- [Secrets engines — store, generate, or encrypt; path mounting and isolation](https://openbao.org/docs/next/secrets/)
- [Database secrets engine — dynamic credentials, leases, revocation, and external database authority](https://openbao.org/docs/2.5.x/secrets/databases/)
- [Transit secrets engine — encryption as a service and the payload non-storage property](https://openbao.org/docs/secrets/transit/)
- [Authentication](https://openbao.org/docs/concepts/auth/) and [policies](https://openbao.org/docs/2.5.x/concepts/policies/)
- [HTTP API — API/CLI relationship and TLS expectation](https://openbao.org/api-docs/2.4.x/)
- [Seal/Unseal — sealed state, Shamir, Auto Unseal, and recovery limitation](https://openbao.org/docs/next/concepts/seal/)
- [Storage — encrypted backend data and backup/configuration distinction](https://openbao.org/docs/concepts/storage/)
- [Security model — barrier encryption/integrity and stated threat-model exclusions](https://openbao.org/docs/internals/security/)
