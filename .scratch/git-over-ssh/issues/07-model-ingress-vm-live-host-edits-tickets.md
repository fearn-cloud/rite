Status: ready-for-agent
Label: ready-for-agent
Parent: 07-model-ingress-vm-live-host-edits-in-inventory.md

# Tickets: Model ingress VM live host edits in inventory

These tickets make the live Git SSH ingress VM address and OpenSSH listener policy inventory-owned and converged by Rite. Source issue: 07-model-ingress-vm-live-host-edits-in-inventory.

Work the **frontier**: any ticket whose blockers are all done.

## Model secondary VM addresses and Management SSH Policy

**What to build:** VM inventory can declare Secondary VM Addresses on interfaces and a Management SSH Policy for OpenSSH listener binding. The primary VM address remains the default Rite connection address, and inventory validation rejects malformed, duplicate, or non-VM-owned management listener addresses.

**Blocked by:** None — can start immediately.

- [ ] VM inventory accepts a primary interface address plus Secondary VM Addresses without changing the meaning of the primary address.
- [ ] VM inventory accepts an optional Management SSH Policy with bare IPv4 listener addresses.
- [ ] Validation rejects malformed Secondary VM Addresses and duplicate primary/secondary VM-owned addresses.
- [ ] Validation rejects Management SSH Policy listener addresses that are not declared on the same VM.
- [ ] Ordinary VMs without a Management SSH Policy keep the current unmanaged OpenSSH listener behavior.

## Project secondary VM addresses into provisioning intent

**What to build:** Fresh or rebuilt VMs receive the declared primary and secondary address shape through the existing PVE/OpenTofu/cloud-init provisioning intent, so the Ingress VM is provisioned with both its management address and Git SSH ingress address.

**Blocked by:** Model secondary VM addresses and Management SSH Policy.

- [ ] Generated provisioning intent includes Secondary VM Addresses alongside the primary VM interface address.
- [ ] The PVE/OpenTofu VM network projection still owns virtual NIC, VLAN, and primary first-boot address behavior.
- [ ] Existing single-address VM provisioning output remains unchanged except for the absence of empty secondary-address data.
- [ ] Tests cover generated provisioning intent for a VM with a Secondary VM Address.

## Converge secondary VM addresses during VM Configure

**What to build:** VM Configure persistently ensures declared primary and Secondary VM Addresses are present inside an already-running guest, runs this convergence before later VM configuration roles, and does not remove undeclared live guest addresses.

**Blocked by:** Model secondary VM addresses and Management SSH Policy.

- [ ] VM Configure includes an early VM network-address convergence step before roles that may rely on the VM's declared address shape.
- [ ] Re-running VM Configure when declared addresses are already present succeeds without unnecessary disruptive changes.
- [ ] Missing declared Secondary VM Addresses are made present and persistent in the guest.
- [ ] Undeclared live guest addresses are not pruned.
- [ ] Tests cover the VM Configure role ordering and idempotent address convergence contract.

## Converge Management SSH Policy during VM Configure

**What to build:** VM Configure renders a managed OpenSSH listener policy from Management SSH Policy inventory, validates sshd configuration, reloads sshd only when the managed listener policy changes, and leaves ordinary VMs unchanged when the policy is absent.

**Blocked by:** Converge secondary VM addresses during VM Configure.

- [ ] VM Configure includes an early Management SSH Policy convergence step after network-address convergence.
- [ ] A VM with a Management SSH Policy receives a managed OpenSSH listener drop-in.
- [ ] Generated OpenSSH configuration is validated before reload.
- [ ] sshd reload occurs only when the managed listener policy changes.
- [ ] Reload failure fails the workflow loudly rather than silently restarting sshd.
- [ ] Tests cover rendered listener policy, validation, reload-on-change behavior, and absence behavior for ordinary VMs.

## Validate Service TCP listener addresses against Ingress VM ownership

**What to build:** Inventory validation rejects Service TCP Ingress Routes whose listener address is not declared on the Ingress VM, while preserving literal bare-IP listener addresses and existing Caddy layer4 and DNS rendering behavior.

**Blocked by:** Model secondary VM addresses and Management SSH Policy.

- [ ] Validation resolves the Ingress VM and collects its primary and Secondary VM Addresses as bare IPv4 addresses.
- [ ] Validation accepts a Service TCP Ingress Route whose listener address is owned by the Ingress VM.
- [ ] Validation rejects a Service TCP Ingress Route whose listener address is owned by another VM or by no VM.
- [ ] HTTP-family Service Ingress Routes continue to use the primary Ingress address and do not gain address-selection fields.
- [ ] Tests cover accepted and rejected Service TCP listener-address ownership cases.

## Prove the Git SSH ingress surface end to end

**What to build:** The staged Forgejo SSH route is fully inventory-owned: the Ingress VM declares both required VM addresses, OpenSSH binds only the management address, Git SSH ingress DNS points at the Git SSH listener address, and re-running the relevant convergence and regeneration commands is idempotent.

**Blocked by:** Project secondary VM addresses into provisioning intent; Converge secondary VM addresses during VM Configure; Converge Management SSH Policy during VM Configure; Validate Service TCP listener addresses against Ingress VM ownership.

- [ ] The Ingress VM inventory declares its primary management address and Git SSH Secondary VM Address.
- [ ] The Ingress VM inventory declares a Management SSH Policy that binds OpenSSH only to the management address.
- [ ] VM Configure makes the live Ingress VM match the declared address and OpenSSH listener policy.
- [ ] Ingress regeneration preserves HTTP-family DNS behavior and keeps the Git SSH DNS record on the Git SSH listener address.
- [ ] A repeated convergence/regeneration run succeeds when the live system already matches inventory.
- [ ] Tests cover the inventory, provisioning, VM Configure, OpenSSH policy, and Service TCP listener validation paths together for the Git SSH ingress scenario.
