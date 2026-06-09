# Assign neuromancer iGPU to the Media VM

Status: ready-for-agent
Type: enhancement

## What to build

Declare the Intel iGPU on the neuromancer Host as a VM PCI Device Assignment for the Media VM. The declaration should make the intended passthrough ownership visible in Inventory and produce a selected-VM OpenTofu plan that would attach the GPU to the Media VM.

This slice is repo-side intent only; live application, Host reboot, and playback verification belong to the rollout issue.

## Acceptance criteria

- [ ] The Media VM declares the neuromancer Intel iGPU as a VM PCI Device Assignment.
- [ ] The declaration uses the resolved full-passthrough settings for a non-primary PCIe GPU assignment.
- [ ] Inventory schema validation passes for the updated Media VM declaration.
- [ ] The selected-VM OpenTofu plan path can be used to inspect the intended host PCI assignment for the Media VM.
- [ ] No unrelated VM or Service Inventory is changed.

## Blocked by

- .scratch/jellyfin-gpu-passthrough/issues/01-converge-host-full-passthrough-readiness.md
- .scratch/jellyfin-gpu-passthrough/issues/02-render-vm-pci-device-assignment-through-opentofu.md

