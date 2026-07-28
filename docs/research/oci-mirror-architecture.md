# OCI Mirror implementation and multi-upstream routing

## Decision question

Can one service behind `oci.fearn.cloud` provide an on-demand cache for the
approved public upstreams, using the explicit image shape
`oci.fearn.cloud/<upstream>/<repository>:<tag>`? The intended first release is
a dedicated VM, TLS at the service edge, host-disk storage, no registry-client
authentication, and Prometheus-compatible monitoring. The cache must continue
serving already present artifacts during an upstream outage; a miss may fail.

The approved upstream aliases are `docker.io`, `ghcr.io`, `lscr.io`,
`codeberg.org`, `registry.gitlab.com`, `registry.k8s.io`, `quay.io`,
`public.ecr.aws`, `mcr.microsoft.com`, and `gcr.io`.

## Findings

### CNCF Distribution Registry does not natively meet the routing requirement

Distribution's pull-through-cache configuration has exactly one required
`proxy.remoteurl`. Its own mirror recipe describes this as a mirror of a
single upstream, and says a Docker daemon mirror URL must be the domain root,
not a path. That rules out a single native Distribution process that interprets
the first repository component as one of ten upstreams. One Distribution cache
per upstream plus an additional path-rewriting reverse proxy could be made to
work, but it creates ten independently configured cache processes and makes
routing correctness an ingress concern rather than a registry concern.

Distribution does have filesystem storage, a health section, and stale-content
cleanup in pull-through mode when deletion is enabled. Those features do not
remove its single-upstream constraint. [Distribution configuration reference](https://distribution.github.io/distribution/about/configuration/)
[Distribution pull-through-cache recipe](https://distribution.github.io/distribution/recipes/mirror/)

### Harbor can route through proxy-cache projects, but is a larger fit

Harbor's unit of proxying is a proxy-cache *project*, connected to one registry
endpoint. A client pulls it as
`<harbor>/<proxy-project>/<repository>:<tag>`, so one project per upstream
would directly produce the desired reference shape: for example,
`oci.fearn.cloud/ghcr.io/owner/image:tag`. Harbor fetches a missing image from
the target registry, serves cached material if the target is unreachable, and
does not allow pushes to proxy-cache projects. It also provides a per-project
storage quota control.

However, its documented proxy-cache provider list does not cover the whole
approved set by name (notably `lscr.io`, `codeberg.org`, and
`registry.gitlab.com`). Some might be usable through Harbor's generic Docker
Registry provider, but that needs a compatibility proof rather than an
assumption. Harbor also provisions and operates considerably more than the
cache-only single-service needed here. Its documented default policy is
seven-day tag retention, not a global fixed-capacity LRU cache.
[Harbor proxy cache](https://goharbor.io/docs/main/administration/configure-proxy-cache/)
[Harbor registry endpoints](https://goharbor.io/docs/main/administration/configuring-replication/create-replication-endpoints/)
[Harbor project storage-quota option](https://goharbor.io/cli-docs/cli-docs/harbor-project-create/)

### Zot natively maps several on-demand upstreams to local prefixes

Zot's `extensions.sync.registries` configuration accepts multiple registry
stanzas. Each stanza has its own upstream URL, remote content prefix, local
destination prefix, and `onDemand` option. The official multi-registry example
maps separate Docker and Kubernetes sources to distinct local prefixes and
pulls those prefixes on demand. One stanza for each allowlisted upstream can
therefore make the prefix an explicit routing key without a separate proxy
layer:

| Consumer reference | Zot local destination | Upstream in its own stanza |
| --- | --- | --- |
| `oci.fearn.cloud/docker.io/library/alpine:tag` | `/docker.io` | Docker Hub |
| `oci.fearn.cloud/ghcr.io/<owner>/<image>:tag` | `/ghcr.io` | GHCR |
| `oci.fearn.cloud/registry.k8s.io/<image>:tag` | `/registry.k8s.io` | Kubernetes registry |

The same pattern applies to all ten aliases. Multiple URLs within a Zot stanza
are failover addresses for that one upstream, not ten-registry routing; keep
the ten upstreams as ten stanzas. Use the full Zot image so that the `sync` and
`metrics` extensions are available. Zot exposes Prometheus metrics at a
configurable `/metrics` endpoint, and the OCI `/v2/` endpoint is suitable for
basic registry readiness probing. TLS may terminate at the existing ingress
or at Zot; the selected deployment shape should make the health endpoint and
metrics endpoint reachable only as intended.
[Zot mirroring and on-demand synchronization](https://zotregistry.dev/v2.0.2/articles/mirroring/)
[Zot metrics endpoint](https://zotregistry.dev/v2.1.0/developer-guide/api-user-guide/)
[Zot full-image extensions](https://zotregistry.dev/v2.1.11/admin-guide/admin-getting-started/)

## Constraint: fixed-size LRU is not a Zot feature

Zot documents automatic garbage collection of orphaned blobs and retention
rules based on tag age or pull/push count. Its primary documentation does not
describe a global host-disk capacity, byte quota, or LRU eviction policy for
on-demand synchronized content. Therefore Zot satisfies the routing and
monitoring requirements but cannot truthfully satisfy the map's exact
fixed-size-LRU requirement by configuration alone.

Do not silently translate this to tag-age retention: it differs materially
from LRU and may delete a recovery-relevant image that remains within the
desired capacity. The implementation plan needs a follow-up decision between
(a) an external hard disk quota plus a controlled/monitored pruning procedure,
(b) a different registry product that can prove byte-bounded LRU behavior, or
(c) relaxing the requirement to a stated, tested retention policy. Until that
decision is made, alerting on filesystem headroom is a necessary safeguard,
not a solution to capacity enforcement.
[Zot storage and garbage collection](https://zotregistry.dev/v2.1.18/articles/storage/)
[Zot retention policies](https://zotregistry.dev/v2.1.0/articles/retention/)

## Recommendation

Choose **Zot (full image) with one on-demand sync stanza per approved upstream
and the upstream alias as the local destination prefix**. It is the smallest
documented implementation that natively makes
`oci.fearn.cloud/<upstream>/<repository>:<tag>` a multi-upstream pull-through
cache routing contract. It needs no custom path-rewriting proxy and fits a
dedicated, disposable host-disk VM.

This recommendation is conditional: it does **not** decide or implement the
fixed-size LRU rule. Resolve that capacity/eviction gap before an
implementation ticket is accepted. Also prove the final configuration against
representative anonymous pulls from every one of the ten endpoints, especially
Docker Hub's `library/` namespace and the less-standard `lscr.io` and
`codeberg.org` endpoints.

## Sources

- [CNCF Distribution: configuring a registry](https://distribution.github.io/distribution/about/configuration/)
- [CNCF Distribution: registry as a pull-through cache](https://distribution.github.io/distribution/recipes/mirror/)
- [Harbor: configure proxy cache](https://goharbor.io/docs/main/administration/configure-proxy-cache/)
- [Harbor: create registry endpoints](https://goharbor.io/docs/main/administration/configuring-replication/create-replication-endpoints/)
- [Harbor CLI: proxy project storage limit](https://goharbor.io/cli-docs/cli-docs/harbor-project-create/)
- [Zot: mirroring registries](https://zotregistry.dev/v2.0.2/articles/mirroring/)
- [Zot: API and Prometheus metrics](https://zotregistry.dev/v2.1.0/developer-guide/api-user-guide/)
- [Zot: full-image extensions](https://zotregistry.dev/v2.1.11/admin-guide/admin-getting-started/)
- [Zot: storage and garbage collection](https://zotregistry.dev/v2.1.18/articles/storage/)
- [Zot: retention policies](https://zotregistry.dev/v2.1.0/articles/retention/)
