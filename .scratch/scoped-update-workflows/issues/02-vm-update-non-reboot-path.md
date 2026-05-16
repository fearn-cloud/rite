Status: ready-for-agent

# VM Update non-reboot path

## What to build

Build the first complete VM Update path for one durable VM without reboot interruption handling. The workflow should run VM Configure first, then perform routine in-place VM software advancement within the VM's current compatibility band. It should keep VM Update independent from Template Update and avoid package removals or release transitions by default.

The operator-facing command surface should be explicit, inspectable, and consistent with existing workflow ceremonies. Use Operator Workflow Plans for phase ordering, stop-on-failure behavior, streaming execution, and operator-visible diagnostics.

## Acceptance criteria

- [ ] VM Update rejects undeclared VMs before mutation.
- [ ] The VM Update plan runs VM Configure before software advancement.
- [ ] VM Update remains independent from Template Update and does not rebuild or mutate clone sources.
- [ ] Routine package advancement avoids removals and release transitions by default.
- [ ] A script wrapper and `just` target expose the workflow with an explicit VM argument.
- [ ] Failures name the failed phase clearly.
- [ ] Plan-builder and command-wrapper tests prove command ordering, validation failures, diagnostics, and runner integration.

## Blocked by

None - can start immediately
