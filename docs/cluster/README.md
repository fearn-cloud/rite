# Cluster context

Rite's Cluster module is the continuation of the historical [Canon repository](https://git.fearn.cloud/fearn-cloud/canon). Canon's domain language, adopted decisions, and primary research are preserved here as a historical migration, while all new Cluster planning and implementation happens in Rite.

## Authority boundary

Rite provides one Operator interface, plan/execution/evidence/diagnostic model, and Forgejo desired-state and durable-evidence host. The module boundary remains strict:

- The Cluster module owns Cluster Desired State, Cluster Host Requirements, Cluster Supply Manifests, K3s bootstrap and GitOps, recovery sequence, workload restoration, and Cluster acceptance.
- The substrate module owns Substrate Inventory, provider-specific VM placement and lifecycle, the External Recovery Substrate, and Cluster Host Readiness Evidence.
- No fact is authoritative in both declarations. Cluster code consumes a small internal substrate interface; it must not traverse provider-specific substrate implementation or raw Substrate Inventory.
- No Cluster is required to recover itself, another Cluster, or the External Recovery Substrate.

The historical cross-repository Handoff Record is superseded: a shared Workflow Run will correlate substrate attestations, Cluster revisions, recovery artifacts, and acceptance evidence. A separate interchange record needs a later, independent justification.

## Migrated material

The migrated [glossary](../../CONTEXT.md), [adopted ADR](../adr/0046-canon-cluster-authority-is-separate-from-substrate-authority.md), and [research](research/) retain Canon's terminology and conclusions. They are historical source material, not an implementation promise. Their source is Canon's working-tree snapshot on 2026-07-31; the last published Canon revision before this migration was [`30e916421b5642f3b972d281308a9a86f6ef883c`](https://git.fearn.cloud/fearn-cloud/canon/src/commit/30e916421b5642f3b972d281308a9a86f6ef883c). Each migrated Markdown file begins with a source-status note.

## Planning continuation

Existing Canon issues remain historical references and are not mechanically rewritten. New Cluster work is planned and tracked in [Rite](https://git.fearn.cloud/fearn-cloud/rite/issues); issue [#250](https://git.fearn.cloud/fearn-cloud/rite/issues/250) establishes this migration. Before Canon becomes read-only, its landing page must point readers here and its active planning map must link to the corresponding Rite issues.

## Validation

Run `scripts/validate-cluster-docs`. It checks local Markdown targets within this context and rejects direct `fortress_cluster` imports of raw substrate implementation packages. This preserves the declared dependency direction without adding Cluster runtime behavior.
