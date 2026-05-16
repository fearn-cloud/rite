Status: ready-for-agent

# Scoped Update Workflows PRD

## Problem Statement

The Operator needs routine maintenance workflows for Hosts, Templates, VMs, and Services without turning "update" into a broad, surprising command that mutates dependent entities implicitly. Today fortress has strong first-class ceremonies for Bootstrap, Host Configure, VM Lifecycle Convergence, Service Deploy, Service Launch, Template build, and Template Verification, but it does not yet have scoped Update workflows that own routine package/runtime advancement, maintenance-window confirmation, graceful interruption, and post-update restoration.

## Solution

Add four first-class operator workflows: Host Update, Template Update, VM Update, and Service Update. Each workflow keeps its target scope narrow, composes the existing convergence or deploy ceremony for that target, avoids package removals and release-transition behavior by default, and treats dependent entities as impacted dependents rather than implicit update targets.

Host Update runs Host Configure first, performs routine Host software advancement, and may reboot the selected Host only as an explicit maintenance-window decision after gracefully shutting down ordinary VMs placed on that Host. After the Host returns, it starts the same ordinary VMs it shut down.

Template Update rebuilds the selected Template from declared Template Inventory, replaces the selected Host's Template copy, and proves the result with Template Verification. It may target one Host copy or every declaring Host only when the Operator explicitly selects all Hosts. Existing VMs cloned from that Template are not changed.

VM Update runs VM Configure first, performs routine VM software advancement, and may reboot the selected VM only as an explicit maintenance-window decision after stopping resident fortress-managed Services normally. After the VM returns, it restores the same resident Services it stopped.

Service Update runs Service Deploy first, advances only to runtime references already declared in Inventory, restarts all fortress-owned units for the named Service, and succeeds when those units reach active state.

## User Stories

1. As the Operator, I want a Host Update workflow, so that I can apply routine Host software maintenance without accidentally updating VMs, Templates, or Services.
2. As the Operator, I want Host Update to run Host Configure first, so that declared Host state is current before maintenance actions begin.
3. As the Operator, I want Host Configure to report reboot-required state without rebooting, so that convergence remains separate from maintenance-window decisions.
4. As the Operator, I want Host Update to show ordinary VMs placed on the Host before rebooting, so that I understand the interruption blast radius.
5. As the Operator, I want Host Update to show resident Services impacted through those VMs, so that I know which applications will be interrupted.
6. As the Operator, I want Host Update to require explicit confirmation before rebooting a Host, so that Host interruption is deliberate.
7. As the Operator, I want Host Update to gracefully shut down ordinary VMs before rebooting a Host, so that VMs are not surprised by a Host shutdown.
8. As the Operator, I want Host Update to stop if a VM cannot shut down cleanly, so that I can decide whether to wait, inspect, or intervene manually.
9. As the Operator, I want Host Update to start the same VMs it shut down after the Host returns, so that the workflow restores the running set it interrupted.
10. As the Operator, I want Host Update to verify Host reachability after reboot, so that failures are reported at the maintenance workflow boundary.
11. As the Operator, I want Host Update to avoid package removals and release transitions by default, so that routine maintenance does not become an Upgrade.
12. As the Operator, I want Host Update to leave Template Update separate, so that Host package maintenance does not rebuild clone sources implicitly.
13. As the Operator, I want a Template Update workflow, so that future VM clones can start from a current reusable base.
14. As the Operator, I want Template Update to rebuild a Template from declared Inventory instead of mutating it in place, so that Template provenance remains reproducible.
15. As the Operator, I want Template Update to run Template Verification after rebuild, so that the clone source still satisfies the VM Lifecycle Contract.
16. As the Operator, I want Template Update to target one Host's Template copy by default, so that Template maintenance has explicit Host scope.
17. As the Operator, I want Template Update to support an explicit all-Hosts selection, so that I can intentionally update every declaring Host copy of a Template.
18. As the Operator, I want Template Update to list existing VMs that declare the Template without changing them, so that lineage is visible but durable VMs are not mutated.
19. As the Operator, I want Template Update to be non-disruptive to existing VMs and Services by default, so that clone-source maintenance does not interrupt running workloads.
20. As the Operator, I want Template Update failure to report whether verification artifacts were preserved, so that debugging follows existing Template Verification behavior.
21. As the Operator, I want a VM Update workflow, so that I can apply routine guest maintenance to one durable VM in place.
22. As the Operator, I want VM Update to run VM Configure first, so that declared VM state is current before package maintenance begins.
23. As the Operator, I want VM Update to remain independent from Template Update, so that urgent VM patching is not blocked by clone-source maintenance.
24. As the Operator, I want VM Update to show resident Services before rebooting, so that I understand the application interruption.
25. As the Operator, I want VM Update to require explicit confirmation before rebooting, so that VM interruption is deliberate.
26. As the Operator, I want VM Update to stop resident fortress-managed Services normally before reboot, so that Services receive a clean shutdown signal.
27. As the Operator, I want VM Update to stop if a Service cannot reach stopped state, so that I can inspect before forcing a reboot.
28. As the Operator, I want VM Update to restore the same Services it stopped after reboot, so that the VM returns to its pre-update service set.
29. As the Operator, I want VM Update to verify VM reachability after reboot, so that failures are reported clearly.
30. As the Operator, I want VM Update to avoid package removals and release transitions by default, so that routine VM maintenance does not become a VM Upgrade.
31. As the Operator, I want a Service Update workflow, so that I can apply routine runtime maintenance to one declared Service.
32. As the Operator, I want Service Update to run Service Deploy first, so that updated Service YAML is applied through the existing deployment path.
33. As the Operator, I want Service Update to advance only to runtime references already declared in Inventory, so that the workflow does not choose newer application versions for me.
34. As the Operator, I want Service Update to update only the named Service, so that Service Group peers are not restarted implicitly.
35. As the Operator, I want Service Update to restart all fortress-owned units for the named Service, so that the Service avoids subtle partial-update states.
36. As the Operator, I want Service Update success to mean all fortress-owned units reached active state, so that the first success contract is clear and testable.
37. As the Operator, I want application-level health checks deferred until explicitly modeled, so that generic Service Update does not pretend to understand each application.
38. As the Operator, I want Update and Upgrade to remain distinct, so that routine maintenance does not hide compatibility or migration work.
39. As the Operator, I want all Update workflows to use Operator Workflow Plans, so that phase ordering, confirmation gates, diagnostics, and stop-on-failure behavior match existing workflows.
40. As the Operator, I want clear failure diagnostics naming the failed phase, so that maintenance failures are easy to resume or debug.
41. As the Operator, I want `just` targets and script wrappers for each Update workflow, so that the command surface matches existing fortress ceremonies.
42. As future-self on a new workstation, I want runbook documentation for each Update workflow, so that I can safely run maintenance without rediscovering the boundaries.
43. As an implementing agent, I want focused plan-builder tests for each Update workflow, so that workflow composition can be proven without live infrastructure.
44. As an implementing agent, I want command-wrapper tests for each Update workflow, so that CLI validation and runner integration follow existing patterns.

## Implementation Decisions

- Build new workflow plan builders for Host Update, Template Update, VM Update, and Service Update, following the existing Operator Workflow Plan pattern used by VM Lifecycle Convergence, Service Launch, and Host Readiness.
- Keep execution mechanics in the existing Operator Workflow Runner. Update-specific modules should build inspectable plans and let the runner own confirmation gates, streaming phase execution, stop-on-failure, and diagnostics.
- Add script wrappers and `just` targets for each workflow. The operator-facing surface should use explicit entity arguments rather than a polymorphic update command.
- Host Update should resolve impacted ordinary VMs from Inventory by Host placement. It should treat hosted VMs and resident Services as impacted dependents, not update targets.
- Host Update should compose Host Configure before package maintenance. Host Configure may report reboot-required state but must not reboot.
- Host Update should snapshot the ordinary VMs it will shut down, gracefully stop them before Host reboot, and restart that same set after Host reachability returns.
- VM Update should resolve resident Services from Inventory by Backend VM. It should treat resident Services as impacted dependents, not update targets.
- VM Update should compose VM Configure before package maintenance. VM Configure may report reboot-required state but must not reboot.
- VM Update should snapshot the resident fortress-managed Services it will stop, stop them normally before VM reboot, and restore that same set after VM reachability returns.
- Template Update should reuse or extend the Template build and Template Verification machinery, but it must replace an existing Template copy instead of silently skipping when the Template already exists.
- Template Update should require explicit Host selection. A special all-Hosts mode may update every Host that declares the Template, but there should be no implicit fleet-wide behavior.
- Template Update should print existing VMs that declare the Template as lineage context and make clear those VMs are not changed.
- Service Update should compose Service Deploy first every time rather than detecting whether generated artifacts are stale.
- Service Update should pull or otherwise ensure declared runtime references, restart all fortress-owned units for the named Service, and verify those units are active.
- Service Update must not select newer Service versions on its own. Version selection happens through Inventory changes first.
- Routine package-based Update behavior should avoid removals and release transitions by default. Major OS, Proxmox, Template, database, or application migration work belongs to Upgrade workflows or runbooks.
- Package-manager specifics should stay below the domain model. The first implementation may be apt-based for Hosts, Templates, and VMs, but the domain terms should remain package-manager neutral.
- Use Inventory Entity Graph-style queries where possible for cross-Entity questions such as VMs placed on a Host, Services resident on a VM, Templates declared by a Host, and VMs declaring a Template.
- Add documentation that uses **Host Configure** and **VM Configure** instead of the retired generic **Configure** term.
- Do not introduce Fleet Update or Service Group Update in this PRD. Those remain deferred until individual workflows are proven.

## Testing Decisions

- Tests should focus on external workflow behavior: generated plan steps, command ordering, confirmation gates, validation failures, stop-on-failure behavior, and operator-visible output.
- Do not test implementation details such as private helper names when plan shape and command output can prove behavior.
- Add plan-builder tests mirroring the existing Service Launch, VM Lifecycle, and Host Readiness workflow tests.
- Add script-wrapper tests mirroring existing wrapper tests for `vm-up`, `host-up`, `service-launch`, `templates-build`, and `service-deploy`.
- Add Inventory Entity Graph tests for any new cross-Entity query used by Update workflows, such as resident Services by VM, ordinary VMs by Host, and VMs declaring a Template.
- Add Template Update tests that prove existing Template copies are replaced through an explicit update path and followed by Template Verification.
- Add Host Update tests that prove Host Configure runs first, impacted VMs are shown, VM shutdown precedes Host reboot, and the same VMs are restarted after reachability returns.
- Add VM Update tests that prove VM Configure runs first, resident Services are shown, Service stop precedes VM reboot, and the same Services are restored after reachability returns.
- Add Service Update tests that prove Service Deploy runs first, only the named Service is updated, all named-Service units are restarted, and active-state verification is required.
- Add documentation tests or extend existing runbook tests so the new Update runbook language stays aligned with the glossary and ADR.
- Live infrastructure acceptance tests are not required for the first implementation, but each workflow should be structured so live proof can be added later if needed.

## Out of Scope

- Fleet Update orchestration, batching, and failure isolation.
- Service Group Update.
- Application-level Service health checks beyond systemd active state.
- Host, Template, VM, or Service Upgrade workflows.
- OS release transitions, Proxmox major-version choreography, package removals, database major-version migrations, or application breaking migrations.
- Automatic selection of newer Service versions or image tags.
- Updating existing VMs as part of Template Update.
- Updating Templates as part of Host Update.
- Updating Services as part of VM Update, beyond graceful stop and restoration around VM reboot.
- Updating VMs or Services as part of Host Update, beyond graceful VM stop and restoration around Host reboot.
- A generalized polymorphic `update` command.

## Further Notes

The language and architectural decision are captured in the glossary and ADR 0029. ADR 0028 was also updated to use **Host Configure** now that generic **Configure** has been retired as a canonical glossary term.

The likely deep modules are the scoped Update plan builders and a small Inventory query surface for impacted dependents. These should keep the operator scripts thin and make most behavior testable without live Proxmox, SSH, apt, Podman, or systemd.
