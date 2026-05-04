# OpenTofu VM Scaffold

Fortress keeps one root OpenTofu module under `tofu/`. That root module is the future fleet state boundary for VM provisioning. Inventory YAML remains the source of truth: `tofu/main.tf` decodes `inventory/vms/*.yaml`, while `inventory/hosts/*.yaml` drives generated Host provider coverage.

Run OpenTofu through `scripts/tofu-wrap <args...>`. The wrapper decrypts each Host's current `pve_tokens.tofu.value` from its Host Sibling SOPS File into an ephemeral `TF_VAR_pve_token_<host>` environment variable, regenerates the ignored HCL, and invokes `tofu` from the `tofu/` working directory. Direct `tofu` invocation is unsupported because Tofu must never read SOPS.

Run `scripts/tofu-generate` after changing Host inventory. The command writes ignored build output:

- `tofu/generated-providers.tf` contains one literal `provider "proxmox"` alias per Host and one sensitive `pve_token_<host>` variable per Host.
- `tofu/generated-vm-partitions.tf` contains one literal per-Host VM partition module, filtering decoded VMs by `placement.host`.

The generated files are not committed. They are reproducible from Inventory and are ignored alongside `.terraform/`, lock files, and local state.

OpenTofu provider aliases must be literal at configuration load time. Fortress therefore does not use dynamic provider indexing such as `proxmox[each.value.host]`; that shape cannot select a provider alias from VM data. Instead, generated static partition blocks bind each Host partition to a literal provider address like `proxmox.wintermute`.

The current `tofu/modules/vm-partition` module is validation-only and non-destructive. It establishes the Host partition interface without creating, updating, or destroying Proxmox VMs.
