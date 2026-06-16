Status: ready-for-human

# Migrate existing Service inventory to ingress_routes

## What to build

Migrate the checked-in non-Hermes Service inventory from the legacy one-route ingress shape to canonical Service Ingress Routes, then retire the legacy shape from the service contract. Services without ingress should have no Service Ingress Routes. Services with direct non-HTTP or administration ports should keep those ports as Published Ports without treating them as Ingress routes.

This issue is ingress-model work only. Ignore uncommitted Hermes files and do not edit them.

## Acceptance criteria

- [ ] Existing non-Hermes Service YAML no longer uses top-level Service `hostname`, Service `ingress`, `backend.port`, or `published_ports[].ingress`.
- [ ] Existing ingress-enabled Services declare equivalent `ingress_routes` entries preserving hostname, LAN-only exposure, TLS, auth, and VM host Published Port.
- [ ] Native Services that do not expose a Service Ingress Route no longer carry orphan Service Backend ports.
- [ ] Direct non-Ingress Published Ports remain declared where needed and are not modeled as Service Ingress Routes.
- [ ] Service schema rejects top-level Service `hostname`, Service `ingress`, `backend.port`, and `published_ports[].ingress`.
- [ ] Model loading no longer injects default Service `ingress` data.
- [ ] Runtime Intent and Inventory Entity Graph no longer expose or depend on Service Backend ports for Ingress.
- [ ] Repository inventory validation passes without depending on Hermes inventory files.
- [ ] Tests or fixtures that encode existing Service inventory are updated to the canonical route shape.

## Blocked by

- .scratch/service-ingress-routes/issues/01-service-ingress-route-inventory-contract.md
- .scratch/service-ingress-routes/issues/02-generate-ingress-from-service-ingress-routes.md
