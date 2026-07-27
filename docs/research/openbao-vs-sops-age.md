# Should Rite replace SOPS + age with OpenBao?

**Recommendation: no—not for the current Rite secret model.** Keep SOPS + age
as the authoritative store for Git-managed, long-lived operator and deployment
secrets. Revisit OpenBao when Rite has a concrete need for independently
authenticated workloads, short-lived generated credentials, centralized
revocation/audit, or more than the current small set of trusted secret
consumers. If that point arrives, use OpenBao *in addition to* SOPS + age at
first; do not make an online secrets service the bootstrap dependency for the
repository and its recovery material.

This is a decision about the current single-Operator, small self-owned fleet,
not a claim that OpenBao is unsuitable. They solve overlapping but materially
different problems.

## What changes, and what does not

| Question | SOPS + age in Rite today | OpenBao |
| --- | --- | --- |
| Primary unit | An encrypted, versioned file committed beside its Entity YAML. | A network API service with stored data, auth methods, policies, tokens, and secrets engines. |
| Access decision | Possession of an age private identity able to unwrap the file data key. | A client authenticates, receives a policy-bearing token, then is allowed or denied per API path. |
| Natural use | Durable, reviewable configuration secrets that must travel with declared Inventory and be recoverable from Git plus offline key material. | Runtime secrets delivery; per-workload access; dynamic credentials and revocation; centralized API audit. |
| Failure dependency while operating from a recovered checkout | No secret server: an authorized workstation can decrypt locally. | The Bao server, its storage, network/TLS, unseal mechanism, client auth, and policy configuration must be working. |
| Git visibility | Git records encrypted revisions and SOPS retains YAML keys/shape for review; SOPS encrypts values and binds their paths into its authenticated encryption/MAC. | Git can version policy/config-as-code, but not the stored secret values unless the team exports them (which defeats the usual reason to centralize them). |

SOPS encrypts YAML leaf values while leaving keys clear, authenticates the
structure, and supports multiple master keys/recipients. `age` is the small
recipient/identity encryption tool underneath this repository's SOPS setup.
[SOPS design and formats](https://github.com/getsops/sops#34-yaml-json-env-and-ini-type-extensions)
[SOPS integrity and key model](https://github.com/getsops/sops#61-message-authentication-code)
[age usage and recipient identities](https://github.com/FiloSottile/age#usage)

OpenBao's KV engine can store arbitrary values, but that alone does not turn it
into a better SOPS replacement: KV v1 paths/key names are not encrypted, and
its optional TTL is advisory rather than automatic deletion. Its differentiated
value appears when callers authenticate separately and policies control their
allowed paths, or when a secrets engine generates and leases credentials.
[OpenBao KV v1](https://openbao.org/docs/secrets/kv/kv-v1/)
[OpenBao authentication](https://openbao.org/docs/concepts/auth/)
[OpenBao security model](https://openbao.org/docs/internals/security/)

## Current Rite fit

Rite deliberately chose a very narrow trust model:

- Per-Entity Sibling SOPS Files keep secrets co-located with the Inventory they
  support, including structured metadata for rotation.
- The intended steady state is one Operator workstation identity plus an
  offline backup identity. The validation runner is explicitly not a recipient;
  a future deployment runner needs a separate design before it gets any secret
  access.
- Workflows decrypt only at the consumption point: SSH keys into tmpfs, PVE and
  NAS credentials into private child-process environments, and Service secrets
  into Podman secrets/root-owned VM files. OpenTofu does not decrypt files or
  receive a SOPS provider.

Those are not incidental implementation details. They support the current
recovery ceremony: clone the repository, restore the operator or offline age
identity, and decrypt locally before any Host or VM workflow. See local
[ADR 0005](../adr/0005-sops-age-two-recipients.md),
[ADR 0006](../adr/0006-tofu-never-reads-sops.md),
[ADR 0023](../adr/0023-service-secrets-are-structured-per-service-sops-entries.md),
and [initial setup](../../runbooks/initial-setup.md).

Replacing these files with OpenBao KV now would add a privileged Service and
several bootstrap questions without removing a demonstrated limitation. For
example, a Service deployment would need a machine auth credential (such as an
AppRole role/secret pair or another workload identity) merely to retrieve its
static password. That credential must itself be delivered and rotated securely.
OpenBao describes AppRole as intended for automated machines/apps, and it maps
login constraints to policies; it is not an unauthenticated secret endpoint.
[OpenBao AppRole](https://openbao.org/docs/auth/approle/)

## Security, availability, and trust trade-off

OpenBao has strong controls worth wanting when the problem needs them: default
deny policy enforcement, expiring/revocable tokens, and request/response audit
devices. However those features introduce a new security-critical control
plane. Its storage is encrypted by OpenBao's barrier, but availability and
integrity still depend on correctly operating and backing up that service and
its storage. OpenBao's own storage guidance says to protect both encrypted data
and service configuration/management scripts, since configuration can contain
sensitive material.
[OpenBao security model](https://openbao.org/docs/internals/security/)
[OpenBao storage and backups](https://openbao.org/docs/concepts/storage/)
[OpenBao audit devices](https://openbao.org/docs/audit/)

OpenBao begins sealed. With the default Shamir seal, a restart requires the
unseal threshold before it can serve normal requests. Auto-unseal moves that
dependency to a KMS/HSM or other seal service; if that mechanism is permanently
lost, OpenBao says the cluster cannot be recovered even from backups. A static
key auto-unseal is specifically recommended only where another trusted secret
source already injects the key—so it does not eliminate Rite's bootstrap-secret
question.
[Seal/unseal and auto-unseal dependency](https://openbao.org/docs/next/concepts/seal/)
[static auto-unseal warning](https://openbao.org/docs/configuration/seal/static/)

A single OpenBao VM with filesystem storage would be an especially poor
substitute for locally decryptable SOPS files: OpenBao documents that backend
as non-HA and not recommended for production. HA is possible, but it requires
multiple unsealed servers and an HA-capable storage backend; it protects service
availability, not horizontal throughput.
[filesystem storage limitations](https://openbao.org/docs/2.5.x/configuration/storage/filesystem/)
[OpenBao HA](https://openbao.org/docs/concepts/ha/)

The practical result is a trust-boundary exchange:

```text
Current:  Git + authorized age identity -> decrypt locally -> targeted workflow

OpenBao:  workload identity + TLS/network + Bao availability + unseal/seal
          dependency + policy correctness -> API read -> targeted workflow
```

Neither is universally safer. SOPS + age concentrates access in long-lived age
identities and has no per-read server audit. OpenBao can reduce a workload's
scope and revoke it centrally, but makes the OpenBao operator, policy system,
seal mechanism, storage backups, and service availability part of the secret
trust boundary.

## When to introduce OpenBao

Adopt it for a specific new capability, rather than as a general replacement,
when one or more of these becomes true:

1. A Service needs database, PKI, cloud, or other credentials that should be
   generated per consumer, leased, and revoked rather than stored as durable
   static Inventory values.
2. Several Services or automation identities need distinct, independently
   revocable least-privilege access, and putting an age identity on each is no
   longer acceptable.
3. Auditable secret reads and a central emergency-revocation mechanism are a
   real operational requirement.
4. Rite has a supported, recoverable management-plane platform for a secret
   service, including monitoring, backups and restore drills, TLS, identity,
   seal-key custody, and an availability target appropriate for the secrets it
   serves.

For example, dynamic credentials are a genuine functional expansion: OpenBao's
secrets engines can issue credentials with leases and revoke them; a static KV
entry does not automatically expire or delete on TTL.
[OpenBao dynamic secrets and leases](https://openbao.org/docs/what-is-openbao/)
[OpenBao KV TTL behaviour](https://openbao.org/docs/secrets/kv/kv-v1/#ttls)

## Safe hybrid path and migration gate

The suitable first architecture is layered:

```text
SOPS + age: recovery keys, initial Bao configuration, seal/bootstrap material,
            break-glass operator access, and long-lived Inventory-bound values.

OpenBao:    only workload-facing or dynamically issued secrets whose benefits
            justify online delivery; policies and non-secret configuration stay
            reviewed in Git.
```

Do not use OpenBao to hold the only material needed to unseal, restore, or
initially configure itself. This would make recovery circular. Keep offline,
tested recovery material outside that dependency, consistent with Rite's
existing operator-workstation recovery model.

Before moving even one secret class, write an ADR and demonstrate all of the
following in an isolated acceptance environment:

1. **Consumer identity:** every human, management runner, and Service has a
   least-privilege auth method; the initial credential and its rotation path are
   documented without embedding a reusable broad token in Inventory.
2. **Policy and audit:** policies are versioned/reviewed, deny cross-Service
   reads, and audit logs are collected securely without exposing secret values.
3. **Availability:** a sealed/restarted server, unavailable storage, and lost
   network produce understood failures. Choose either a consciously accepted
   single-service risk or a tested HA design—not an accidental single point of
   failure.
4. **Recovery:** restore a storage snapshot and configuration into an isolated
   environment; exercise Shamir or auto-unseal recovery and prove that the
   necessary offline material is available. Backups alone are insufficient if
   the required seal mechanism has been irretrievably lost.
5. **Workflow integration:** preserve the current no-plaintext-on-persistent-
   disk and no-secret-in-Tofu-state/plan/log rules. Fetch only immediately
   before the consuming process, use a short-lived token, and ensure failures
   do not print tokens or values.
6. **Cutover and rollback:** migrate a single low-blast-radius Service secret,
   retain a time-bounded SOPS rollback copy under the existing recipient model,
   rotate the old value after cutover, and test both rollback and revocation.

Until those requirements are driven by a concrete consumer and proven, SOPS +
age remains the simpler system with the stronger match to Rite's declared
Inventory, offline recovery, and single-Operator operating model.
