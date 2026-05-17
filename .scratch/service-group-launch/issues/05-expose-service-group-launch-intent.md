# Expose Service Group Launch intent through the Inventory Entity Graph

Status: ready-for-agent

## Parent

.scratch/service-group-launch/PRD.md

## What to build

Add an Inventory Entity Graph query for Service Group Launch intent. The query should return the requested Service Group name, the shared Backend VM name, ordered Service names, and whether Ingress Regeneration is required. Workflow planning should be able to depend on this deep query instead of duplicating raw YAML traversal.

The query should provide clear domain errors for unknown groups, groups without launch declarations, missing Backend VMs, and groups that violate first-pass shared Backend VM constraints.

## Acceptance criteria

- [ ] Inventory Entity Graph exposes a Service Group Launch intent query.
- [ ] Successful intent includes group name, shared Backend VM, ordered Service names, and whether any launched Service declares Ingress.
- [ ] Unknown Service Groups produce a clear not-found error.
- [ ] Service Groups without VM launch metadata produce a clear not-launchable error.
- [ ] Missing Backend VM or mixed Backend VM cases produce clear Service Group Launch errors.
- [ ] Tests cover successful media intent ordering and Ingress Regeneration requirement.
- [ ] Workflow code does not need to traverse raw Service and VM YAML to discover launch intent.

## Blocked by

- .scratch/service-group-launch/issues/04-declare-and-validate-service-group-launch-order.md

