# Domain Docs

How engineering skills should consume this repo’s domain documentation when exploring the codebase.

## Before exploring, read these

- `CONTEXT.md` at the repo root.
- `docs/adr/` — read ADRs that touch the area being worked on.

If either is absent, proceed silently. The producer skill (`/grill-with-docs`) creates domain docs only when terms or decisions are resolved.

## File structure

This is a single-context repo:

```text
/
├── CONTEXT.md
├── docs/
│   └── adr/
└── src/
```

## Use the glossary’s vocabulary

When naming a domain concept in an issue, refactor proposal, hypothesis, or test name, use the term defined in `CONTEXT.md`. If the concept is absent, reconsider whether it is already named differently or note the gap for `/grill-with-docs`.

## Flag ADR conflicts

If a proposal contradicts an existing ADR, surface that explicitly rather than silently overriding it.
