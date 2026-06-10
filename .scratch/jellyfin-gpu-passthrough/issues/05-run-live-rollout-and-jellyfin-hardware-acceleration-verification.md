# Run live rollout and Jellyfin hardware-acceleration verification

Status: ready-for-human
Type: enhancement

## What to build

Carry out the operator-controlled live rollout for Jellyfin GPU acceleration and verify the original playback problem is resolved. The rollout should converge Host readiness and VM PCI Device Assignment, coordinate any required Host or VM reboot, expose the render node to the Jellyfin container, switch Jellyfin's application-native encoding configuration to hardware acceleration, and compare playback/transcode behavior against the known CPU-only baseline.

This slice is intentionally human-led because it touches live Proxmox state, requires reboot timing, and includes Jellyfin application configuration.

## Acceptance criteria

- [x] Host-side checks show the iGPU is no longer owned by the Host display driver when full passthrough is active.
- [x] Proxmox VM configuration shows the Media VM has the iGPU assigned.
- [x] The Media VM exposes `/dev/dri/renderD128` or the appropriate render node after reboot.
- [x] The Jellyfin container can see and open the render node with the configured UID/GID and render group access.
- [x] Jellyfin application configuration is switched from no hardware acceleration to the chosen VAAPI or QSV path.
- [x] Jellyfin logs or controlled ffmpeg testing show hardware acceleration is used where expected.
- [x] The originally failing 4K workload is retested against the previous CPU-only baseline and the outcome is documented.
- [x] Any remaining codec, HDR tonemapping, subtitle burn-in, or client-direct-play limitations are recorded for follow-up rather than hidden.

## Live verification notes

- 2026-06-10: `neuromancer` iGPU `00:02.0` is bound to `vfio-pci`, and `media-vm` has `hostpci0: mapping=neuromancer-igpu,pcie=1,rombar=1,x-vga=0`.
- 2026-06-10: `media-vm` booted `6.12.90+deb13.1-amd64`, exposes `/dev/dri/renderD128`, and `lspci -nnk -s 01:00.0` shows `Kernel driver in use: i915`.
- 2026-06-10: Jellyfin Quadlet renders `AddDevice=/dev/dri` and deploy resolves the VM `render` group to numeric `GroupAdd=991`; the running container has `/dev/dri/renderD128` and supplemental group `991`.
- 2026-06-10: Controlled container-side ffmpeg test using `/usr/lib/jellyfin-ffmpeg/ffmpeg -init_hw_device vaapi=va:/dev/dri/renderD128 ... -c:v h264_vaapi` completed successfully.
- 2026-06-10: Jellyfin application encoding configuration was changed from `HardwareAccelerationType=none` to `vaapi` with `VaapiDevice=/dev/dri/renderD128`.
- 2026-06-10: Previous CPU-only baseline for the original failing 4K workload was the `The Lord of the Rings The Fellowship of the Ring (2001)` 4K HEVC Dolby Vision/HDR10 remux with PGS subtitle overlay. The June 9 CPU-only transcode logs used `libx264`, CPU tonemapping/overlay, and topped out around `0.50x` transcode speed, below real time.
- 2026-06-10: Retested the same 4K workload through a Jellyfin stream after VAAPI enablement. The new transcode log used `h264_vaapi` with `hwupload_vaapi`; observed speed rose above real time and stabilized around `1.25x-1.29x`. Operator playback verification reported the stream looked good.
- 2026-06-10: Remaining limitation recorded: this stress case still uses significant CPU for subtitle overlay/scaling around the hardware encode path. No playback failure was observed, but future HDR tonemapping or subtitle burn-in changes should be validated against this same workload rather than assuming all 4K variants behave like direct play.
- 2026-06-10: Follow-up ffmpeg benchmarking against the same `The Lord of the Rings The Fellowship of the Ring (2001)` remux reproduced the later slow Jellyfin stream at `0.84x` using the current 4K PGS subtitle burn-in path. Removing only PGS subtitle burn-in reached `0.97x`; all-GPU VAAPI HEVC decode, VAAPI scale, and VAAPI encode without subtitles reached `2.38x`; 1080p PGS burn-in reached `1.08x`; hardware decode plus CPU PGS overlay plus VAAPI encode reached `0.90x`. Lower VAAPI bitrate and CQP encoder settings stayed around `0.87x`, while VAAPI low-power H.264 encode failed to initialize. The limiting path is CPU-side PGS subtitle composition/scaling, not the VAAPI encoder.

## Blocked by

- .scratch/jellyfin-gpu-passthrough/issues/01-converge-host-full-passthrough-readiness.md
- .scratch/jellyfin-gpu-passthrough/issues/02-render-vm-pci-device-assignment-through-opentofu.md
- .scratch/jellyfin-gpu-passthrough/issues/03-assign-neuromancer-igpu-to-media-vm.md
- .scratch/jellyfin-gpu-passthrough/issues/04-expose-render-node-access-to-jellyfin-container.md
