Status: ready-for-human

# Refresh ingress docs and workflow surfaces

## What to build

Refresh operator-facing docs, workflow help, runbooks, and acceptance expectations so they describe Service Ingress Routes instead of the legacy Service hostname / `ingress.enabled` / Backend port model. New-service guidance and live-proof docs should make it clear that Service Ingress Routes target VM host Published Ports.

This issue is ingress-model work only. Do not add Hermes-specific documentation.

## Acceptance criteria

- [ ] Architecture and runbook prose describe `ingress_routes` as the Service ingress declaration.
- [ ] New-service guidance shows a Service Ingress Route rather than top-level Service hostname and `ingress.enabled`.
- [ ] Workflow help or operator-facing output names Service Ingress Routes where it discusses Ingress Regeneration.
- [ ] Acceptance or live-proof documentation names Service Ingress Routes and VM host Published Ports consistently with `CONTEXT.md`.
- [ ] No docs or workflow tests continue to describe `published_ports[].ingress` as the ingress opt-in.

## Blocked by

- .scratch/service-ingress-routes/issues/03-migrate-existing-service-inventory-to-ingress-routes.md
