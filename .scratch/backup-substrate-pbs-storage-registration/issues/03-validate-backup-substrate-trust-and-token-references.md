Status: ready-for-agent

# Validate Backup Substrate trust and token references

## Parent

.scratch/backup-substrate-pbs-storage-registration/PRD.md

## What to build

Validate the Backup Substrate's PBS TLS trust declaration and per-Host PBS token references. Hosts with Backup Targets must have token references, Hosts without Backup Targets may have extra token references, and token references must point into the PBS Service sibling SOPS boundary. Static validation should inspect encrypted SOPS structure only and must not decrypt token values.

## Acceptance criteria

- [ ] Static validation requires declared PBS TLS trust material for the Backup Substrate.
- [ ] Static validation requires a per-Host PBS token reference for every Host that currently has at least one Backup Target.
- [ ] Static validation allows token references for Hosts that currently have no Backup Targets.
- [ ] Token references are validated as paths into the PBS Service sibling SOPS file, preserving PBS Configure ownership of PBS-side credentials.
- [ ] Tests prove encrypted SOPS key paths are checked structurally without requiring SOPS decryption or private key material.
- [ ] Backup Configure continues to consume identities only and does not create, rotate, or decrypt PBS credentials.

## Blocked by

- .scratch/backup-substrate-pbs-storage-registration/issues/01-declare-and-load-backup-substrate.md
