# Declare fleet-level DNS Filtering Exceptions

Status: ready-for-agent

## What to build

Add a fleet-level Inventory contract for DNS Filtering Exceptions. The completed slice should let the Operator declare fixed-IPv4 clients that keep fortress DNS resolution while bypassing Pi-hole blocking, without making Rite responsible for router DHCP reservations, VLAN membership, or firewall policy.

## Acceptance criteria

- [ ] Inventory loading treats missing DNS Filtering Exceptions inventory as an empty declaration.
- [ ] The declaration supports multiple entries with required `name` and `ipv4_address` fields and an optional `reason` field.
- [ ] Validation rejects invalid IPv4 addresses, duplicate names, and duplicate IPv4 addresses.
- [ ] Validation does not check router VLAN membership, create DHCP reservations, or infer firewall access.
- [ ] Fast tests cover missing-file, empty-list, valid declaration, invalid IPv4, duplicate name, and duplicate IPv4 cases.

## Blocked by

None - can start immediately
