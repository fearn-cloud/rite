# VM Mounts reference Datasets

Status: needs-triage

## What to build

Replace the old `nfs_mounts[].export` contract with VM `mounts[]` declarations that reference Datasets by name. Each Mount uses flat fields: `name`, `dataset`, `protocol`, `mount_point`, and `access`. Mount Names are VM-local, `protocol` is required, and `access` is `read_only | read_write`.

## Acceptance criteria

- [ ] `inventory/vms/_schema.json` accepts `mounts[]` with required `name`, `dataset`, `protocol`, `mount_point`, and `access`, and no longer requires or documents `nfs_mounts[].export`.
- [ ] Cross-file validation rejects Mounts referencing missing Datasets.
- [ ] Cross-file validation rejects duplicate Mount Names within a VM.
- [ ] Cross-file validation rejects Mount-bearing VMs without an unambiguous static IP address.
- [ ] The VM NFS mount Ansible role renders systemd `.mount` units from `mounts[]` where `protocol: nfs`.
- [ ] `access` is authoritative: `read_only` renders read-only behavior, and protocol options that contradict `access` are rejected.

## Blocked by

- `.scratch/nas-datasets-shares/issues/01-dataset-inventory-and-validation.md`
