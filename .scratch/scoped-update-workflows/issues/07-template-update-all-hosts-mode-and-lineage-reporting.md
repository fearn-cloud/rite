Status: ready-for-agent

# Template Update all-Hosts mode and lineage reporting

## What to build

Extend Template Update with an explicit all-Hosts selection that updates every Host copy declaring the selected Template. Also add lineage reporting that lists existing VMs that declare the Template while making clear those durable VMs are not changed.

All-Hosts behavior must be intentional and visible at the command surface. There should be no implicit fleet-wide Template Update behavior.

## Acceptance criteria

- [ ] Template Update supports an explicit all-Hosts selection for every Host that declares the selected Template.
- [ ] Template Update does not update every Host implicitly from the default one-Host command path.
- [ ] The workflow validates that at least one Host declares the selected Template before all-Hosts work begins.
- [ ] Existing VMs that declare the Template are listed as lineage context.
- [ ] Lineage output makes clear existing durable VMs are not changed by Template Update.
- [ ] All-Hosts mode runs the same rebuild-and-verify behavior for each selected Host copy.
- [ ] Tests prove all-Hosts selection, no implicit fleet-wide behavior, lineage output, and non-mutation of existing VMs and Services.

## Blocked by

- `.scratch/scoped-update-workflows/issues/06-template-update-one-host-copy.md`
