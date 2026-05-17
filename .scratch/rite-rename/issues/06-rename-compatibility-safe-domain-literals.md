Status: ready-for-agent

# Rename compatibility-safe domain literals

## What to build

Rename only the domain literals that the generated artifact compatibility policy explicitly marks as safe to migrate. This may include generated prefixes, service-owned filenames, DNS generated-file names, PVE identities, SOPS keys, or other live-facing names, but only when the policy defines the migration and verification path.

## Acceptance criteria

- [ ] Every renamed literal is explicitly allowed by the compatibility policy.
- [ ] Tests cover the new literal names and any compatibility behavior for old names.
- [ ] Operator documentation or runbooks describe any live migration steps required.
- [ ] Validation catches mixed old/new states when those states would be unsafe.
- [ ] A repository search shows no unintended remaining references to migrated literals.

## Blocked by

- .scratch/rite-rename/issues/04-decide-generated-artifact-compatibility-policy.md
