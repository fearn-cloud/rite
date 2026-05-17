# Declare and validate Service Group Launch Order on VMs

Status: ready-for-agent

## Parent

.scratch/service-group-launch/PRD.md

## What to build

Add VM-level metadata for launchable Service Groups. A launchable Service Group is declared on its shared Backend VM and includes the complete Service Group Launch Order for that VM. Configure the Media VM with the first `media` Service Group Launch Order: Prowlarr, Sonarr, Radarr, Bazarr, Jellyfin, then Seerr.

Validation should make the VM declaration and member Service declarations agree before any workflow starts.

## Acceptance criteria

- [ ] VM schema accepts launchable Service Group metadata with an explicit ordered Service list.
- [ ] The Media VM declares launchable `media` ordered as Prowlarr, Sonarr, Radarr, Bazarr, Jellyfin, then Seerr.
- [ ] Validation rejects launch-order entries that reference missing Services.
- [ ] Validation rejects launch-order entries whose Service does not declare the matching `service_group`.
- [ ] Validation rejects launch-order entries whose Service uses a different Backend VM than the declaring VM.
- [ ] Validation rejects missing and duplicate entries when compared with every Service in that group on the declaring Backend VM.
- [ ] Validation rejects declaring the same launchable Service Group on more than one VM.

## Blocked by

- .scratch/service-group-launch/issues/01-introduce-service-network-inventory-field.md

