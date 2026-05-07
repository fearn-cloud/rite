# Share-backed Service volumes

Status: done

## What to build

Add Service volume declarations that consume Dataset access through a VM-local Mount Name on the Service's Backend VM. Share-backed Volumes use `mount`, `source`, `container`, and optional `access`; `source: /` binds the Mount root, while other sources are safe relative subpaths. A Service may narrow a Mount's access but never widen it.

## Acceptance criteria

- [x] Service schema accepts Share-backed Volume declarations separately from ordinary host-path bind mounts.
- [x] Cross-file validation resolves each Share-backed Volume `mount` against the Service Backend VM's Mount Names.
- [x] Validation rejects Share-backed Volumes that reference missing Mounts or attempt to widen Mount access.
- [x] Validation rejects unsafe sources such as absolute host paths other than `source: /` and any `..` traversal.
- [x] Quadlet rendering adds ordering on the corresponding systemd `.mount` unit for Share-backed Volumes.
- [x] Service deployment validates declared Share-backed Volume subpaths before starting containers.

## Blocked by

- `.scratch/nas-datasets-shares/issues/02-vm-mounts-reference-datasets.md`
