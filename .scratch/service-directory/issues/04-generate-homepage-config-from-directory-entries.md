# Generate Homepage config from Directory Entries

Status: ready-for-agent

## What to build

Generate Homepage configuration for the Service Directory from current Directory Entries. The generated config should group entries by Directory Entry group, sort groups and labels deterministically, and use the owning ingress route hostname as the only source of each entry destination.

## Acceptance criteria

- [ ] A generator renders Homepage service groups from Directory Entry facts.
- [ ] Generated groups are ordered deterministically by group label.
- [ ] Generated entries inside each group are ordered deterministically by entry label.
- [ ] Generated destinations are derived from route hostnames and use the route-facing HTTPS URL.
- [ ] Generated output does not preserve or merge operator edits inside the generated surface.
- [ ] Fast tests cover empty, single-group, multi-group, and mixed route-kind generation.

## Blocked by

- .scratch/service-directory/issues/02-expose-directory-entries-from-inventory.md
- .scratch/service-directory/issues/03-declare-service-directory-homepage-service.md
