# Run live rollout and Jellyfin hardware-acceleration verification

Status: ready-for-human
Type: enhancement

## What to build

Carry out the operator-controlled live rollout for Jellyfin GPU acceleration and verify the original playback problem is resolved. The rollout should converge Host readiness and VM PCI Device Assignment, coordinate any required Host or VM reboot, expose the render node to the Jellyfin container, switch Jellyfin's application-native encoding configuration to hardware acceleration, and compare playback/transcode behavior against the known CPU-only baseline.

This slice is intentionally human-led because it touches live Proxmox state, requires reboot timing, and includes Jellyfin application configuration.

## Acceptance criteria

- [ ] Host-side checks show the iGPU is no longer owned by the Host display driver when full passthrough is active.
- [ ] Proxmox VM configuration shows the Media VM has the iGPU assigned.
- [ ] The Media VM exposes `/dev/dri/renderD128` or the appropriate render node after reboot.
- [ ] The Jellyfin container can see and open the render node with the configured UID/GID and render group access.
- [ ] Jellyfin application configuration is switched from no hardware acceleration to the chosen VAAPI or QSV path.
- [ ] Jellyfin logs or controlled ffmpeg testing show hardware acceleration is used where expected.
- [ ] The originally failing 4K workload is retested against the previous CPU-only baseline and the outcome is documented.
- [ ] Any remaining codec, HDR tonemapping, subtitle burn-in, or client-direct-play limitations are recorded for follow-up rather than hidden.

## Blocked by

- .scratch/jellyfin-gpu-passthrough/issues/01-converge-host-full-passthrough-readiness.md
- .scratch/jellyfin-gpu-passthrough/issues/02-render-vm-pci-device-assignment-through-opentofu.md
- .scratch/jellyfin-gpu-passthrough/issues/03-assign-neuromancer-igpu-to-media-vm.md
- .scratch/jellyfin-gpu-passthrough/issues/04-expose-render-node-access-to-jellyfin-container.md

