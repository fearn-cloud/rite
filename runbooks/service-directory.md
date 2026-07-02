# Service Directory

Use this runbook when deploying the stable Homepage Service, regenerating its generated navigation config, or changing Directory Entries.

## Model

The Service Directory is an internal-ingress-bound operator navigation page. It is generated from route-local Directory Entries declared on existing Service Ingress Routes, Host Ingress Routes, and NAS Ingress Routes.

A Directory Entry opts a route into navigation presentation only:

```yaml
directory_entry:
  enabled: true
  label: Grafana
  group: Operations
```

Use `label` for the operator-facing destination name. Use `group` for navigation language such as `Operations`, `Network`, `Hosts`, `Storage`, or `Development`. Do not copy `service_group` by default; Service Groups are launch semantics, while Directory Entry groups are how the operator scans the page.

## Deploy And Regenerate

`service-deploy service-directory` deploys the stable Homepage Service on the Service Directory Backend VM. It creates the Service Data Directory, installs the Quadlet unit, installs the generated baseline `services.yaml`, reloads systemd, and starts Homepage. Use it when the Service Directory Service itself changes, when the Backend VM is new, or when Homepage needs to be installed again.

`directory-regenerate` regenerates the Homepage `services.yaml` from current Inventory, pushes it to the Service Directory Backend VM, and restarts the Homepage unit. Use it when the Directory Entry set, labels, groups, or route hostnames have changed and the Homepage Service is already installed.

```sh
just service-deploy service-directory
just directory-regenerate
```

Service Launch and Service Group Launch refresh the Service Directory automatically only when the launched Service declares at least one enabled Directory Entry. They do this after Service Deploy, and after any needed Ingress Regeneration, so the generated navigation points at the current route state.

Host and NAS Directory Entry changes require explicit Directory Regeneration:

```sh
just directory-regenerate
```

Host Configure, Host Bootstrap, NAS Reconcile, and Ingress Regeneration do not currently refresh the Service Directory for Host or NAS route presentation changes.

## First Entries

The first Directory Entries are intentionally selected for operator navigation instead of inferred from every route.

Service routes:

- `service-directory`: `Service Directory` in `Operations`
- `observability`: `Grafana` in `Operations`
- `identity`: `Authentik` in `Operations`
- `dns-primary`: `Pi-hole Primary` in `Network`
- `dns-secondary`: `Pi-hole Secondary` in `Network`
- `forgejo`: `Forgejo` in `Development`
- `file-browser`: `Personal Files` in `Storage`
- `bazarr`: `Bazarr` in `Media`
- `clonarr`: `Clonarr` in `Media`
- `jellyfin`: `Jellyfin` in `Media`
- `media-file-browser`: `Media Files` in `Media`
- `prowlarr`: `Prowlarr` in `Media`
- `radarr`: `Radarr` in `Media`
- `radarr-anime`: `Radarr Anime` in `Media`
- `seerr`: `Seerr` in `Media`
- `sonarr`: `Sonarr` in `Media`
- `sonarr-anime`: `Sonarr Anime` in `Media`

Host routes:

- `molly`: `Molly Proxmox` in `Hosts`
- `neuromancer`: `Neuromancer Proxmox` in `Hosts`
- `straylight`: `Straylight Proxmox` in `Hosts`
- `wintermute`: `Wintermute Proxmox` in `Hosts`

NAS routes:

- `truenas`: `TrueNAS` in `Storage`

When adding or removing entries, regenerate the directory and have the operator review the labels and groups in the rendered page before considering the navigation set final.
