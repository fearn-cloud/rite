# Architecture Deepening Findings

Status: exploratory findings
Date: 2026-05-15

This note records the architecture review findings from the `improve-codebase-architecture` pass so they survive context compaction. No implementation has been chosen yet.

## Source Context

- Domain language: `CONTEXT.md`
- ADR constraints: `docs/adr/`
- Main explored surfaces: `scripts/`, `fortress_inventory/`, `fortress_services/`, `fortress_ingress/`, `fortress_nas/`, `fortress_tofu/`, `tests/`

## Framing

The recurring architectural friction is that several Modules expose broad Interfaces made of raw dicts, shell argv, generated files, subprocess order, and implementation-specific strings. The goal of these candidates is to deepen those Modules: more behavior behind smaller Interfaces, with better Leverage for callers and better Locality for maintainers and tests.

These candidates should preserve the settled ADRs:

- Flat per-Entity YAML remains the Inventory source of truth.
- Workflow wrappers compose existing ceremonies rather than inventing new deployment engines.
- OpenTofu provisions VM shells; Ansible configures everything else.
- SOPS secrets stay out of HCL and decrypted SSH keys stay tmpfs-only.
- Acceptance Tests may create disposable Operational VMs and Ephemeral Datasets.

## Candidate Shortlist

### 1. Acceptance Test Harness Module

Files:

- `scripts/acceptance-nfs-shared-mount`
- `scripts/acceptance-service-layer`
- `scripts/acceptance-clean-generated-artifacts`

Problem:

NFS shared-mount and Service-layer Acceptance Tests duplicate intent resolution, bridge derivation, generated Operational VM Inventory, Ephemeral Dataset handling, SSH checks, NAS Reconcile assertions, and cleanup. The current Interface is nearly "know every shell effect in order", so the Modules are shallow.

Solution:

Create a deeper Acceptance Test harness Module around Acceptance Policy, Host, Template, NAS Endpoint, Primary Acceptance VM, and Peer Acceptance VM. Keep workflow commands, SSH, NAS Reconcile, and file writes as Adapters at explicit Seams.

Benefits:

Better Locality for generated Inventory safety and cleanup rules. Better Leverage because each new Acceptance Test can reuse the same lifecycle instead of re-learning the whole ceremony.

### 2. Service Deploy Plan Module

Files:

- `fortress_services/deploy.py`
- `fortress_services/quadlet.py`
- `scripts/service-deploy`
- `fortress_inventory/validate.py`

Problem:

Service Deploy knowledge is split across validation, Quadlet rendering, Native Deploy vars, Service Secret preflights, Share-backed Volume paths, Container Dependency ordering, and Ansible extra vars. Tests often assert raw Ansible vars or playbook choreography.

Solution:

Deepen Service Deploy into a plan Module that concentrates the Service's runtime artifacts, secret requirements, start/stop units, Service Data Directories, Native config files, and deploy actions.

Benefits:

Tests can target the Service Deploy contract instead of implementation strings. Changes to Quadlet, Native Deploy, or Service Secret behavior gain Locality.

### 3. Inventory Entity Graph Module

Files:

- `fortress_inventory/model.py`
- `fortress_inventory/validate.py`
- `fortress_ingress/generate.py`
- `fortress_nas/reconcile.py`
- `inventory/plugins/fortress.py`

Problem:

`InventoryModel` is currently a shallow dict bag. Callers repeatedly know YAML shape for VM static addresses, Host management addresses, Backend lookup, Dataset lookup, Mounts, generated Operational VM policy, and Ingress facts.

Solution:

Add an Inventory query Module over flat YAML. ADR-0003 stays intact: YAML remains source of truth, but domain queries stop leaking across packages. The first design question is whether this should be a read-only view over raw Inventory YAML or a richer normalization layer. Current default: start as a read-only view.

Benefits:

Higher Depth for all callers. Validation, Ingress Regeneration, NAS Reconcile, Ansible inventory, and workflow scripts get Leverage from shared domain facts.

### 4. NAS Reconcile Plan Module With Apply Seam

Files:

- `fortress_nas/reconcile.py`
- `fortress_nas/truenas_client.py`
- `fortress_nas/truenas_reality.py`
- `scripts/nas-reconcile-plan`

Problem:

NAS Reconcile Plan mixes read-only findings, Derived Share planning, Dataset lifecycle policy, Acceptance Test Ephemeral Dataset cleanup, apply sequencing, and redacted connection reporting. The TrueNAS Adapter Seam exists, but the plan Interface is still raw dicts plus flags.

Solution:

Separate the NAS Reconcile Plan value Module from apply Adapters.

Benefits:

Fixture-backed and live runs share one deeper planning surface. Dataset and Derived Share rules gain Locality, and live TrueNAS failure handling becomes easier to test through the Seam.

### 5. VM Lifecycle Convergence / OpenTofu Plan Module

Files:

- `fortress_tofu/generate.py`
- `scripts/vm-up`
- `scripts/vm-destroy`
- `scripts/tofu-wrap`

Problem:

Selected-VM OpenTofu knowledge is scattered: provider coverage, generated HCL, state provider aliases, target resource strings, SOPS-derived env vars, and VM Lifecycle Convergence orchestration.

Solution:

Concentrate selected-VM OpenTofu planning behind one Module. HCL writing, state reading, SOPS extraction, and subprocess execution remain Adapters.

Benefits:

VM Lifecycle callers stop knowing OpenTofu resource addresses. Tests can assert VM Lifecycle intent instead of brittle target strings.

### 6. Operator Workflow Phase Module

Files:

- `scripts/vm-up`
- `scripts/service-launch`
- `scripts/host-up`
- `scripts/template-verify`

Problem:

Multiple workflow Modules reimplement phase ordering, failure reporting, prompts, stdout capture, `auto_confirm`, `keep_on_fail`, and cleanup behavior.

Solution:

Deepen the operator ceremony phase runner while preserving ADR-0027 and ADR-0028: wrappers still compose existing workflows, but phase mechanics live in one place.

Benefits:

Better Locality for failure semantics and progress reporting. More Leverage when adding new workflows.

### 7. Template Build Module

Files:

- `scripts/templates-build`

Problem:

The Template build Implementation exists twice: once locally and once as a quoted remote worker string. Changes to Cloud Image cache, checksum verification, `virt-customize`, or `qm` creation must be made in two places.

Solution:

Extract Template build behavior into a reusable Module with local and remote Adapters.

Benefits:

One Implementation for Template creation gives strong Locality. Remote execution becomes an Adapter choice rather than a second copy of the build logic.

## Suggested Exploration Order

1. Inventory Entity Graph Module
2. Acceptance Test Harness Module
3. Service Deploy Plan Module
4. NAS Reconcile Plan Module With Apply Seam
5. VM Lifecycle Convergence / OpenTofu Plan Module
6. Operator Workflow Phase Module
7. Template Build Module

Rationale:

Inventory queries sit underneath several other candidates. Acceptance Tests have the loudest duplication and highest cleanup risk. Service Deploy and NAS Reconcile both want a plan-first shape. VM Lifecycle and workflow phase handling become easier once the plan shapes are clearer. Template Build is comparatively independent.

## Next Grilling Question

For the Inventory Entity Graph Module:

Should this Module be a read-only view over raw Inventory YAML, or should it become the place where Inventory is normalized into richer domain objects?

Current default:

Start as a read-only view. Preserve flat YAML as the source of truth and expose deeper queries such as Backend VM for Service, static IPv4 for VM, Dataset for Mount, Host bridge matching address, and Ingress route facts. This gives Depth without forcing a large model migration.
