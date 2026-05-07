# Dataset inventory and validation

Status: needs-triage

## What to build

Add first-class Dataset inventory so fortress can represent adopted NAS data without owning its destructive lifecycle. A Dataset lives under `inventory/datasets/<dataset>.yaml`, has a globally unique name, declares `nas`, `path`, `lifecycle: adopted | ephemeral`, and requires `owner.uid`/`owner.gid` for adopted Datasets. Ordinary fleet inventory rejects `ephemeral`; acceptance-test fixture inventory may use it.

## Acceptance criteria

- [ ] `inventory/datasets/_schema.json` validates Dataset files with required `name`, `nas`, `path`, `lifecycle`, and adopted owner UID/GID.
- [ ] Inventory loading includes Datasets alongside Hosts, VMs, Services, and Templates.
- [ ] Cross-file validation enforces globally unique Dataset names and rejects `lifecycle: ephemeral` in ordinary fleet inventory.
- [ ] Existing tests and fixtures cover valid adopted Datasets, invalid missing owner, invalid unknown NAS endpoint, and invalid ordinary ephemeral Dataset.
- [ ] Documentation examples in `docs/architecture.md` and `runbooks/nas-truenas.md` remain consistent with the implemented schema.

## Blocked by

None - can start immediately
