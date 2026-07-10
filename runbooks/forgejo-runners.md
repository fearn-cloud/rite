# Forgejo runners

Phase-one Forgejo Actions are limited to non-mutating repository validation. The Forgejo Runner VM exists to run checks that inspect the repository, such as schema validation, unit tests, linting, and generated-artifact drift checks. It is not a deployment principal for Fortress infrastructure.

The Runner VM is not an age Recipient and does not decrypt Fortress SOPS secrets. Do not add runner age recipient material to `age/recipients.txt`, `.sops.yaml`, runner inventory, or runner workflows as part of phase-one runner work. CI jobs must not call `sops --decrypt`, receive decrypted secret files, or receive credentials that let them converge live infrastructure.

Live Host, VM, NAS, PBS, and Service convergence remains Operator-owned. The operator still runs Host Configure, VM Up/Configure/Destroy, NAS reconciliation, PBS backup workflows, Service Deploy/Launch, and instrumentation convergence from the operator environment where the existing SOPS and management trust boundaries apply.

Runner labels describe validation capabilities only. Labels may identify the validation environment, such as Debian version and job-container image, but must not advertise deployment, management, production, Host, VM, NAS, PBS, Service, SOPS, Tofu, or Ansible authority.

Job containers do not receive container-runtime socket access in phase one. The runner service may use the dedicated runner user's Podman socket to create job containers, but jobs themselves must not mount Docker or Podman sockets unless a later design explicitly changes that boundary.

Deployment runners require a separate later design. That design must decide whether a deployment runner exists at all, how it is isolated, what credentials it receives, how SOPS recipients are managed, what network reachability it needs, and how human approval gates preserve Operator ownership.

## First validation workflow

The first Forgejo Actions workflow lives at `.forgejo/workflows/validation.yaml`. It runs on the declared validation label from `inventory/vms/forgejo-runner-vm.yaml`:

```text
debian-13:docker://debian:13
```

The job bootstraps only disposable Debian package dependencies inside the job container, checks out the repository, validates Inventory cross-file relationships, and runs the Forgejo runner policy tests. It does not need Host, VM, NAS, PBS, or Service credentials.

Trigger it from Forgejo by opening the repository, choosing **Actions**, selecting **Fortress validation**, and using **Run workflow**. A push to `main` also queues the workflow once the runner is registered and online.

Inspect the run from the same **Actions** page. Open the queued or completed run, then open the **Repository validation** job to check that it was picked up by the Runner VM label and that the validation steps completed. If the run stays queued, inspect the runner registration and service health on `forgejo-runner-vm`; do not broaden the workflow with deployment credentials to make it pass.
