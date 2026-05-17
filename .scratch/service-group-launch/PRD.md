# PRD: Service Group Launch and Service Network Split

**Status**: ready-for-agent
**Date**: 2026-05-17
**Companion documents**: `CONTEXT.md`, `docs/adr/0030-service-groups-are-logical-service-networks-own-podman-networking.md`

---

## Problem Statement

The operator wants to deploy a coherent set of Services, such as the media Services, as one intentional workflow instead of manually launching each Service one at a time. Today `service-launch` is scoped to exactly one Service, while `service_group` is overloaded: it sounds like a logical group of Services, but the implementation uses it to render a shared Podman network and Container Alias namespace.

That overload creates two problems. First, asking for "deploy the media Service Group" has no first-class command even though the operator thinks of media as one group. Second, putting a Service in a group accidentally grants private network reachability because grouping and networking are the same field. The operator needs logical Service grouping and VM-local Service networking to be separate concepts, then needs a group-scoped launch workflow that is explicit about order, blast radius, failure behavior, and Ingress regeneration.

## Solution

Introduce **Service Network** as the VM-local Podman networking concept and preserve **Service Group** as the logical/operator grouping concept. Existing Services that used `service_group` to share a Podman network keep their logical `service_group` and add a matching `service_network` so runtime behavior does not change during migration.

Add **Service Group Launch** as a first-class operator workflow invoked as `service-group-launch <group>` and exposed through Just. For the first implementation, a launchable Service Group must have all launched Services on one Backend VM, with that VM declaring the complete Service Group Launch Order. The workflow runs VM Lifecycle Convergence once for the shared Backend VM, deploys every ordered Service through Service Deploy, stops at the first failed Service Deploy without rollback, and runs Ingress Regeneration once at the end only if at least one launched Service declares Ingress.

For the media group, the first launch order is Prowlarr, Sonarr, Radarr, Bazarr, Jellyfin, then Seerr.

## User Stories

1. As the operator, I want **Service Group** to mean a logical group of Services, so that the term matches how I talk about media, download, observability, and similar groups.

2. As the operator, I want shared Podman networking to be called **Service Network**, so that runtime connectivity is not confused with logical grouping.

3. As the operator, I want a Service to declare `service_group` for logical grouping, so that group-level workflows can find the Services I intend to operate together.

4. As the operator, I want a Service to declare `service_network` for private Service-to-Service networking, so that network reachability is explicit.

5. As the operator, I want existing shared-network Services to migrate to both `service_group` and `service_network`, so that the migration preserves runtime behavior.

6. As the operator, I want Services with the same `service_network` to share one VM-local Podman network, so that private Container Alias communication keeps working where it is explicitly requested.

7. As the operator, I want Services with the same `service_group` but no shared `service_network` to avoid private network coupling, so that logical grouping does not grant reachability.

8. As the operator, I want validation to reject a Service Network that spans Backend VMs, so that a VM-local Podman network is never implied across machines.

9. As the operator, I want validation to check Container Alias collisions inside a Service Network, so that private DNS names remain unambiguous.

10. As the operator, I want Service Group Launch to have its own command, so that `service-launch <service>` remains clearly scoped to a single Service.

11. As the operator, I want to run `service-group-launch media`, so that deploying media does not require remembering six separate launch commands.

12. As the operator, I want Just to expose Service Group Launch, so that the command surface stays consistent with the rest of fortress.

13. As the operator, I want Service Group Launch to require one shared Backend VM for the first implementation, so that group launch has a clear operational boundary.

14. As the operator, I want the shared Backend VM to declare the group launch order, so that the VM that runs the Services owns the local launch choreography.

15. As the operator, I want validation to require every launch-order entry to reference an existing Service, so that typos are caught before a workflow starts.

16. As the operator, I want validation to require every launch-order entry to have the matching `service_group`, so that the VM declaration and Service declarations agree.

17. As the operator, I want validation to require every launch-order entry to use the declaring VM as its Backend VM, so that Service Group Launch cannot silently cross VM boundaries.

18. As the operator, I want validation to require every Service in the launched group on that Backend VM to appear exactly once in launch order, so that no group member is skipped or duplicated.

19. As the operator, I want validation to reject declaring the same launchable Service Group on more than one VM, so that a group-targeted launch has one unambiguous plan.

20. As the operator, I want Service Group Launch to run VM Lifecycle Convergence once before deploying group Services, so that the Backend VM is ready without repeating the VM workflow for every Service.

21. As the operator, I want Service Group Launch to pass operator confirmation policy through to VM Lifecycle Convergence, so that the group workflow follows the same approval behavior as Service Launch.

22. As the operator, I want Service Group Launch to deploy Services in the explicit order, so that operational dependencies are represented deliberately instead of by filenames or alphabetic sorting.

23. As the operator, I want the first media launch order to be Prowlarr, Sonarr, Radarr, Bazarr, Jellyfin, then Seerr, so that the indexing/catalog/subtitle/playback/request chain comes up in a sensible order.

24. As the operator, I want each group member deployed through ordinary Service Deploy, so that Quadlet and Native Services both work through their existing deploy paths.

25. As the operator, I want Service Group Launch to stop at the first failed Service Deploy, so that later Services are not deployed against a partially failed group.

26. As the operator, I want Service Group Launch to avoid rollback after a failure, so that durable VM and Service state is not destroyed by a downstream deploy error.

27. As the operator, I want rerunning Service Group Launch after a fix to be safe, so that already successful Service Deploy phases can be converged again.

28. As the operator, I want Service Group Launch to skip Ingress Regeneration when a Service Deploy fails, so that routing is refreshed only after the group deploys cleanly.

29. As the operator, I want Service Group Launch to run Ingress Regeneration once at the end when any launched Service declares Ingress, so that Caddy/DNS refresh happens efficiently.

30. As the operator, I want Service Group Launch to avoid Service Update restart and active-check semantics, so that Launch remains distinct from Update.

31. As the operator, I want Service Group Launch to support Native Services as well as Quadlet Services, so that logical groups are independent of deployment substrate.

32. As the operator, I want a clear error when the requested group is not declared as launchable, so that I know whether I need to add VM launch-order metadata.

33. As the operator, I want a clear error when a launchable group contains Services on multiple Backend VMs, so that first-pass launch constraints are obvious.

34. As the operator, I want the workflow result to report which phase and Service failed, so that I can fix the right Inventory or deployment issue.

35. As the operator, I want generated Quadlet network names to come from `service_network`, so that the code reflects the new domain language.

36. As the operator, I want existing media, download, observability, identity, DNS, and other grouped Services to keep their current runtime networking where they currently relied on it, so that the terminology migration is not a behavior change.

37. As a future maintainer, I want the Inventory Entity Graph to expose a deep, testable Service Group Launch intent, so that workflow planning does not duplicate raw YAML traversal.

38. As a future maintainer, I want Service Network validation to be isolated from Service Group Launch validation, so that runtime topology and operator workflow rules can evolve independently.

39. As a future maintainer, I want tests to describe externally visible plans, rendered artifacts, schema acceptance, and validation failures, so that refactors do not freeze implementation details.

40. As a future maintainer, I want documentation and runbooks to use **Service Group** and **Service Network** consistently, so that future agents do not reintroduce the old overloaded meaning.

## Implementation Decisions

- Respect the domain split recorded in ADR 0030: **Service Group** is logical/operator grouping, and **Service Network** is VM-local Podman networking.

- Keep `service_group` as the Service-level logical group field. Add `service_network` as the Service-level private runtime network membership field.

- Migrate existing Services that relied on `service_group` for shared Podman networking by adding a matching `service_network`. This preserves current Podman network behavior while freeing `service_group` for logical grouping.

- Change Quadlet rendering so shared network artifacts and `Network=` lines are driven by `service_network`. Services without `service_network` keep their isolated per-Service network behavior.

- Change Service Network validation so same-network Services must share one Backend VM and share a Container Alias namespace. This is the old Service Group validation behavior moved to the new concept.

- Keep Service Group validation independent from Service Network validation. Logical grouping alone must not create network reachability.

- Add VM-level launch metadata for launchable Service Groups. The VM declaration owns each launchable group name and its complete launch order.

- Add validation for VM-declared Service Group Launch Order: listed Services must exist, match the declared `service_group`, use the declaring VM as `backend.vm`, appear exactly once, cover every Service in that group on that VM, and not be declared as launchable on another VM.

- Add a deep Inventory Entity Graph query for Service Group Launch intent. The interface should return the target group name, shared Backend VM name, ordered Service names, and whether Ingress Regeneration is required. This keeps workflow planning small and testable.

- Add a Service Group Launch workflow builder that composes existing workflow commands: VM Lifecycle Convergence once, Service Deploy once per ordered Service, and conditional Ingress Regeneration once at the end.

- Add an executable script for `service-group-launch <group> [--auto-confirm]` that validates arguments, builds the plan, runs the shared Operator Workflow Runner, and renders group-specific failure diagnostics.

- Add a Just recipe for Service Group Launch that mirrors the existing `service-launch` auto-confirm behavior.

- Preserve `service-launch <service>` as the single-Service workflow. Do not overload it with group targets.

- Preserve Launch/Update separation. Service Group Launch does not restart and actively check units beyond what Service Deploy already does.

- Support Quadlet and Native Services in Service Group Launch because grouping is independent of deployment substrate.

- Configure the media VM with a launchable `media` Service Group ordered as Prowlarr, Sonarr, Radarr, Bazarr, Jellyfin, then Seerr.

- Keep failure semantics aligned with existing Service Launch: stop on failure, report the failing phase, do not roll back durable Backend VM or earlier Service Deploy work.

## Testing Decisions

- Tests should verify external behavior and domain contracts: accepted schema shapes, validation errors, rendered Quadlet artifacts, workflow plans, command invocation order, and operator-facing diagnostics.

- Schema tests should cover `service_network` on Services and VM-declared Service Group Launch metadata. Prior art: inventory schema tests for Service and VM YAML acceptance/rejection.

- Cross-file validation tests should cover Service Network same-Backend and alias-collision behavior, plus Service Group Launch Order completeness, duplicates, missing Services, wrong group membership, wrong Backend VM, and duplicate launchable group declarations. Prior art: existing inventory cross-file validator tests for Service Group same-VM and alias collision.

- Quadlet rendering tests should prove `service_network` controls shared network artifact names and container `Network=` wiring. Prior art: existing golden and focused Quadlet rendering tests for shared group networks.

- Inventory Entity Graph tests should cover Service Group Launch intent success, unknown group, missing launch declaration, missing Backend VM, mixed Backend VM, ordered Service names, and Ingress Regeneration requirement.

- Workflow plan tests should cover the exact phase shape: VM Lifecycle Convergence, ordered Service Deploy phases, and optional final Ingress Regeneration.

- Workflow script tests should cover CLI usage, unknown flags, `--auto-confirm` propagation to VM Lifecycle Convergence, command order, failure reporting, and stop-on-first-failed-Service behavior. Prior art: Service Launch and Service Update workflow tests.

- Justfile tests should cover the new Service Group Launch recipe and auto-confirm mapping. Prior art: existing workflow tests that assert Just recipe command surfaces.

- Inventory migration should be tested by loading the real Inventory and asserting existing Services remain valid after adding `service_network` where needed.

- Documentation tests should be updated if existing tests assert command names, workflow names, or glossary terminology around Service Group.

## Out of Scope

- Ongoing **Service Group Update** semantics remain out of scope. This PRD covers Launch, not routine runtime advancement.

- Multi-Backend Service Group Launch is out of scope. A Service Group may be logical, but first-pass Service Group Launch requires one Backend VM.

- Dependency inference is out of scope. Service Group Launch uses explicit launch order, not app dependency discovery.

- Rollback after partial group launch failure is out of scope.

- Application-level health checks are out of scope. Service Group Launch does not add health semantics beyond existing Service Deploy behavior.

- Continuous automated configuration of arr applications is out of scope. This PRD is about deployment workflow and grouping/network terminology.

- A standalone `inventory/service-groups/` entity directory is out of scope for the first implementation. Launchable groups are declared on the shared Backend VM.

- Changing Ingress, DNS, NAS Reconcile, Host readiness, or Service Deploy internals beyond what is needed to compose the workflow is out of scope.

## Further Notes

- `CONTEXT.md` has already been updated with the new glossary terms and resolved ambiguities.

- ADR 0030 records the hard-to-reverse terminology and schema boundary decision.

- The PRD intentionally keeps Service Group Launch as a composition of existing operator workflows. This follows the established workflow style used by Service Launch, Host Readiness, and scoped update workflows.

- The implementation should be broken into small issues if converted with `to-issues`: schema and migration, validation and graph intent, Quadlet renderer migration, workflow command, and documentation/runbook updates are natural slices.
