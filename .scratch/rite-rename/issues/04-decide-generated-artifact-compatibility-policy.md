Status: ready-for-human

# Decide generated artifact compatibility policy

## What to build

Make an explicit human decision about whether compatibility-sensitive `fortress` names should remain stable or migrate to Rite names. This includes generated artifact prefixes, systemd and Podman identities, DNS generated-file names, PVE identities, SOPS keys, service-owned filenames, and any other live infrastructure literal that may already exist outside the repository.

## Acceptance criteria

- [ ] The decision states which `fortress` literals remain permanent compatibility names.
- [ ] The decision states which `fortress` literals should migrate to Rite names.
- [ ] For every migrating category, the decision describes the expected operator impact and rollback/recovery posture.
- [ ] The decision is recorded in documentation appropriate for a compatibility policy, with an ADR offered only if the trade-off meets the ADR bar.
- [ ] No compatibility-sensitive literal is renamed before this policy exists.

## Blocked by

- .scratch/rite-rename/issues/02-rename-operator-facing-prose-to-rite.md
