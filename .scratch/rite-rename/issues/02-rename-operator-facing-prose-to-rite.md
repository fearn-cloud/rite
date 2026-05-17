Status: ready-for-agent

# Rename operator-facing prose to Rite

## What to build

Update operator-facing prose so the project is described as Rite instead of fortress where the text is naming the tool, project, or operator experience. Leave compatibility-sensitive names alone, including generated prefixes, package names, module names, command names, SOPS keys, PVE identities, DNS file names, and historical ADR context where changing the wording would blur the original decision.

## Acceptance criteria

- [ ] README, architecture docs, runbooks, and current planning docs use Rite for the project/tool identity.
- [ ] Operator-facing prose uses Operator Workflow consistently for the domain concept.
- [ ] Historical ADRs are either left unchanged or only updated where the new wording does not distort the recorded decision.
- [ ] A repository search for lowercase `fortress` is reviewed, and remaining matches are documented as intentional compatibility, historical, or implementation references.
- [ ] No code, generated artifact names, package/module names, or live infrastructure literals are renamed in this slice.

## Blocked by

- .scratch/rite-rename/issues/01-document-rite-naming-boundary.md
