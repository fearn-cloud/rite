Status: done

## Parent

docs/prds/initial-building-blocks.md

## What to build

Service deployment via Podman Quadlets as the default substrate. Multi-container layouts are first-class. Podman secrets are injected via the `_FILE` env convention; each Service runs on an isolated Podman network unless it joins a same-VM Service Group; Service-owned container volumes are bind-mounts under `/srv/services/<service>/`; Share-backed Volumes reference a Mount Name declared on the Backend VM, bind the VM-side Mount root or a safe relative subpath, and add systemd ordering on that `.mount` unit; image tags are pinned and auto-update is disabled.

The initial renderer uses rootful system Quadlets; fortress treats VM placement as the Service security boundary.

## Acceptance criteria

- [x] Service yaml schema with `deploy.type: quadlet`: hostname, optional `service_group`, singular backend (VM + port), ingress block (enabled/exposure/TLS strategy/auth), optional Service Data Owner, deploy block with list of containers (image, structured publish ports, source/target volumes, env, secrets, depends_on)
- [x] Optional Service Data Owner (`storage.uid`/`storage.gid`) creates/chowns Service-owned paths only; Share-backed Volume ownership remains governed by the VM Mount/Dataset ownership convention
- [x] Quadlet Services may publish multiple TCP/UDP ports, but exactly one TCP-capable Published Port with `ingress: true` satisfies the HTTP-family Ingress Backend when ingress is enabled
- [x] Quadlet renderer ansible role produces `.container`, `.network`, dependency-aware unit options
- [x] Quadlets are rendered as rootful system units; rootless user Quadlets are out of scope for this issue
- [x] `depends_on` validates same-Service container references, rejects cycles, and renders start-order/stop-coupling systemd unit dependencies without promising application readiness
- [x] Podman secrets created from `secrets:` in the Service Sibling SOPS File, installed with service-scoped names, and consumed only via env vars ending in `_FILE`
- [x] Non-secret `env` is declared in Service yaml; `env` and Quadlet Fragment `Environment=` entries cannot override generated secret `_FILE` env vars or each other
- [x] Each Service gets its own Podman network by default; Services in the same Service Group share a group network
- [x] Deploying one Service ensures its isolated or Service Group network exists but does not deploy other Services in the Service Group
- [x] Container `name` becomes the Podman network DNS alias, while rendered container identity is service-scoped as `<service>-<container>`; validator rejects alias collisions within each Service or Service Group network
- [x] Runtime artifacts use `fortress-` names: container units and Podman container names as `fortress-<service>-<container>`, isolated networks as `fortress-<service>`, and Service Group networks as `fortress-group-<service_group>`
- [x] Container volumes bind-mounted under a predictable path (e.g., `/srv/services/<name>/`)
- [x] Share-backed Volumes use the service schema shape `mount`, `source`, `container`, and optional `access`; they do not declare NAS Endpoint, Dataset, Share, or protocol details directly
- [x] Share-backed Volumes resolve `mount` against the Service's Backend VM `mounts[].name`, translate to bind mounts from the Mount's `mount_point` or a safe relative subpath, and add `Requires=` + `After=` on the matching `.mount` unit; unusual extra native options use validated Quadlet Fragments
- [x] Share-backed Volume validation rejects missing Backend VM Mount Names, absolute non-root sources, `..` traversal, and attempts to widen a read-only Mount to read-write
- [x] Service deployment validates declared Share-backed Volume subpaths before starting containers, but does not run NAS Reconcile, create NAS Shares, or create VM Mount units implicitly
- [x] Quadlet Fragment sidecar files use native Quadlet syntax but cannot override fortress-owned generated keys such as image, container identity, network, published ports, volumes, secrets, or generated dependencies
- [x] Quadlet Fragments live under `inventory/services/<service>.quadlet.d/` as `<container>.container` fragments plus optional `network.network`; unknown fragment filenames are invalid
- [x] Quadlet Fragments are plaintext-only and must not contain secret values; all Service secrets go through the Service Sibling SOPS File and `_FILE` injection
- [x] Quadlet Fragment validation derives forbidden keys from the generated Quadlet for that Service/container; repeated additive keys such as `Unit.Requires`, `Unit.After`, and `Unit.Wants` may add values without replacing/removing generated dependencies
- [x] Images require either a non-`latest` tag or a digest; untagged images and `:latest` are rejected; auto-update is disabled
- [x] Golden-file tests cover: single-container, multi-container, secrets injection, networks, NFS-mount deps, image pinning variants
- [x] Cross-file validator extended: all Published Port collisions on the same VM, hostname uniqueness for ingress-enabled Services, VM ref resolution
- [x] Validator requires `hostname` only when `ingress.enabled: true`; duplicate hostname checks apply only to ingress-enabled Services
- [x] Ingress defaults: `enabled: true` when `hostname` is present, `enabled: false` when absent; enabled Ingress defaults to `exposure: lan_only`, `tls: letsencrypt_dns`, and `auth.type: none`
- [x] Cross-file validator treats `service_group` as a globally unique Service Group name and rejects a Service Group whose Services point at different Backend VMs
- [x] `just service-deploy service=<name>` deploys or redeploys a single service
- [x] `service-deploy` requires the Backend VM Sibling SOPS File for SSH and requires the Service Sibling SOPS File only when containers declare Service Secrets
- [x] Redeploy prunes only fortress-rendered Quadlet units for the Service and obsolete service-scoped Podman secrets; it never prunes `/srv/services/<service>/` data
- [x] Redeploy performs a full Service restart in dependency order: stop containers in reverse topological order and start them in topological order; avoiding data loss or bad state takes priority over zero-downtime updates
- [x] If a container fails to start, deploy aborts remaining starts, surfaces the failed unit name and relevant journal/status guidance, and leaves rollback as an explicit operator action
- [x] `runbooks/new-service.md` written
- [x] Live acceptance demo deploys a contrived but real-world-shaped multi-container Service on a VM: web + postgres-like + redis-like containers, Service Secret, Service-owned volume, Share-backed Volume referencing an existing Backend VM Mount with `source: /`, `depends_on`, multiple Published Ports with one Ingress Backend, optional Service Data Owner, and one validated Quadlet Fragment

## Out of scope

- Service deletion/destruction is not automated in this issue. `service-deploy` only deploys or redeploys a declared Service and prunes obsolete rendered artifacts within that Service; a later `service-destroy` workflow must define safe removal while preserving Service data by default.
- Compatibility with the pre-issue-07 scaffolded Quadlet shape is out of scope; existing fixtures should be rewritten to the new schema rather than supported through a migration layer.

## Blocked by

.scratch/initial-building-blocks/issues/06-nfs-integration.md

## Comments

> *This was generated by AI during triage.*

Completion check: implementation is present across the Service schema/model defaults, cross-file validator, Quadlet renderer, deploy workflow, runbook, static demo inventory, and acceptance workflow. Verified with targeted service-layer tests and the full test suite.

Verification:

- `python3 -m unittest tests.test_service_quadlet_rendering tests.test_service_deploy_workflow tests.test_inventory_cross_file_validator tests.test_inventory_schemas tests.test_acceptance_service_layer_workflow tests.test_new_service_runbook` — 80 tests passed.
- `python3 -m unittest discover -s tests` — 262 tests passed.
