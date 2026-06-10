# Expose render-node access to Jellyfin container

Status: done
Type: enhancement

## What to build

Expose the Media VM's render node to the Jellyfin Service container using the existing Quadlet Fragment mechanism. The fragment should grant both `/dev/dri` device access and supplemental render group access while preserving the existing Jellyfin runtime UID/GID.

This slice keeps Container Device Access as a native Quadlet Fragment concern rather than introducing first-class Service Inventory device fields.

## Acceptance criteria

- [ ] The Jellyfin container fragment declares `/dev/dri` device access.
- [ ] The Jellyfin container fragment grants supplemental `render` group access.
- [ ] The Jellyfin container continues to run as the declared media UID/GID.
- [ ] Quadlet rendering accepts and merges the Jellyfin fragment without overriding Rite-owned generated keys.
- [ ] Focused tests or golden output prove `Device=/dev/dri` and `GroupAdd=render` survive fragment rendering.
- [ ] No first-class Service Inventory device schema is introduced in this slice.

## Blocked by

- .scratch/jellyfin-gpu-passthrough/issues/03-assign-neuromancer-igpu-to-media-vm.md
