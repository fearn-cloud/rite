# Declare the service-directory Homepage Service

Status: ready-for-agent

## What to build

Declare Homepage as the `service-directory` Service on `observability-vm`, with stable runtime scaffolding owned by Service Deploy and an ingress route at `directory.fearn.cloud`. The Service identity should use the domain role, while the container can use the Homepage product name.

## Acceptance criteria

- [ ] Inventory declares a `service-directory` Service whose Backend VM is `observability-vm`.
- [ ] The Service exposes an ingress route for `directory.fearn.cloud`.
- [ ] Service Deploy can install the stable Homepage runtime scaffolding without requiring generated Directory Entry config to already exist.
- [ ] The Service is not added to the `observability` Service Group unless a later explicit decision changes that boundary.
- [ ] Fast tests or existing inventory validation prove the declaration is valid.

## Blocked by

None - can start immediately
