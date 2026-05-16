Status: ready-for-agent

# Host Update reboot interruption and restoration

## What to build

Extend Host Update with the maintenance-window path for Host reboot. Before rebooting, the workflow should show ordinary VMs placed on the Host and resident Services impacted through those VMs, require explicit confirmation, gracefully shut down the ordinary VMs it will interrupt, and stop if any VM cannot shut down cleanly. After the Host returns, the workflow should verify Host reachability and start the same ordinary VMs it shut down.

Ordinary VMs and impacted Services should be resolved from Inventory through the Inventory Entity Graph-style query surface, treating them as impacted dependents rather than update targets.

## Acceptance criteria

- [ ] Host Update resolves ordinary VMs placed on the selected Host from Inventory.
- [ ] Host Update shows ordinary VMs and resident Services impacted through those VMs before reboot confirmation.
- [ ] Host reboot requires explicit maintenance-window confirmation.
- [ ] Ordinary VMs are gracefully shut down before Host reboot.
- [ ] The workflow stops before reboot if any VM cannot shut down cleanly.
- [ ] After reboot, Host reachability is verified and failures are reported at the Host Update boundary.
- [ ] The workflow starts the same VMs it shut down, not a freshly re-resolved or broadened set.
- [ ] Host Update does not update VMs, Templates, or Services beyond graceful interruption and restoration.
- [ ] Tests prove impact output, confirmation behavior, VM shutdown ordering, stop-on-failure, reachability verification, and restoration ordering.

## Blocked by

- `.scratch/scoped-update-workflows/issues/04-host-update-non-reboot-path.md`
