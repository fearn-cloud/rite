Status: ready-for-agent

# Host Update non-reboot path

## What to build

Build the first complete Host Update path for one Host without reboot interruption handling. The workflow should run Host Configure first, then perform routine in-place Host software advancement within the Host's current compatibility band. Host Configure may report reboot-required state, but convergence must remain separate from maintenance-window reboot decisions.

Host Update should keep its target scope narrow: it should not rebuild Templates, update VMs, or update Services implicitly. Use Operator Workflow Plans for phase ordering, stop-on-failure behavior, streaming execution, and diagnostics.

## Acceptance criteria

- [ ] Host Update rejects undeclared Hosts before mutation.
- [ ] The Host Update plan runs Host Configure before software advancement.
- [ ] Host Configure can report reboot-required state without rebooting as part of Host Configure.
- [ ] Routine package advancement avoids removals and release transitions by default.
- [ ] Host Update does not rebuild Templates or update VMs or Services implicitly.
- [ ] A script wrapper and `just` target expose the workflow with an explicit Host argument.
- [ ] Failures name the failed phase clearly.
- [ ] Plan-builder and command-wrapper tests prove command ordering, validation failures, diagnostics, and runner integration.

## Blocked by

None - can start immediately
