Status: ready-for-agent

# Rename Python packages and internal modules

## What to build

Rename internal Python packages and module references from fortress-oriented names to Rite-oriented names after the operator command surface exists. Preserve working imports during the transition if needed through compatibility shims, and keep the change focused on repository-internal code rather than live infrastructure names.

## Acceptance criteria

- [ ] Internal package and module names use Rite-oriented naming where the compatibility policy permits.
- [ ] Existing tests, scripts, and command entrypoints import the renamed modules successfully.
- [ ] Compatibility shims are added where needed so existing operator entrypoints continue to work during the transition.
- [ ] The full relevant unit test suite passes.
- [ ] No generated artifact prefixes or live infrastructure literals are renamed unless covered by the compatibility policy.

## Blocked by

- .scratch/rite-rename/issues/03-introduce-rite-command-aliases.md
- .scratch/rite-rename/issues/04-decide-generated-artifact-compatibility-policy.md
