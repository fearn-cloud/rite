# OCI Mirror lifecycle and recovery

Use this runbook to verify or recover the disposable Zot cache behind
`oci.fearn.cloud`. The OCI Mirror's configuration is durable Inventory; its
cache contents are not durable state.

## Acceptance after deploy, update, or restart

For a new deployment, run `just service-deploy oci-mirror`. For a routine
image update, run `just service-update oci-mirror`. After either workflow, and
after `systemctl restart fortress-oci-mirror-zot` on `oci-mirror-vm`, run:

```sh
scripts/oci-mirror-acceptance
```

Then run `just instrumentation-converge` to refresh the generated
Observability artifacts before using the View or alerts as evidence.

The procedure proves all of the following through Ingress:

- `https://oci.fearn.cloud/v2/` answers successfully.
- Zot UI is visible at `https://oci.fearn.cloud/`.
- Zot metrics are reachable at `/metrics` for the declared Instrumentation
  target.
- Known pulls through `oci.fearn.cloud` work for every approved upstream.

Then open the OCI Mirror `oci_mirror` Observability View in Grafana.
Confirm both the registry API and metrics targets are up, the cache-storage and
VM disk-free panels have samples, and no `OciMirror*` alert is firing. This is
the post-update-health evidence.

## Retention proof

The checked-in Zot configuration keeps the five most recently pulled tags per
repository and runs garbage collection every 24 hours. To prove the lifecycle
against one representative repository, pull these six known tags in order
through the mirror, waiting for each pull to complete:

```sh
for tag in 14 14-alpine 15 15-alpine 16 16-alpine; do
  skopeo copy --src-no-creds "docker://oci.fearn.cloud/docker.io/library/postgres:${tag}" "dir:/tmp/oci-mirror-retention/${tag}"
done
curl --fail --silent "https://oci.fearn.cloud/v2/docker.io/library/postgres/tags/list" | jq
```

After the configured retention delay and the next scheduled garbage collection,
inspect the Zot UI or the tags endpoint to confirm only the five most recently
pulled tags remain. The oldest tag, `14`, is the evicted-tag candidate.

Temporarily deny only `oci-mirror-vm` egress to Docker Hub, then request the
evicted `14` tag through `oci.fearn.cloud`; it must fail, proving Zot does not
serve it from cache. Restore the approved upstream egress and repeat the pull.
Its successful pull is the upstream refill evidence; recheck the tag list to
confirm it was cached again. Do not run this proof against a tag whose eviction
has not been observed. Existing cached artifacts may remain usable while the
upstream is unavailable.

## Cold-cache recovery

For cold-cache reprovisioning, provision or restore the VM from its declared
Inventory, then run `just service-deploy oci-mirror` and
`just instrumentation-converge`. Do not restore `/srv/services/oci-mirror/data`:
the cache is disposable. Run `scripts/oci-mirror-acceptance`, review the Zot
UI, and confirm the Grafana health and capacity signals before returning the
Mirror to service. The first successful known pull is expected to refill from
its approved upstream.

## Alerts and response

The generated Observability rules provide API/post-update health,
disk-headroom, disk-full/write-failure risk, and failed-pull signals:

- `OciMirrorApiUnavailable`: check the systemd unit and Ingress, then rerun
  the acceptance script after repair.
- `OciMirrorDiskSpaceLow`: examine cache growth and retention; plan a
  cold-cache reprovision if capacity cannot be recovered safely.
- `OciMirrorDiskFull`: Zot writes can fail. Stop relying on new cache fills,
  reprovision the disposable cache, and run the cold-cache procedure.
- `OciMirrorFailedPulls`: Zot records failed pull responses, including a cache
  write that makes a pull fail. Correlate it with `OciMirrorDiskFull` and the
  Zot logs to distinguish disk-full/write failure from an unavailable upstream.

## Rollback

If a deploy or update fails its acceptance procedure, restore the previous
pinned image and configuration from the prior committed Inventory revision,
then run `just service-deploy oci-mirror` followed by
`just instrumentation-converge` and `scripts/oci-mirror-acceptance`. Do not attempt to roll back cache contents or
treat cache contents as durable state; the safe rollback contract is the
previous pinned image and configuration plus an empty or refilled cache.
