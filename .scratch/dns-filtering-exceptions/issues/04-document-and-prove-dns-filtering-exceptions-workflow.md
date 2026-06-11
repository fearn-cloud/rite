# Document and prove DNS Filtering Exceptions workflow

Status: ready-for-human

## What to build

Document the DNS Filtering Exceptions operator workflow and add lightweight proof coverage so future Operators know how to add, apply, remove, and verify client exceptions across both Pi-hole peers. The documentation should reflect ADR-0041 and the glossary boundary that Rite owns DNS filtering policy projection, not router/IPAM/firewall state.

## Acceptance criteria

- [ ] Operator documentation explains how to declare an exception, run print mode, apply live convergence, and remove the last exception.
- [ ] Documentation states that missing or empty DNS Filtering Exceptions inventory means zero declared exceptions and still converges the managed group.
- [ ] Documentation states that fixed IPv4 assignment is handled outside Rite and that Rite does not validate router VLAN membership or create DHCP reservations.
- [ ] Documentation describes the managed Pi-hole group boundary and warns that Rite does not own manual Pi-hole groups, domain allowlists, blocklists, or adlists.
- [ ] Documentation includes a lightweight verification path for both primary and secondary DNS peers.
- [ ] Tests keep the runbook and command surface wired to the implemented workflow.

## Blocked by

- .scratch/dns-filtering-exceptions/issues/03-apply-dns-filtering-exceptions-to-pihole-peers.md

## Comments

- Implemented via TDD. `runbooks/dns-architecture.md` now documents declaring, printing, applying, removing the final exception, managed group boundaries, out-of-scope router/DHCP/VLAN/firewall state, and lightweight verification across both DNS peers. Tests pin the runbook and command surface.
