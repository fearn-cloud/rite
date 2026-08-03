# Existing projects analogous to Rite's Rite–Canon direction

Research date: 2026-07-29. Scope: the direction in [Rite issue
#221](https://git.fearn.cloud/fearn-cloud/rite/issues/221): Rite realizes an
independently recoverable substrate (Hosts, VM lifecycle, networking, storage,
access, backups, and observability primitives), while Canon owns K3s-cluster
lifecycle and in-cluster concerns. This is a comparison of published project
boundaries, not a recommendation to adopt a project.

## Finding

There is no close, drop-in equivalent to the whole pair. The nearest existing
project is **Sidero Omni**, but it deliberately combines the substrate-provider
and Kubernetes-cluster layers around Talos. The closest reusable *architecture*
is **Cluster API** (and its K3s provider), but its controllers require a
Kubernetes management cluster. **MAAS + Juju** is the long-established
substrate/consumer split, but is oriented to pooled bare metal and Canonical's
model rather than a small, explicitly recoverable Proxmox fleet. **Gardener**
is a useful large-scale precedent for provider/consumer contracts and backup
responsibility, though it also makes Kubernetes a management dependency.

| Project | What is analogous | Material mismatch with Rite–Canon |
| --- | --- | --- |
| [Sidero Omni](https://docs.siderolabs.com/omni/infrastructure-and-extensions/infrastructure-providers) | Infrastructure providers manage static machines or create/destroy VMs, while Omni allocates them into Kubernetes clusters. Its current provider list includes Proxmox. | Omni owns the Kubernetes layer and is Talos-specific; it is not a separate substrate provider handing a generic readiness/evidence contract to an independently governed Canon. Its bare-metal provider also requires an Omni instance and an image factory reachable by the machines. [Provider model](https://docs.siderolabs.com/omni/infrastructure-and-extensions/infrastructure-providers) [bare-metal requirements](https://docs.siderolabs.com/omni/omni-cluster-setup/setting-up-the-bare-metal-infrastructure-provider) |
| [Cluster API](https://cluster-api.sigs.k8s.io/) + [cluster-api-k3s](https://github.com/k3s-io/cluster-api-k3s) | The canonical provider decomposition: infrastructure providers create machines; bootstrap and control-plane providers turn them into a cluster. The K3s provider specifically creates cloud-init instructions and manages K3s control-plane machine lifecycle. | Cluster API is explicitly a Kubernetes-style cluster lifecycle system, and requires an existing Kubernetes management cluster. This makes its management/recovery dependency materially different from Canon's requirement for an external recovery substrate. It also excludes lifecycle of infrastructure unrelated to Kubernetes. [CAPI goals/non-goals](https://cluster-api.sigs.k8s.io/introduction) [management-cluster prerequisite](https://cluster-api.sigs.k8s.io/user/quick-start) [K3s provider](https://github.com/k3s-io/cluster-api-k3s) |
| [MAAS](https://canonical.com/maas/docs/latest/) + [Juju](https://canonical.com/maas/docs/latest/uncategorized/what-maas-can-do/) | A mature provider/consumer composition: MAAS commissions, allocates, deploys, and tests bare-metal or virtual machines; Juju can consume MAAS as a provider to deploy systems including Kubernetes. Its commissioning/allocated-before-deployment sequence resembles substrate readiness prior to a consumer taking control. | MAAS is a data-centre resource pool and owns DHCP/DNS/PXE/BMC workflows. It is not an inventory-and-evidence control plane for a few standalone Proxmox Hosts, and its documented handoff is resource allocation rather than a versioned, cross-repository readiness/acceptance record. [Machine deployment lifecycle](https://canonical.com/maas/docs/latest/explanation/deploying-machines/) |
| [Gardener](https://gardener.cloud/contribute/gardener/new-cloud-provider/) | Its provider integration contract separates shoot-cluster intentions from provider machine/infrastructure lifecycle and separately assigns backup/restore responsibility. That is strong precedent for keeping capability-specific contracts explicit. | Gardener's Seed Kubernetes cluster deploys/manages Shoot control planes and hosts their etcd deployments. It is a multi-tenant managed-Kubernetes architecture, not an external substrate that remains usable with every workload cluster down. [Seed/Shoot model and provider contract](https://gardener.cloud/contribute/gardener/new-cloud-provider/) |

## What is worth borrowing

- From Omni: a narrow infrastructure-provider interface that reports machine
  availability and keeps credentials scoped per provider/location—without
  absorbing Canon's cluster policy.
- From Cluster API: separate, versioned infrastructure, bootstrap, and
  control-plane contracts. Do **not** inherit its requirement to keep a
  management Kubernetes cluster alive.
- From MAAS: a distinct commissioning/readiness stage before allocation to a
  consumer; Rite's evidence should be more durable and recovery-oriented than
  MAAS's allocation state.
- From Gardener: spell out backup/restore ownership at the seam instead of
  assuming that VM backup implies cluster/application recovery.

## Bottom line

Rite is not recreating a missing basic provisioner. Existing systems cover the
mechanics, and Omni is notably close operationally. The distinctive part is the
small-fleet, operator-first, **recoverable external substrate** with explicit
plans and readiness evidence handed to a separately governed cluster layer.
That boundary is closer to a deliberately constrained composition of the above
patterns than to a feature-for-feature clone of any one project.
