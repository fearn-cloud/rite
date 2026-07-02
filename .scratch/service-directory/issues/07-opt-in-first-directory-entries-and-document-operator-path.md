# Opt in first Directory Entries and document the operator path

Status: ready-for-human

## What to build

Choose and declare the first useful set of Directory Entries, then document the operator path for deploying and regenerating the Service Directory. The first entries should be intentionally selected rather than inferred from every route, with labels and groups that reflect operator navigation rather than Service Group launch semantics.

## Acceptance criteria

- [x] Initial Directory Entries are declared for a useful, intentionally selected set of Service, Host, and NAS routes.
- [x] Directory Entry groups use operator navigation language and do not rely on Service Group names unless that label is also the desired navigation group.
- [x] The runbook explains the split between `service-deploy service-directory` and `directory-regenerate`.
- [x] The runbook explains when Service Launch and Service Group Launch refresh the Service Directory automatically.
- [x] The runbook explains that Host and NAS Directory Entry changes require explicit Directory Regeneration.
- [ ] A human operator has reviewed the initial labels and groups.

## Blocked by

- .scratch/service-directory/issues/05-add-directory-regeneration-workflow.md
