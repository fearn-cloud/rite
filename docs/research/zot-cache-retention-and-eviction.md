\ # Zot on-demand cache retention and eviction

## Question

Can Zot configure an on-demand OCI mirror to evict cached content without
continuing operator intervention, specifically through a byte quota, LRU,
pull-count or tag-age retention, garbage collection, or disk-pressure policy?

## Conclusion

**Partly.** Zot can automatically prune an on-demand cache using configured,
per-repository *tag retention* plus garbage collection. This can avoid routine
manual cleanup. It cannot configure a total byte quota, a global LRU cache, or
automatic eviction when the backing filesystem reaches a free-space threshold.
Consequently, Zot alone cannot guarantee that a 250 GiB cache volume will not
fill, even when retention rules are enabled.

## What can be configured

- An upstream sync registry with `onDemand: true` fetches an image that is
  absent locally when it is requested. Omitting `content` makes this an
  on-demand-only cache rather than a periodically populated mirror. A `content`
  list can instead restrict which repository prefixes and tags may be fetched.
  [Official sync configuration reference](https://github.com/project-zot/zot/blob/v2.1.18/examples/README.md#sync)

- Retention policies apply by repository glob and tag-pattern regex. A matching
  tag can be retained by `mostRecentlyPulledCount`,
  `mostRecentlyPushedCount`, `pulledWithin`, or `pushedWithin`; rules are ORed.
  This permits a practical policy such as retaining the most recently pulled
  tags and tags used within a chosen window for every mirrored upstream
  namespace. It is tag-based, not byte-based, and is scoped per repository
  policy rather than a cache-wide LRU order.
  [Official retention reference](https://github.com/project-zot/zot/blob/v2.1.18/examples/README.md#retention)

- After retention deletes manifests, Zot's enabled-by-default garbage
  collection reclaims their orphaned blobs. `gcDelay` controls the delayed run
  and `gcInterval` can schedule periodic collection; neither setting chooses
  objects based on volume capacity or filesystem pressure.
  [Official storage and GC documentation](https://zotregistry.dev/v2.1.18/articles/storage/#configuring-garbage-collection)

## What cannot be configured

- Zot's documented storage settings contain no byte capacity, minimum-free-
  space, LRU, eviction, or disk-pressure action. Its `maxRepos` setting is not
  a storage quota: the implementation counts existing repositories and rejects
  a `PUT` which would create a repository beyond that count.
  [Quota implementation](https://github.com/project-zot/zot/blob/v2.1.18/pkg/api/quota.go#L19-L101)

- The named storage `cacheDriver` is metadata used for deduplication; it is not
  an image-cache eviction driver.
  [Official storage configuration reference](https://zotregistry.dev/v2.1.18/articles/storage/#cache-drivers)

- GC removes blobs only after their manifests have first been deleted. It is
  not a pressure-triggered cache cleaner, and it cannot itself select old or
  large cached images to remove.
  [Official storage and GC documentation](https://zotregistry.dev/v2.1.18/articles/storage/#garbage-collection)

## Implication for the OCI Mirror

Use Zot retention plus periodic GC if the goal is to eliminate normal
operator-led pruning. Select a tag policy deliberately (for example, recent
pull count together with a pull-age window), test it with the intended image
mix, and monitor the volume. This is an automated retention policy, not an
ejection contract: it supplies no hard cache-size bound or automatic action at
disk pressure. A requirement for those properties needs a component outside
Zot or a different registry/cache design.

## Sources

- [Zot v2.1.18 configuration examples: retention and sync](https://github.com/project-zot/zot/blob/v2.1.18/examples/README.md)
- [Zot v2.1.18 storage planning](https://zotregistry.dev/v2.1.18/articles/storage/)
- [Zot v2.1.18 repository-count quota implementation](https://github.com/project-zot/zot/blob/v2.1.18/pkg/api/quota.go)
