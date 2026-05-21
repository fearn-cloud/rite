# Rite

Rite is an operator-first control plane for declaring, validating, and safely converging small self-owned fleets through explicit Operator Workflows.

Rite exists to make infrastructure operations inspectable, resumable, and boring for small self-owned fleets, without pretending that YAML alone is operations.

## Current Fit

Rite is currently a living control plane for one real fleet, not a packaged product. The domain model, workflow runner, validation, and runbooks are intentionally being shaped toward reuse, but this repository is not yet a drop-in tool for arbitrary environments.

Today, Rite is most mature for a single Operator managing standalone Proxmox Hosts with repo-encrypted secrets, declarative Inventory, OpenTofu-provisioned VMs, Ansible configuration, and explicit operator ceremonies.

## Core Model

Rite's model has four main parts:

- **Inventory is declared state.** Flat per-Entity YAML files describe Hosts, VMs, Services, Templates, Datasets, and related policy. Inventory is the source of truth, not a rendered intermediate.
- **Tools have bounded jobs.** OpenTofu provisions VM shells. Ansible configures Hosts, VMs, and Services. Python validation and planning code resolves domain meaning, checks cross-Entity relationships, and composes workflows.
- **Operator Workflows are the interface.** The Operator runs named workflows through `just` and `scripts/`, not loose tool invocations. Workflows expose plans, confirmation gates, and diagnostic labels.
- **Acceptance proves readiness.** Disposable Operational VMs and live checks prove assumptions before ordinary VMs and Services depend on them.

Rite is not trying to hide infrastructure behind a platform abstraction. It keeps the Operator close to the fleet: Inventory is readable, plans are inspectable, generated artifacts are explicit, and workflows stop at decision points.

## First Commands

Start with the command surface and local checks:

```sh
just
just test
```

For real fleet operations, start with the runbooks. Rite is intentionally stateful around Inventory, encrypted secrets, external systems, and operator ceremonies.

## Operator Workflows

Rite commands are organized around operator outcomes.

Bring a Host into service:

```sh
just host-up <host>
```

Create or converge a VM:

```sh
just vm-up <vm>
```

Launch a Service or ordered Service Group:

```sh
just service-launch <service>
just service-group-launch <group>
```

Perform routine in-place maintenance:

```sh
just host-update <host>
just vm-update <vm>
just service-update <service>
just template-update <host> <template>
```

Regenerate derived operating surfaces:

```sh
just ingress-regenerate
just instrumentation-converge
```

Plan or apply external NAS changes:

```sh
just nas-reconcile-live-plan <endpoint>
just nas-reconcile-live <endpoint>
```

Use `just --list` for the complete command surface. Use the runbooks for ceremony details, prerequisites, and stop points.

## Safety Model

Rite's safety model is practical and explicit:

- Secrets remain encrypted in the repo with SOPS and age.
- Decrypted SSH keys live only in tmpfs during workflows.
- OpenTofu never reads SOPS directly.
- Workflows prefer explicit plans, confirmation gates, and refusal over silent mutation.
- Acceptance workflows create disposable Operational VMs to prove assumptions before ordinary VMs and Services depend on them.

## Current Assumptions

This repository currently assumes:

- standalone Proxmox Hosts as the first substrate;
- a Debian-based working environment or the devcontainer;
- SOPS and age for encrypted repo secrets;
- TrueNAS for Dataset and Share reconciliation when NAS workflows are used;
- Cloudflare DNS for the current Ingress setup;
- Tailscale for the current remote-operator access path.

These are current repository assumptions, not the full long-term boundary of Rite.

## Repository Map

```text
inventory/          declared Hosts, VMs, Services, Datasets, and policy
fortress_inventory/ Inventory parsing, validation, and domain queries
fortress_workflows/ Operator Workflow Plans and Runner
fortress_services/  Service runtime intent, Quadlet rendering, observability
fortress_tofu/      generated OpenTofu surfaces
fortress_nas/       TrueNAS reconciliation planning
scripts/            operator entrypoints used by just
runbooks/           procedural guides
docs/adr/           architectural decisions and tradeoffs
```

## Where To Go Next

- New operator workstation: [docs/toolchain.md](docs/toolchain.md), [runbooks/initial-setup.md](runbooks/initial-setup.md)
- Add infrastructure: [runbooks/new-host.md](runbooks/new-host.md), [runbooks/new-vm.md](runbooks/new-vm.md), [runbooks/new-service.md](runbooks/new-service.md)
- Understand the model: [CONTEXT.md](CONTEXT.md), [docs/architecture.md](docs/architecture.md), [docs/adr/](docs/adr/)
- Operate safely: relevant runbooks plus `just --list`

## Status

Rite is pre-packaging and evolving against one real fleet. The domain model, workflow runner, validation, and runbooks are intentionally being shaped toward reuse, but this repository is not yet a drop-in tool for arbitrary environments.
