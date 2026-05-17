Status: ready-for-agent

# Document the Rite naming boundary

## What to build

Capture the resolved naming decision: Rite is the project and eventual CLI identity, while Operator Workflow remains the canonical domain term for executable infrastructure ceremonies. This slice should update domain documentation only, without renaming code, generated artifacts, package names, service identities, or compatibility-sensitive literals.

## Acceptance criteria

- [ ] The glossary names Rite as the project identity.
- [ ] The glossary preserves Operator Workflow as the canonical domain term.
- [ ] Documentation explains that `rite` is the intended operator surface name without implying that existing commands or internals have already been renamed.
- [ ] No generated artifact names, module names, package names, service identities, or live infrastructure literals are renamed in this slice.

## Blocked by

None - can start immediately
