Status: ready-for-agent

# Update workflow runbooks and glossary alignment

## What to build

Add operator runbook documentation for Host Update, Template Update, VM Update, and Service Update. The documentation should help future-self run routine maintenance safely while preserving the boundaries captured by the scoped Update workflows.

The runbooks should use canonical domain language: Update and Upgrade remain distinct, Host Configure and VM Configure replace the retired generic Configure term, and package-manager specifics stay below the domain model.

## Acceptance criteria

- [ ] Host Update runbook documentation explains scope, confirmation gates, impacted dependents, reboot behavior, restoration behavior, and what remains out of scope.
- [ ] VM Update runbook documentation explains scope, confirmation gates, impacted Services, reboot behavior, restoration behavior, and what remains out of scope.
- [ ] Template Update runbook documentation explains one-Host scope, explicit all-Hosts mode, lineage reporting, Template Verification, and that existing VMs are not changed.
- [ ] Service Update runbook documentation explains Service Deploy composition, declared runtime references, named-Service-only restart behavior, and active-state success.
- [ ] Documentation distinguishes Update from Upgrade and avoids implying release transitions, package removals, database migrations, or application breaking migrations are part of routine Update.
- [ ] Documentation uses Host Configure and VM Configure rather than the retired generic Configure term.
- [ ] Documentation tests, or the nearest existing runbook tests, keep the new runbook language aligned with the glossary and ADR.

## Blocked by

- `.scratch/scoped-update-workflows/issues/01-service-update-workflow.md`
- `.scratch/scoped-update-workflows/issues/02-vm-update-non-reboot-path.md`
- `.scratch/scoped-update-workflows/issues/04-host-update-non-reboot-path.md`
- `.scratch/scoped-update-workflows/issues/06-template-update-one-host-copy.md`
