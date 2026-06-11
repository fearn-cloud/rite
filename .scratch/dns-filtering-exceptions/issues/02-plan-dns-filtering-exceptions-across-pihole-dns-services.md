# Plan DNS Filtering Exceptions across Pi-hole DNS Services

Status: ready-for-human

## What to build

Add a non-mutating plan for applying DNS Filtering Exceptions across every Pi-hole-backed DNS Service. The completed slice should let the Operator print the fixed fortress-managed Pi-hole group name, desired exception clients, and target DNS peers without changing live Pi-hole state.

## Acceptance criteria

- [ ] The plan consumes the fleet-level DNS Filtering Exceptions declaration.
- [ ] The plan discovers every Pi-hole-backed DNS Service that should receive the managed exception group.
- [ ] The plan uses one fixed fortress-managed Pi-hole group name and does not make the group name configurable in Inventory.
- [ ] The plan reports zero declared clients when the declaration is missing or empty.
- [ ] The plan exposes a print-only script mode that does not call `vm-shell` or mutate live Pi-hole state.
- [ ] Fast tests cover multiple DNS peers, missing or empty exception declarations, and stable printed plan output.

## Blocked by

- .scratch/dns-filtering-exceptions/issues/01-declare-fleet-level-dns-filtering-exceptions.md

## Comments

- Implemented via TDD. Added a pure DNS Filtering Exceptions plan with fixed fortress-managed group name, deterministic Pi-hole-backed DNS Service targets, zero-client handling for missing/empty declarations, and stable `scripts/dns-filtering-exceptions-apply --print` output that does not call `vm-shell`.
