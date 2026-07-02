# Refresh Service Launch workflows for Directory Entries

Status: ready-for-agent

## What to build

Update Service Launch and Service Group Launch so higher-level Service workflows run Directory Regeneration when launched Services declare Directory Entries. Keep Service Deploy scoped to the named Service and run Directory Regeneration once at the end of a Service Group Launch when any launched Service has Directory Entries.

## Acceptance criteria

- [ ] Service Deploy remains scoped to deploying only the named Service and does not run Directory Regeneration.
- [ ] Service Launch runs Directory Regeneration after Service Deploy when the launched Service declares one or more Directory Entries.
- [ ] Service Launch does not run Directory Regeneration when the launched Service has no Directory Entries.
- [ ] Service Group Launch runs Directory Regeneration once after all Service Deploy phases when any launched group Service declares Directory Entries.
- [ ] Service Group Launch does not run Directory Regeneration when no launched group Service has Directory Entries.
- [ ] Workflow tests cover refresh and no-refresh cases for both launch workflows.

## Blocked by

- .scratch/service-directory/issues/05-add-directory-regeneration-workflow.md
