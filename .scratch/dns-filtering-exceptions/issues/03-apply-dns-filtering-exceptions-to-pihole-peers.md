# Apply DNS Filtering Exceptions to Pi-hole peers

Status: ready-for-human

## What to build

Implement the operator workflow that reconciles DNS Filtering Exceptions into live Pi-hole peers. The workflow should run without a confirmation gate, apply only the fortress-managed Pi-hole group and its declared client IPv4 assignments, and leave all other Pi-hole groups, domain lists, adlists, router state, VLAN membership, and firewall policy untouched.

## Acceptance criteria

- [ ] `scripts/dns-filtering-exceptions-apply` validates Inventory and applies the planned exceptions to every targeted Pi-hole-backed DNS Service.
- [ ] `just dns-filtering-exceptions-apply` exposes the workflow.
- [ ] The workflow uses `vm-shell` against each DNS VM rather than depending on ingress availability.
- [ ] The workflow always ensures the fortress-managed Pi-hole group exists, even when there are zero declared exception clients.
- [ ] The workflow is authoritative only for clients assigned to the fortress-managed group, removing undeclared clients from that group while leaving other Pi-hole state alone.
- [ ] The workflow avoids full Pi-hole systemd/container restarts unless no supported Pi-hole API or CLI path can refresh the changed group assignment.
- [ ] The workflow exits nonzero and reports the failed peer if any target fails, without rolling back peers already converged.
- [ ] Rerunning the workflow after a partial failure is idempotent and converges the remaining peer.
- [ ] Fast tests cover command exposure, no confirmation gate, peer ordering, empty-state convergence, failure reporting, and no-rollback behavior.

## Blocked by

- .scratch/dns-filtering-exceptions/issues/02-plan-dns-filtering-exceptions-across-pihole-dns-services.md

## Comments

- Implemented via TDD. `scripts/dns-filtering-exceptions-apply` validates Inventory, uses `vm-shell` for each Pi-hole-backed DNS VM, ensures the managed group exists, authoritatively reconciles only that group's client assignments, refreshes with Pi-hole CLI instead of full service restart, reports failed peers, and leaves successful peers converged.
