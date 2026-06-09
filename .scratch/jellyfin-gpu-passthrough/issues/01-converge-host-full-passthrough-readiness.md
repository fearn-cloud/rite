# Converge Host full-passthrough readiness

Status: ready-for-agent
Type: enhancement

## What to build

Make Host Configure converge the minimal Host-side readiness needed for full GPU passthrough. A Host declaring full GPU passthrough should end up with the required IOMMU and vfio boot/module configuration staged, any required boot/initramfs refresh performed, and an operator-facing reboot-required report emitted. Host Configure must not reboot the Host automatically.

This slice closes the gap between documented Rite behavior and the current partial Host GPU passthrough configuration.

## Acceptance criteria

- [ ] Host Configure stages Intel IOMMU kernel arguments for full Intel GPU passthrough Hosts.
- [ ] Host Configure stages the vfio-related module configuration required for full passthrough readiness.
- [ ] Host Configure refreshes the relevant boot/initramfs artifacts when passthrough configuration changes.
- [ ] Host Configure appends a clear reboot-required reason when changes need an operator-controlled Host reboot.
- [ ] Host Configure never reboots the Host automatically.
- [ ] SR-IOV passthrough behavior remains compatible with the existing Host declarations.
- [ ] Focused tests or playbook assertions cover the full-passthrough readiness path and reboot-required reporting.

## Blocked by

None - can start immediately

