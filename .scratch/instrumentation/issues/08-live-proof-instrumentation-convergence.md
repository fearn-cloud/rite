# Live-proof Instrumentation Convergence

Status: ready-for-human

## What to build

Perform the live infrastructure proof for Instrumentation Convergence after the agent-ready implementation and runbook slices land. This slice should prove the real operator path against ordinary VMs and the live Observability Service, then record any live-only caveats or follow-up work.

## Acceptance criteria

- [ ] Run `instrumentation-converge` against real ordinary VMs.
- [ ] Confirm node exporter scrape targets for instrumented VMs are up in Prometheus.
- [ ] Confirm Grafana Alloy ships VM logs to Loki.
- [ ] Confirm at least one Service Telemetry Target appears in the generated observability configuration and is collected successfully.
- [ ] Confirm an opted-out VM is not configured or scraped by baseline VM-level Instrumentation, if a safe opt-out candidate exists.
- [ ] Record any firewall, VLAN, credential, or live Observability caveats in the issue comments or runbook.

## Blocked by

- .scratch/instrumentation/issues/07-document-instrumentation-operator-runbooks-and-migration-path.md

## Live proof checklist

Do not mark the live proof acceptance criteria complete until these checks have
actually run against live infrastructure.

- Confirm the operator workstation has the operator credentials needed for VM
  Configure, Service Update, and Observability Service access.
- Choose at least one real ordinary VM with baseline VM-level Instrumentation
  enabled.
- Run `just instrumentation-converge` against the live Inventory.
- In Prometheus, confirm Prometheus target health is up for the selected VM's
  node exporter target.
- Confirm the generated `fortress-vm-node-exporter` scrape targets include
  instrumented real ordinary VMs and exclude any safe opted-out VM candidate.
- In Loki, confirm Grafana Alloy is shipping logs from the selected VM.
- Confirm at least one Service Telemetry Target appears in the generated
  Observability Service configuration and is collected successfully.
- If a safe opted-out VM exists, declare `instrumentation.enabled: false`, rerun
  `just instrumentation-converge`, and confirm that opted-out VM is not
  configured or scraped by baseline VM-level Instrumentation.
- Record the checked VMs, Service Telemetry Target, observed Prometheus/Loki
  status, and any live caveats under issue comments before closing this issue.

## Live-only caveats

- Firewall and VLAN policy must allow the Observability Service to reach VM
  node exporter ports and Service Telemetry Target Published Ports. Local tests
  cannot prove live route or ACL state.
- The proof depends on current operator credentials for VM Configure,
  Service Update, and Observability Service UI/API access.
- Prometheus target health and Loki log visibility can lag behind convergence by
  at least one scrape interval; record the observed wait if this matters.
- A safe opt-out candidate may not exist during the live proof. If every
  ordinary VM should remain instrumented, record that and leave the opt-out
  acceptance criterion unchecked.
- Live Observability Service state may include old targets until the service
  reload finishes; verify the generated configuration and the collected status
  after the refresh settles.
