# New Template

Use this runbook when adding a Proxmox VM Template from a checksum-pinned Cloud Image.

## Declare the Template

Create `inventory/templates/<name>.yaml`.

Required fields:

- `name`: the Template name.
- `vmid`: the Proxmox Template VMID. Use the reserved `9000`-`9999` range.
- `source.url`: the upstream Cloud Image URL.
- `source.checksum.algorithm`: `sha512`.
- `source.checksum.value`: the expected SHA-512 digest.
- `customize.packages`: optional packages to install with `virt-customize`.
- `customize.run_commands`: optional commands to run with `virt-customize`.
- `hardware.cores` and `hardware.memory`: required Proxmox hardware defaults.

Builder defaults:

- Template disk storage defaults to `fast`.
- Cloud-init drive storage defaults to `local-lvm`.
- Template network bridge defaults to `vmbr0`.
- Network model defaults to `virtio`.
- SCSI controller defaults to `virtio-scsi-pci`.

## Assign the Template to a Host

Add the Template name to the Host yaml under `proxmox.templates`.

Example:

```yaml
proxmox:
  templates:
    - debian-12-base
```

## Build

Run:

```sh
just templates-build host=<name>
```

The command builds only the Templates listed on that Host. An undeclared Host name fails before any tool runs.

## Checksum and Cache Behavior

Every Cloud Image is verified with the declared SHA-512 checksum before use. A mismatch fails before `virt-customize` or any `qm` mutation runs.

Downloaded Cloud Images are stored in a checksum-addressed cache. A later run with the same checksum verifies the cached file and avoids another download. The builder copies the cached Cloud Image to a per-build working copy; `virt-customize` never runs against the cache.

When upstream publishes a new Cloud Image, update `source.checksum.value` in the Template yaml in the same change that accepts the new image.

## Idempotency and VMID Collisions

If the declared VMID already exists as a Template on the Host, the builder skips it. A second run is a no-op.

If the declared VMID exists but is not a Template, the builder fails clearly. It does not delete, overwrite, or convert the existing VM.
