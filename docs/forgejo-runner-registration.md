# Forgejo Runner Registration

Fortress treats the phase-one Forgejo Runner registration as reproducible state, not as an irreplaceable file on the Runner VM. VM Configure derives the registration identity from Inventory, runs Forgejo's offline registration command on the Forgejo backend VM, and renders the Runner VM's `/var/lib/forgejo-runner/.runner` state file before starting `forgejo-runner.service`.

The desired registration is derived from VM-level `forgejo_runner_runtime` intent:

- runner name: `fortress-<vm name>`
- scope: the declared runtime scope, currently `instance`
- labels: the declared runtime labels
- Forgejo URL: the Forgejo service root URL
- runner secret identifier: a stable 16-character hexadecimal identifier derived from Forgejo service name, VM name, and runner name

Forgejo's offline registration command is the steady-state path used by VM Configure:

```sh
forgejo forgejo-cli actions register \
  --name fortress-forgejo-runner-vm \
  --scope '' \
  --labels debian-13:docker://debian:13 \
  --secret-file /run/fortress/forgejo-runner.secret
```

That command is idempotent for the derived shared secret. The first 16 hex characters identify the runner; the remaining 24 hex characters are the secret material. Re-running VM Configure refreshes the existing runner instead of creating another active runner for the same declared Runner VM. The returned UUID and token are rendered into the Runner VM runtime state file at `/var/lib/forgejo-runner/.runner`, so rebuilding the VM does not require restoring a backup of that file.

Manual interactive runner tokens are only a temporary bootstrap fallback. They should not become the normal operating model, because they recreate the irreplaceable VM-local state this design is removing.
