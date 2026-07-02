# Add Directory Regeneration workflow

Status: ready-for-agent

## What to build

Add Directory Regeneration as an explicit operator workflow that reads current Inventory, renders the generated Homepage configuration for the Service Directory, writes it to the `service-directory` Backend VM, and reloads or restarts Homepage without redeploying source Services.

## Acceptance criteria

- [ ] A `directory-regenerate` script or equivalent operator entrypoint regenerates the Service Directory from current Inventory.
- [ ] The workflow writes the generated Homepage config to the `service-directory` Backend VM.
- [ ] The workflow reloads or restarts Homepage so generated changes take effect.
- [ ] The workflow fails with clear diagnostics when the `service-directory` Service or Backend VM is missing.
- [ ] Service Deploy for `service-directory` remains responsible only for stable Homepage installation and scaffolding.
- [ ] Fast workflow tests cover success, missing target, and generated-content update behavior.

## Blocked by

- .scratch/service-directory/issues/04-generate-homepage-config-from-directory-entries.md
