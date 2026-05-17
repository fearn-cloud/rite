Status: ready-for-agent

# Retire fortress compatibility shims

## What to build

Remove temporary fortress compatibility shims and stale references once the Rite entrypoints, internal module names, and any approved literal migrations have been proven stable. This is the final cleanup pass, not the place to make new naming decisions.

## Acceptance criteria

- [ ] Temporary compatibility shims introduced for the rename are removed or explicitly documented as permanent.
- [ ] Deprecated command aliases are removed only if the operator documentation says they are no longer supported.
- [ ] A repository search for `fortress` is reviewed, and every remaining match is either historical, compatibility-intentional, or removed.
- [ ] The relevant test suite and command smoke checks pass after shim removal.
- [ ] No new naming policy decisions are introduced in this cleanup slice.

## Blocked by

- .scratch/rite-rename/issues/03-introduce-rite-command-aliases.md
- .scratch/rite-rename/issues/05-rename-python-packages-and-internal-modules.md
- .scratch/rite-rename/issues/06-rename-compatibility-safe-domain-literals.md
