Status: ready-for-agent

# Service Update workflow

## What to build

Build the Service Update operator workflow for one declared Service. The workflow should compose Service Deploy first, advance only to runtime references already declared in Inventory, restart every fortress-owned unit for the named Service, and succeed only when those named-Service units reach active state.

The operator-facing command surface should match the existing ceremony pattern with an explicit script wrapper and `just` target. The workflow should use Operator Workflow Plans so confirmation, phase ordering, stop-on-failure behavior, streaming execution, and diagnostics follow the existing runner conventions.

## Acceptance criteria

- [ ] The Service Update plan starts with Service Deploy for the named Service.
- [ ] Service Update updates only the named Service and does not restart Service Group peers implicitly.
- [ ] Service Update does not choose newer application versions or image tags outside declared Inventory runtime references.
- [ ] All fortress-owned units for the named Service are restarted.
- [ ] Success requires all fortress-owned units for the named Service to reach active state.
- [ ] Application-level health checks remain out of scope unless explicitly modeled elsewhere.
- [ ] A script wrapper and `just` target expose the workflow with an explicit Service argument.
- [ ] Plan-builder and command-wrapper tests prove command ordering, validation, diagnostics, and runner integration.

## Blocked by

None - can start immediately
