Status: done

## Parent

docs/prds/initial-building-blocks.md

## What to build

NAS topology declares NAS Endpoints and Datasets separately; per-VM Mount declarations reference Datasets by name and declare protocol, mount point, and access policy. Mounts are implemented as systemd `.mount` units so Quadlets can declare `Requires=` for ordering through Share-backed Volumes. UID/GID convention is coordinated with Dataset ownership.

## Acceptance criteria

- [x] NAS Endpoint and Dataset declarations exist, with global NAS protocol defaults and UID/GID convention
- [x] VM yaml schema supports a `mounts:` block with `name`, `dataset`, `protocol`, `mount_point`, and `access`
- [x] Per-VM mounts rendered as systemd `.mount` units on the VM
- [x] UID/GID convention documented in `runbooks/nas-truenas.md` alongside required TrueNAS-side dataset ownership steps
- [x] Cross-file validator checks Mount Dataset references resolve, Mount Names are unique within a VM, Mount-bearing VMs have one static IP address, and Access Policy constraints are respected
- [x] `vm-up` workflow extended to write mount units when present
- [ ] Demo: a test VM with declared mount has a functional, systemd-managed NFS mount

## Blocked by

.scratch/initial-building-blocks/issues/05-tofu-yaml-to-resource-bridge-vm-lifecycle.md
