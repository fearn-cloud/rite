# Forgejo runner options research

Date: 2026-07-09

## Current Fortress constraints

- `forgejo-vm` is the Infrastructure VLAN VM for Forgejo at `10.40.0.12/24` on the `straylight` Host.
- The glossary already says the Forgejo VM does not run CI runner workloads, and that future Forgejo Runner VMs are separate from the Forgejo VM.
- ADR-0017 says VMs are the Service security boundary. CI jobs are remote code execution, so runner placement should be treated as a trust-boundary decision, not just a capacity decision.
- SOPS currently has two age recipients: operator workstation and offline backup. Adding CI implies a deliberate runner recipient and `sops updatekeys` ceremony.
- Forgejo 15.0.3 is deployed, and live preflight evidence recorded no existing Forgejo Actions usage or registered action runners at that time.

## Upstream Forgejo facts

- Forgejo Runner is installed separately from the Forgejo instance; upstream docs explicitly recommend not installing it on the same machine as Forgejo for security reasons.
- Runner labels decide what jobs a runner can execute. Forgejo Runner supports `docker`, `lxc`, and `host` label types.
- `docker` labels run workflow steps as root inside a Docker/Podman-created job container.
- `lxc` labels run workflow steps as root inside an LXC container.
- `host` labels run workflow steps directly in a shell on the runner host. Upstream warns this has no isolation and a single job can permanently destroy the host.
- Workflows that need `docker build` need extra Docker access configuration. Sharing the host Docker socket is simple but gives workflow containers broad access to that Docker daemon. Docker-in-Docker isolates this better but usually requires a privileged DinD container.
- Runners can be registered at system, organization, user, or repository scope. Offline registration can be useful for IaC: generate a shared secret, register it inside Forgejo with `forgejo-cli actions register`, and generate the runner-side `.runner` file from the same secret.

## Plausible options

### 1. Dedicated Forgejo Runner VM, runner installed as a native systemd daemon

The VM is declared in `inventory/vms`, provisioned by OpenTofu, configured by Ansible, and runs the `forgejo-runner` binary as a systemd service. Jobs use Docker/Podman or LXC labels inside that VM.

This best matches the current Fortress model: the VM is the security boundary, the runner is separate from Forgejo, and the VM can be backed up, updated, destroyed, or rotated through existing workflows. The first implementation can avoid exposing host Docker sockets outside the runner VM.

Trade-offs: more VM overhead, more Ansible surface, and Docker/Podman/LXC setup has to become a first-class VM configuration concern.

### 2. Dedicated Forgejo Runner VM, runner deployed as a Quadlet Service

The VM is still the boundary, but the runner daemon itself is a normal Fortress Service using the official Forgejo Runner OCI image. Jobs still need Docker/Podman/DinD wiring.

This fits existing Service Deploy machinery and avoids a new Native Service role. It also aligns with Forgejo's documented OCI image path.

Trade-offs: runner-as-container plus job-containers creates nested-container complexity. Docker-in-Docker tends to require privileged configuration, and mounting a host socket hands jobs control over that VM's container daemon.

### 3. Dedicated Forgejo Runner VM with Docker-in-Docker sidecar

Run the runner and a DinD daemon together, either via a custom Service shape or native systemd units. The runner points `DOCKER_HOST` at the DinD daemon.

This is attractive for workflows that build images, because it keeps image-build side effects away from the VM's main container daemon.

Trade-offs: privileged DinD is still powerful inside the runner VM, cache/image persistence needs explicit cleanup policy, and Fortress does not currently model multi-container runner internals separately from ordinary Services.

### 4. Dedicated Forgejo Runner VM with LXC job labels

Install the runner natively and configure labels like `bookworm:lxc://debian:bookworm`. Jobs run in LXC containers inside the runner VM.

This may give a better "fresh system" feel than plain Docker labels and can support nested Docker/KVM shapes according to Forgejo docs.

Trade-offs: LXC inside a VM is a more specialized operational path; runner needs passwordless sudo for LXC commands; failures will be less familiar than Podman Quadlets; it may become its own platform inside a platform.

### 5. Proxmox LXC container as the runner host

Instead of a VM, create a Proxmox LXC container dedicated to runner workloads.

This is lighter than a VM, but it conflicts with the current Fortress domain model: Inventory and OpenTofu manage VMs, not Proxmox containers, and ADR-0017 treats VMs as the primary security boundary. It would require broadening the Entity model and provisioning path.

Trade-offs: lower overhead, but a large architectural change for a CI component that runs untrusted workflow code.

### 6. Host-level runner on a Proxmox Host

Install Forgejo Runner directly on `straylight`, `wintermute`, or another Host.

This is the smallest moving-parts count and the largest blast radius. With `host` labels, jobs execute directly on the Host; with Docker labels, jobs can still pressure the Host container daemon and filesystem. This does not fit Fortress's current security model.

Recommendation: reject unless limited to a deliberately disposable Host, which Fortress does not currently have.

### 7. Co-located runner on `forgejo-vm`

Install the runner alongside Forgejo.

This is operationally convenient but contradicts both upstream guidance and the existing Fortress glossary. Workflow compromise could affect Forgejo data, repositories, SSH keys, or package/auth state.

Recommendation: reject.

### 8. External runner outside Fortress

Run the runner on an operator workstation, a cloud VM, or another non-Fortress machine and register it with Forgejo.

This avoids adding runner capacity to Proxmox immediately and can be a useful bootstrap path. It does not need inbound access to the runner if the runner can reach Forgejo.

Trade-offs: CI becomes dependent on something outside Inventory, secrets handling is less uniform, and it postpones rather than solves the Fortress runner model.

### 9. Kubernetes runner pool

Run Forgejo runners in a Kubernetes cluster using a Helm chart or custom deployment.

This is most useful if Fortress later has a Kubernetes substrate or needs autoscaling runner pools. It is currently a poor first fit because Fortress does not model Kubernetes as a Service substrate, and Forgejo runner Kubernetes setups commonly still rely on nested Docker/DinD patterns.

Recommendation: defer.

## Provisional recommendation

Start with one dedicated Forgejo Runner VM, separate from `forgejo-vm`, with tightly scoped runner registration and labels. Choose the job isolation mode based on the first CI workload:

- For ordinary validation (`python3 -m unittest`, schema checks, lint, docs checks), use `docker` or Podman labels with pinned images and no Docker socket sharing.
- For image-building workflows, prefer a separate runner label backed by DinD inside the runner VM, accepting that the runner VM is disposable/replaceable if compromised.
- Avoid `host` labels for anything that can be triggered by repository changes.

The first design decision to make is whether the runner VM is allowed to decrypt Fortress SOPS secrets. If yes, it becomes a highly trusted automation principal and needs a runner age Recipient plus narrow registration scope. If no, first CI should be limited to checks that do not need live infrastructure credentials.

## Sources

- Forgejo Runner installation guide: https://forgejo.org/docs/v15.0/admin/actions/installation/binary/
- Forgejo Runner Docker installation: https://forgejo.org/docs/v15.0/admin/actions/installation/docker/
- Forgejo Runner configuration: https://forgejo.org/docs/v15.0/admin/actions/configuration/
- Securing Forgejo Actions Deployments: https://forgejo.org/docs/v15.0/admin/actions/security/
- Forgejo Runner registration: https://forgejo.org/docs/v15.0/admin/actions/registration/
- Utilizing Docker within Actions: https://forgejo.org/docs/v15.0/admin/actions/docker-access/
- Proxmox VE administration guide: https://pve.proxmox.com/pve-docs/pve-admin-guide.html
