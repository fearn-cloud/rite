# Backup Substrate and PBS Storage Registration PRD

Status: ready-for-agent

## Problem Statement

The operator wants Backup Configure to fully prepare the PVE-side target required for fortress-owned Backup Jobs, without reopening general Proxmox storage automation. Today the project has Backup Policies, Backup Jobs, Backup Readiness, Backup Health, and a local PBS recovery model, but the Backup Job target is still blurred with the PBS Datastore. The planner talks as though Backup Jobs target the Primary Datastore directly, while Proxmox actually needs a Host-local PBS Storage Registration such as `rite-pbs` that points at the PBS Datastore.

The operator also wants this storage registration to be safe. General Proxmox storage registration remains operator-controlled because disk and pool mistakes are destructive. PBS Storage Registration is narrower, but it still crosses trust, credential, and Host boundaries. The repo needs a declared Backup Substrate so Backup Configure can derive `rite-pbs`, PBS Service endpoint, Primary Datastore, TLS trust material, and per-Host PBS token references from Inventory instead of hardcoded assumptions.

## Solution

Introduce a first-class Backup Substrate model as the fleet-level foundation for backups. The Backup Substrate declares the single local PBS Service, the PVE PBS Storage Registration ID `rite-pbs`, the Primary Datastore, PBS TLS trust material, and per-Host PBS token references. It is required whenever at least one production VM is a Backup Target, but it should not be added to real Inventory until the required token and trust artifacts exist.

Teach static validation to prove that Backup Targets have a complete declared substrate. Validation should confirm the PBS Service shape, the local PBS backend VM, the NAS-backed Primary Datastore mount, the local PBS VM's Unprotected VM status, the PBS Storage Registration ID, TLS fingerprint declaration, and per-Host token references for Hosts with Backup Targets. Validation checks encrypted SOPS files structurally for referenced secret paths; secret decryption belongs only to workflows that consume those secrets.

Clean up Backup Configure planning terminology so Backup Jobs target the PBS Storage Registration `rite-pbs`, while `rite-pbs` points at the PBS Datastore such as `pbs-datastore`. Plan output should show storage registration actions separately from Backup Job actions. The first implementation slice should stop at schema, loading, validation, planner terminology, and plan rendering. Live PVE storage reconciliation, PBS Configure, token creation, TLS certificate creation, and Backup Readiness live checks come later.

## User Stories

1. As the operator, I want a declared Backup Substrate, so that Backup Configure derives backup infrastructure from Inventory instead of hidden defaults.
2. As the operator, I want Backup Substrate to include the PBS Service, so that backup workflows know which Service provides PBS.
3. As the operator, I want Backup Substrate to include the PBS Storage Registration ID `rite-pbs`, so that PVE Backup Jobs have a stable Host-side storage target.
4. As the operator, I want Backup Substrate to include the Primary Datastore, so that `rite-pbs` points at the intended PBS snapshot location.
5. As the operator, I want Backup Substrate to include PBS TLS trust material, so that PVE Hosts do not connect to PBS with unpinned trust.
6. As the operator, I want Backup Substrate to include per-Host PBS token references, so that each Host can authenticate to PBS without sharing one fleet-wide token.
7. As the operator, I want Backup Substrate required when any production VM is a Backup Target, so that backup intent cannot exist without declared backing infrastructure.
8. As the operator, I want Backup Substrate optional when there are no Backup Targets, so that PBS can exist before backup protection is active.
9. As the operator, I want `pbs-vm` to remain an Unprotected VM, so that local PBS does not pretend to back itself up.
10. As the operator, I want Backup Substrate validation to require the local PBS backend VM to be Unprotected, so that the recovery model is enforced.
11. As the operator, I want the Primary Datastore to be NAS-backed, so that PBS recovery does not depend on VM-local backup storage.
12. As the operator, I want the PBS VM to mount the Primary Datastore read-write, so that PBS can actually write Backup Runs.
13. As the operator, I want validation to reject a missing PBS Service, so that backup workflows cannot silently fall back to a hardcoded VM name.
14. As the operator, I want validation to reject an ambiguous or malformed PBS Service, so that Backup Configure has one clear PBS endpoint.
15. As the operator, I want validation to derive the PBS server address from the PBS VM's declared static interface, so that each Host uses the declared network model.
16. As the operator, I want validation to derive the PBS port from the PBS Service backend, so that the Service model owns the application port.
17. As the operator, I want validation to reject a PBS VM without a usable static address, so that Backup Configure does not create unusable Host storage.
18. As the operator, I want the Backup Job target called PBS Storage Registration rather than Primary Datastore, so that plan output matches Proxmox reality.
19. As the operator, I want Backup Jobs to target `rite-pbs`, so that all Backup Policies use the same local PBS storage target for now.
20. As the operator, I want `rite-pbs` to point at `pbs-datastore`, so that future Backup Runs land in the Primary Datastore.
21. As the operator, I want Backup Configure plans to show storage registration actions separately, so that I can distinguish Host-side storage changes from Backup Job changes.
22. As the operator, I want Backup Configure plans to show job actions separately, so that VM backup scheduling remains reviewable.
23. As the operator, I want a Host with Backup Targets to require a per-Host PBS token reference, so that missing credentials are caught before mutation.
24. As the operator, I want Hosts without Backup Targets not to require PBS token references, so that unused Hosts do not block the repo.
25. As the operator, I want extra Host token references allowed, so that PBS Configure can prepare future Hosts without forcing immediate Backup Targets.
26. As the operator, I want token references to point into the PBS Service sibling SOPS file, so that PBS-side credentials stay owned by the PBS Service boundary.
27. As the operator, I want static validation to check encrypted SOPS key paths structurally, so that missing secret slots are caught without decrypting secrets.
28. As the operator, I want static validation to avoid decrypting PBS tokens, so that inventory checks do not require private key material.
29. As the operator, I want secret decryption limited to consuming workflows, so that token handling follows existing workflow primitives.
30. As the operator, I want Backup Configure to consume identities rather than mint them, so that PVE identity lifecycle, PBS identity lifecycle, and backup mutation stay separate.
31. As the operator, I want Host Configure to own the PVE backup identity, so that Host-side PVE users, roles, ACLs, and tokens remain in one workflow.
32. As the operator, I want PBS Configure to own PBS API tokens and TLS trust material, so that PBS-side identity and certificate lifecycle stay in one workflow.
33. As the operator, I want Backup Configure to fail when prerequisite identities are missing, so that it does not fall back to root, Tofu, or shared PBS credentials.
34. As the operator, I want the first slice to avoid live PVE mutation, so that the declared model can be made precise before apply behavior is added.
35. As the operator, I want real Inventory left unchanged until PBS Configure artifacts exist, so that repository validation does not fail on placeholder secrets.
36. As an implementing agent, I want a deep Backup Substrate module, so that loading, derivation, and validation can be tested without live Proxmox or PBS.
37. As an implementing agent, I want Backup Configure's plan model to expose storage actions and job actions separately, so that rendering and apply can evolve cleanly.
38. As an implementing agent, I want fixtures that include a complete Backup Substrate, so that planner and validation behavior can be proven without touching real Inventory.
39. As future-self, I want ADR 0013 preserved for general storage, so that this narrow carve-out does not become broad Proxmox storage automation.
40. As future-self, I want ADR 0039 and ADR 0040 respected, so that Backup Configure owns `rite-pbs` but not credential creation.

## Implementation Decisions

- Add a singular Backup Substrate inventory contract. It is not a list and does not model multiple PBS instances, offsite backup targets, archive targets, or policy-selected storage.
- The Backup Substrate is required only when at least one production VM is a Backup Target.
- The Backup Substrate declares the PBS Service, PBS Storage Registration ID, Primary Datastore, TLS fingerprint, and per-Host PBS token references.
- The canonical PBS Storage Registration ID is `rite-pbs`.
- The Primary Datastore remains the PBS Datastore, currently `pbs-datastore`, and is distinct from the PVE storage ID `rite-pbs`.
- The PBS server address is derived from the PBS Service backend VM's declared static interface address.
- The PBS server port is derived from the PBS Service backend port.
- Backup Policies continue to express schedule and retention. They do not select alternate storage registrations in this PRD.
- Backup Jobs target `rite-pbs`; `rite-pbs` points at the Primary Datastore.
- Do not add real Backup Substrate inventory until PBS Configure or equivalent real artifacts can provide token and TLS trust material.
- Existing PBS substrate inspection should be deepened or wrapped so it can derive the new Backup Substrate facts through a compact, testable interface.
- Inventory loading should expose whether the Backup Substrate file exists and, when present, its parsed declaration.
- Static validation should fail when Backup Targets exist but no Backup Substrate is declared.
- Static validation should fail when the PBS Service is missing, malformed, ambiguous, or not backed by the declared PBS VM.
- Static validation should fail when the PBS VM has no usable static address for Host-to-PBS traffic.
- Static validation should fail when the Primary Datastore is not NAS-backed.
- Static validation should fail when the PBS VM does not mount the Primary Datastore read-write.
- Static validation should fail when the PBS Service backend VM is not an Unprotected VM with a reason.
- Static validation should require a per-Host PBS token reference for each Host that currently has at least one Backup Target.
- Static validation should allow token references for Hosts that currently have no Backup Targets.
- Static validation should inspect encrypted SOPS key structure only. It must not decrypt token values.
- Backup Configure planning should split storage registration actions from Backup Job actions.
- Backup Configure plan text should render storage actions with the PVE storage ID, PBS server, and PBS Datastore.
- Backup Configure plan text should render Backup Job actions with the VM, policy, PVE storage ID, job name, and schedule.
- Backup Configure JSON should preserve the same distinction so a future apply workflow can consume it without guessing which datastore is meant.
- Observed Backup Jobs should compare against the PVE storage ID, not the PBS Datastore name.
- The first slice should not create, update, or prune live PVE storage.
- The first slice should not create, update, or rotate PBS API tokens.
- The first slice should not create or rotate PBS TLS certificates.
- The first slice should not add live Backup Readiness validation for `rite-pbs`.
- General Proxmox storage registration remains operator-controlled. This work is the narrow PBS Storage Registration carve-out recorded in ADR 0039.
- Backup Configure consumes PVE and PBS identities produced by Host Configure and PBS Configure, as recorded in ADR 0040.

## Testing Decisions

- Tests should prove external behavior: loaded Backup Substrate facts, validation errors, plan output, and JSON shape. They should not assert private helper names or incidental parsing steps.
- Add focused tests for Backup Substrate loading and derived facts using fixture inventories.
- Add validation tests for missing substrate when Backup Targets exist.
- Add validation tests showing substrate is optional when no Backup Targets exist.
- Add validation tests for malformed PBS Service, missing PBS VM static address, non-NAS Primary Datastore, non-read-write PBS VM mount, and PBS VM not marked Unprotected.
- Add validation tests for missing per-Host token references on Hosts with Backup Targets.
- Add validation tests proving extra token references for unused Hosts are allowed.
- Add validation tests proving encrypted SOPS key paths are checked structurally without requiring decryption.
- Add Backup Configure plan tests proving storage registration actions render separately from Backup Job actions.
- Add Backup Configure plan tests proving Backup Jobs use `rite-pbs` while the registration points at `pbs-datastore`.
- Update existing Backup Configure plan tests that currently expect `datastore=pbs-datastore` on job actions.
- Update script-level plan tests so text and JSON output preserve the storage/job distinction.
- Use existing PBS substrate tests as prior art for substrate fact derivation and operator-safe secret reporting.
- Use existing inventory cross-file validation tests as prior art for static validation error shape.
- Use existing Backup Configure plan tests as prior art for deterministic schedule, pruning, manual job preservation, and script output behavior.
- Do not add live Proxmox, live PBS, or decrypted secret tests in the first slice.

## Out of Scope

- Live creation or update of `rite-pbs` in PVE.
- Live validation that `rite-pbs` can authenticate to PBS.
- Backup Configure apply behavior for PBS Storage Registration.
- Pruning unused `rite-pbs` registrations.
- Dangerous update confirmation for changing PBS server address or PBS Datastore.
- PBS Configure workflow implementation.
- PBS API token creation, rotation, or revocation.
- PBS TLS certificate creation, renewal, fingerprint refresh, or rotation state.
- Host Configure implementation for the dedicated PVE backup identity.
- Backup Readiness live checks for valid PBS Storage Registration.
- Multiple Backup Substrates.
- Offsite PBS, archive PBS, or policy-selected storage backends.
- Adding real Backup Substrate inventory with placeholder secrets.
- Broad Proxmox storage automation beyond the `rite-pbs` carve-out.

## Further Notes

This PRD follows the resolved glossary terms in `CONTEXT.md`: Backup Substrate, PBS Storage Registration, Primary Datastore, Backup Configure, PBS Configure, Backup Target, Unprotected VM, Backup Readiness, and Recovery Secret.

The key domain split is that `pbs-datastore` is the PBS Datastore / Primary Datastore, while `rite-pbs` is the PVE-side PBS Storage Registration that Backup Jobs target.

Relevant ADRs are ADR 0013 for general operator-controlled storage, ADR 0039 for the PBS Storage Registration carve-out, and ADR 0040 for identity ownership boundaries.
