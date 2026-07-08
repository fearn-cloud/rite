# Forgejo Upgrade

Use this runbook for the explicit application Upgrade from the currently
declared Forgejo container image to the newest supported Forgejo release.

As of 2026-07-08, `inventory/services/forgejo.yaml` declares:

```yaml
image: codeberg.org/forgejo/forgejo:11.0.1
```

The newest upstream release is `15.0.3`, published on 2026-06-10. Forgejo
15.0 is the current LTS line and is supported until 2027-07-15. Forgejo 11.0
LTS is supported until 2026-07-16.

This is an Upgrade, not a routine Service Update: it crosses major versions,
runs database migrations, and includes breaking changes documented by upstream.

## Source Notes

Primary sources checked:

- Forgejo release index: <https://forgejo.org/releases/>
- Forgejo 15.x releases: <https://forgejo.org/releases/15.x/>
- Forgejo upgrade guide: <https://forgejo.org/docs/v15.0/admin/upgrade/>
- Forgejo v15.0 announcement: <https://forgejo.org/2026-04-release-v15-0/>
- Forgejo v12.0 release notes: <https://codeberg.org/forgejo/forgejo/src/branch/forgejo/release-notes-published/12.0.0.md>
- Forgejo v13.0 release notes: <https://codeberg.org/forgejo/forgejo/src/branch/forgejo/release-notes-published/13.0.0.md>
- Forgejo v14.0 release notes: <https://codeberg.org/forgejo/forgejo/src/branch/forgejo/release-notes-published/14.0.0.md>
- Forgejo v15.0 release notes: <https://codeberg.org/forgejo/forgejo/src/branch/forgejo/release-notes-published/15.0.0.md>

## Target Path

Preferred path: upgrade directly from `11.0.1` to `15.0.3`.

Forgejo's upgrade guide says to read version-specific notes, then upgrade
straight to the latest released Forgejo version by replacing the binary or
container image; migrations run on startup.

Fallback path if the direct upgrade fails and the failure is not obvious:

1. `11.0.1` to `11.0.15`
2. `11.0.15` to `12.0.4`
3. `12.0.4` to `13.0.5`
4. `13.0.5` to `14.0.5`
5. `14.0.5` to `15.0.3`

Only use the fallback to isolate the failing major-version boundary. Do not
leave production on 12.x, 13.x, or 14.x; those lines are already out of
support.

## Breaking Change Checklist

Check these before changing Inventory:

- Check for customized templates, CSS, or public content under Forgejo's custom
  path. If present, compare against the new version and update the custom files
  before upgrading. Do not use `forgejo help` to locate `CustomPath`; use the
  configuration tab in the Forgejo Site administration panel.
- Verify the Backend VM has Git `>= 2.34.1`; Forgejo 13.0 raises the minimum
  required Git version.
- Check whether Forgejo Actions are used:
  - Forgejo 13.0 validates workflow YAML more strictly; existing workflows
    should be reviewed for schema errors before the upgrade.
  - Forgejo 13.0 changes previously copied artifact download URLs; old bookmarked
    artifact URLs may no longer work.
  - Forgejo 15.0 adds reusable workflow expansion, OIDC support, form-based
    runner registration, and ephemeral runner support. Existing runners should
    keep working, but runner registration/admin procedures may change.
- Check whether API clients rely on public-only access tokens, repository
  deletion, template generation, artifact URLs, repository listing, or admin hook
  APIs. Forgejo 12.0 through 15.0 include breaking API and permission changes.
- Check specific API/client assumptions:
  - URL query API authentication is removed in Forgejo 12.0 when
    `[security].DISABLE_QUERY_AUTH_TOKEN=false` had been explicitly set.
  - `POST /repos/{owner}/{repo}/contents` now requires the documented `sha`.
  - `GET /api/v1/admin/hooks` is paginated in Forgejo 14.0.
  - Template generation and repository deletion APIs require the same permission
    scopes as repository creation in Forgejo 15.0.
  - Forgejo 15.0 tightens public-only token behavior and changes some private
    repository access failures from `403` to `404`.
- Check whether the instance uses rootless Forgejo container images and a config
  volume mounted at `/etc/gitea`. This service uses
  `codeberg.org/forgejo/forgejo`, not the rootless image, but verify the live
  container before the upgrade. If rootless and still using `/etc/gitea`, move
  the config to `/var/lib/gitea/custom/conf/app.ini` or set `GITEA_APP_INI`.
- Check whether `app.ini` sets removed or changed options:
  `TEST_CONFLICTING_PATCHES_WITH_GIT_APPLY`, `CSRF_COOKIE_HTTP_ONLY`,
  `repository.pull-request.ADD_CO_COMMITTER_TRAILERS`, or old logger syntax.
- Check whether any automation parses Forgejo CLI output:
  - Forgejo 12.0 deprecates `forgejo docs` and moves CLI errors from stdout to
    stderr.
  - Forgejo 14.0 errors on extra non-flag CLI arguments for subcommands that
    accept only flags.
- Check whether SSH is enabled through Forgejo-managed `authorized_keys`.
  Forgejo 14.0 refuses to start if the managed file contains unexpected keys
  unless `[server].SSH_ALLOW_UNEXPECTED_AUTHORIZED_KEYS = true` is set. Prefer
  resolving unexpected keys instead of disabling the check.
- Check whether users rely on forked `.profile` repositories to populate public
  profile pages. Forgejo 14.0 treats forked `.profile` repositories as standard
  repositories and no longer uses them for profile content.
- Check whether instance policy or documentation mentions the removed squash
  merge trailer behavior. Forgejo 15.0 removes
  `repository.pull-request.ADD_CO_COMMITTER_TRAILERS`.
- Expect users to log in again after Forgejo 15.0 unless the remember-cookie name
  was explicitly pinned back to `gitea_incredible`.
- Plan to run `forgejo doctor avatar-strip-exif` once after upgrade if existing
  uploaded avatars may contain EXIF metadata. New avatar uploads are stripped by
  Forgejo 14.0, and the doctor command handles stored avatars.

## Preflight

Confirm the declared service shape:

```sh
rg -n "codeberg.org/forgejo/forgejo" inventory/services/forgejo.yaml
```

Confirm the Backend VM and current container are reachable:

```sh
scripts/vm-shell forgejo-vm -- systemctl is-active fortress-forgejo-server.service
scripts/vm-shell forgejo-vm -- sudo podman ps --filter name=fortress-forgejo-server
scripts/vm-shell forgejo-vm -- sudo podman exec fortress-forgejo-server forgejo --version
scripts/vm-shell forgejo-vm -- git --version
```

Inspect live config location and relevant settings:

```sh
scripts/vm-shell forgejo-vm -- sudo podman exec fortress-forgejo-server sh -lc 'find /data -path "*app.ini" -print'
scripts/vm-shell forgejo-vm -- sudo podman exec fortress-forgejo-server sh -lc 'grep -R "DISABLE_QUERY_AUTH_TOKEN\|TEST_CONFLICTING_PATCHES_WITH_GIT_APPLY\|CSRF_COOKIE_HTTP_ONLY\|ADD_CO_COMMITTER_TRAILERS\|SSH_ALLOW_UNEXPECTED_AUTHORIZED_KEYS\|COOKIE_REMEMBER_NAME" /data/gitea/conf /data/forgejo/conf 2>/dev/null || true'
```

Run Forgejo's pre-upgrade checks:

```sh
scripts/vm-shell forgejo-vm -- sudo podman exec --user git fortress-forgejo-server forgejo doctor check --all --log-file /tmp/doctor-before-upgrade.log
scripts/vm-shell forgejo-vm -- sudo podman exec --user git fortress-forgejo-server forgejo manager flush-queues --timeout 5m
```

If `flush-queues` times out, repeat with a larger timeout. Do not continue while
queues still contain work; Forgejo notes that serialized queue data is not
guaranteed to be backward compatible between versions.

## Backup Gate

Take a consistent backup before changing the image tag.

Preferred backup: stop Forgejo, snapshot or back up the `forgejo-vm` disk, then
start Forgejo again only if the maintenance is paused. This service stores its
data under the Service-owned `/srv/services/forgejo/data` path mounted into the
container at `/data`; the VM snapshot is the simplest consistent unit.

Minimum application-level backup during the same maintenance window:

```sh
scripts/vm-shell forgejo-vm -- sudo systemctl stop fortress-forgejo-server.service
scripts/vm-shell forgejo-vm -- sudo podman run --rm -v /srv/services/forgejo/data:/data -v /srv/services/forgejo:/backup codeberg.org/forgejo/forgejo:11.0.1 forgejo dump --file /backup/forgejo-pre-15.0.3.zip
```

Prefer the VM snapshot over relying only on `forgejo dump`. Upstream documents
known limitations around SQL dumps inside the dump archive for some database
backends.

## Inventory Change

Change only the Forgejo image tag:

```diff
-      image: codeberg.org/forgejo/forgejo:11.0.1
+      image: codeberg.org/forgejo/forgejo:15.0.3
```

Run local validation before touching production:

```sh
just test
```

## Apply

Run the existing Service Update workflow in the maintenance window:

```sh
just service-update forgejo
```

At the confirmation gate, type:

```text
update forgejo
```

Service Update runs Service Deploy first, restarts the fortress-owned Forgejo
unit, and verifies `fortress-forgejo-server.service` is active. Forgejo performs
database migrations during startup.

## Verify

Check service and container state:

```sh
scripts/vm-shell forgejo-vm -- systemctl is-active fortress-forgejo-server.service
scripts/vm-shell forgejo-vm -- sudo podman exec fortress-forgejo-server forgejo --version
scripts/vm-shell forgejo-vm -- sudo journalctl -u fortress-forgejo-server.service --since "30 min ago" --no-pager
```

Run Forgejo doctor after migrations:

```sh
scripts/vm-shell forgejo-vm -- sudo podman exec --user git fortress-forgejo-server forgejo doctor check --all --log-file /tmp/doctor-after-upgrade.log
```

Manually verify:

- `https://git.fearn.cloud/` loads through Ingress.
- Admin login works.
- Repository list and one private repository load.
- Git clone over HTTPS works.
- Git clone or push over SSH works on port `2222`.
- If Actions are enabled, at least one representative workflow parses and either
  runs or fails for an expected workflow reason.
- If package/container registry usage matters, pull or browse one known package.
- API tokens used by automation still have the required scopes.

After verification, commit the Inventory change and this runbook together so the
declared runtime version and the operator procedure stay aligned.

## Rollback

Prefer to restore the pre-upgrade VM snapshot. Database migrations can make image
downgrade unsafe; Forgejo stores database version state and refuses downgrades
that would damage data.

Only revert the image tag without restoring data if Forgejo did not complete
startup migrations. If there is any doubt, restore the VM snapshot.
