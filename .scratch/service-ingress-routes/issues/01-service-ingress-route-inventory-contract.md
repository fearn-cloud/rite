Status: ready-for-human

# Service Ingress Route inventory contract

## What to build

Introduce Service Ingress Routes as the canonical Service ingress inventory contract. Services should declare one Backend VM and zero or more Service Ingress Routes; route targets point at resolved VM host Published Ports, not container-only ports. The old Service ingress shape should stop being accepted as the canonical model.

This issue should make the route concept available to schema, model loading, Service Runtime Intent, Inventory Entity Graph queries, and cross-file validation so later issues can generate Ingress from it. Compatibility with the existing checked-in legacy inventory may remain until the migration issue lands, but new route facts should be the preferred internal path.

This issue is ingress-model work only. Do not edit Hermes inventory files.

## Acceptance criteria

- [ ] Service schema accepts `ingress_routes` entries with `name`, `hostname`, `published_port`, `exposure`, `tls`, and `auth`.
- [ ] Service schema allows `backend.vm` without `backend.port` for Services that declare route targets through `ingress_routes`.
- [ ] Service Runtime Intent or Inventory Entity Graph exposes Service Ingress Route facts that include Service name, route name, hostname, Backend VM, and resolved VM host Published Port.
- [ ] Cross-file validation requires Service Ingress Route names to be unique within a Service.
- [ ] Cross-file validation requires every Service Ingress Route hostname to be an explicit FQDN under the fleet domain.
- [ ] Cross-file validation requires every Service Ingress Route target to resolve to a declared TCP-capable VM host Published Port on the Service's Backend VM.
- [ ] Cross-file validation keeps direct non-Ingress Published Ports valid when no Service Ingress Route targets them.
- [ ] Tests cover a Service with two Service Ingress Routes targeting two different Published Ports.
- [ ] Tests cover route-name duplication, hostname collision, and missing/non-TCP Published Port failures.

## Blocked by

None - can start immediately
