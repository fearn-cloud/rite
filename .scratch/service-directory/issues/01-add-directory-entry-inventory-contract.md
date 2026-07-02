# Add Directory Entry inventory contract

Status: ready-for-agent

## What to build

Add the first-pass Directory Entry inventory contract so Service, Host, and NAS ingress routes can opt into the Service Directory with route-local presentation intent. A Directory Entry should declare only enabled state, label, and group; the destination URL remains derived from the owning ingress route.

## Acceptance criteria

- [ ] Service Ingress Routes accept a route-local Directory Entry with `enabled`, `label`, and `group`.
- [ ] Host Ingress Routes accept a route-local Directory Entry with `enabled`, `label`, and `group`.
- [ ] NAS Ingress Routes accept a route-local Directory Entry with `enabled`, `label`, and `group`.
- [ ] Inventory schema validation rejects Directory Entries that try to declare destination URLs or other unsupported first-pass presentation fields.
- [ ] Inventory validation rejects enabled Directory Entries on routes that are not enabled or not otherwise routable.
- [ ] Fast tests cover valid and invalid Directory Entry declarations across Service, Host, and NAS route kinds.

## Blocked by

None - can start immediately
