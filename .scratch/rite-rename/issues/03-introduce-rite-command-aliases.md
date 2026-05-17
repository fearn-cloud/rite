Status: ready-for-agent

# Introduce Rite command aliases

## What to build

Introduce a Rite-branded operator command surface while preserving existing operator commands and scripts. The new surface should delegate to the current working implementation so operators can begin using `rite` terminology without forcing an internal rename or breaking established workflows.

## Acceptance criteria

- [ ] Operators can invoke at least one representative Host, VM, Service, and validation workflow through a Rite-branded command surface.
- [ ] Existing Just targets and scripts continue to work unchanged.
- [ ] Help/list output makes the Rite-branded entrypoints discoverable.
- [ ] Tests or smoke checks prove the new aliases delegate to the same behavior as the existing entrypoints.
- [ ] Documentation makes clear that this is an alias/entrypoint pass, not an internal package or generated artifact rename.

## Blocked by

- .scratch/rite-rename/issues/01-document-rite-naming-boundary.md
