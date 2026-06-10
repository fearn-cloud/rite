# Render VM PCI Device Assignment through OpenTofu

Status: done
Type: enhancement

## What to build

Teach the VM provisioning path to carry declared VM PCI Device Assignments through to the Proxmox VM resource. The VM Inventory schema should accept the supported first-pass PCI assignment fields, and the generated OpenTofu configuration should render those declarations as Proxmox host PCI assignments.

This slice should prove the Inventory-to-OpenTofu path without relying on live Proxmox changes.

## Acceptance criteria

- [ ] VM Inventory accepts a PCI device assignment with host address, primary GPU flag, PCIe flag, and rombar flag.
- [ ] VM Inventory rejects malformed PCI device assignment shapes.
- [ ] OpenTofu VM rendering includes host PCI assignments derived from declared VM PCI Device Assignments.
- [ ] VMs without PCI device assignments continue to render without host PCI blocks.
- [ ] Focused tests prove the generated OpenTofu shape for both assigned and unassigned VMs.
- [ ] Existing selected-VM provisioning behavior remains unchanged for unrelated VMs.

## Blocked by

None - can start immediately
