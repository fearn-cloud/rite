Status: ready-for-agent

# Declare and load Backup Substrate

## Parent

.scratch/backup-substrate-pbs-storage-registration/PRD.md

## What to build

Introduce the singular Backup Substrate Inventory contract and make it loadable as a first-class fleet-level declaration. Static validation should require a declared Backup Substrate whenever at least one production VM is a Backup Target, while allowing Inventory with no Backup Targets to omit it. Include fixture Inventory that demonstrates a complete Backup Substrate without adding placeholder substrate data to real Inventory.

## Acceptance criteria

- [ ] Inventory loading exposes whether the Backup Substrate declaration exists and, when present, exposes the parsed declaration through the Inventory model or an equivalent domain query.
- [ ] Schema or schema-equivalent validation accepts one singular Backup Substrate and rejects list/multiple-substrate shapes.
- [ ] Static validation fails when any production VM is a Backup Target and no Backup Substrate is declared.
- [ ] Static validation allows no Backup Substrate when no production VM is a Backup Target.
- [ ] Tests prove loaded Backup Substrate facts and the required/optional validation behavior using fixtures, without adding real Backup Substrate Inventory.

## Blocked by

None - can start immediately
