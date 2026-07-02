# Expose Directory Entries from Inventory

Status: ready-for-agent

## What to build

Expose all Directory Entries through the Inventory query layer so Directory Regeneration and workflow planning can consume route-derived directory facts without traversing raw Service, Host, or NAS YAML shapes. The query should preserve the owning route kind and identity, the display label and group, and the route-derived HTTPS destination.

## Acceptance criteria

- [ ] Inventory exposes Directory Entry facts for opted-in Service Ingress Routes.
- [ ] Inventory exposes Directory Entry facts for opted-in Host Ingress Routes.
- [ ] Inventory exposes Directory Entry facts for opted-in NAS Ingress Routes.
- [ ] Directory Entry destinations are derived from the owning route hostnames, not from Directory Entry fields.
- [ ] Directory Entry facts are ordered deterministically by group and label.
- [ ] Fast tests cover mixed Service, Host, and NAS Directory Entry facts and disabled entries.

## Blocked by

- .scratch/service-directory/issues/01-add-directory-entry-inventory-contract.md
