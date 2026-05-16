Status: ready-for-agent

# Template Update for one Host copy

## What to build

Build the default Template Update workflow for one explicitly selected Host copy of one declared Template. The workflow should rebuild the selected Template from declared Template Inventory, replace the selected Host's existing Template copy through an explicit update path, and run Template Verification afterward.

This should reuse or extend the Template build and Template Verification machinery, but Template Update must not silently skip when the Template already exists. Existing VMs cloned from the Template are not changed.

## Acceptance criteria

- [ ] Template Update requires explicit Host and Template selection.
- [ ] Template Update rejects undeclared Hosts, undeclared Templates, and Host/Template pairs where the Host does not declare the Template.
- [ ] The selected Host's Template copy is rebuilt from declared Template Inventory.
- [ ] Existing Template copies are replaced through an explicit update path instead of being skipped as already present.
- [ ] Template Verification runs after rebuild.
- [ ] Failure output reports whether verification artifacts were preserved according to existing Template Verification behavior.
- [ ] Existing VMs and Services are not interrupted or mutated by the default one-Host Template Update path.
- [ ] A script wrapper and `just` target expose the workflow with explicit Host and Template arguments.
- [ ] Plan-builder and command-wrapper tests prove replacement behavior, verification ordering, validation failures, diagnostics, and runner integration.

## Blocked by

None - can start immediately
