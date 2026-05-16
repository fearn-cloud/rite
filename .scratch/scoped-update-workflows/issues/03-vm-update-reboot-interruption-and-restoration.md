Status: ready-for-agent

# VM Update reboot interruption and restoration

## What to build

Extend VM Update with the maintenance-window path for VM reboot. Before rebooting, the workflow should show resident fortress-managed Services, require explicit confirmation, stop those Services normally, and stop if any Service cannot reach stopped state. After the VM returns, the workflow should verify VM reachability and restore the same resident Services it stopped.

Resident Services should be resolved from Inventory by Backend VM through the Inventory Entity Graph-style query surface, treating those Services as impacted dependents rather than update targets.

## Acceptance criteria

- [ ] VM Update resolves resident fortress-managed Services for the selected VM from Inventory.
- [ ] The workflow shows resident Services before any VM reboot confirmation.
- [ ] VM reboot requires explicit maintenance-window confirmation.
- [ ] Resident fortress-managed Services are stopped normally before VM reboot.
- [ ] The workflow stops before reboot if any Service cannot reach stopped state.
- [ ] After reboot, VM reachability is verified and failures are reported at the VM Update boundary.
- [ ] The workflow restores the same Services it stopped, not a freshly re-resolved or broadened set.
- [ ] Tests prove Service impact output, confirmation behavior, stop ordering, stop-on-failure, reachability verification, and restoration ordering.

## Blocked by

- `.scratch/scoped-update-workflows/issues/02-vm-update-non-reboot-path.md`
