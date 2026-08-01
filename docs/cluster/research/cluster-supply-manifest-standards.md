> Historical Canon source — migrated to Rite on 2026-07-31 from `docs/research/cluster-supply-manifest-standards.md`. See [migration status](../README.md).

# Cluster Supply Manifest standards

Research date: 2026-07-28. Sources are limited to standards, specifications,
official project documentation, and first-party source repositories.

## Executive finding

There is no established standard that directly represents Canon's required
combination: a complete, revision-bound inventory of recovery inputs delivered
through both OCI and HTTPS endpoints, with endpoint configuration kept outside
the inventory.

Canon should define a small, schema-versioned **Cluster Supply Manifest** and
reuse the standard **OCI Content Descriptor** fields for every artifact:
`mediaType`, `digest`, and `size`. OCI explicitly recommends embedding
descriptors in other formats to securely reference external content; the
descriptor supplies a content type, content identifier, and byte size, and
requires SHA-256 support. Retrieved bytes should be checked first for size and
then digest. ([OCI Content Descriptors](https://github.com/opencontainers/image-spec/blob/v1.1.1/descriptor.md))

The manifest should add only the information OCI does not provide: a stable
logical name, the recovery phase and consumer that make completeness auditable,
and a discriminated delivery locator for an externally configured OCI or HTTPS
endpoint. It should not embed live endpoint base URLs, credentials, registry
implementation names, backup topology, tags as identity, an SBOM, or build
provenance.

YAML is acceptable as a human-authoring syntax, but it is not the source of a
standard solution. Use YAML 1.2 constrained to the JSON data model, reject
duplicate keys and aliases, and validate the parsed document against JSON
Schema. If Canon later signs canonical manifest content rather than relying on
the containing Git revision, JSON or another explicitly canonical serialization
should be selected at that point.

## The standards solve different problems

| Concern | Appropriate standard or mechanism | What it does not establish |
|---|---|---|
| Inventory of Canon recovery inputs | Canon Cluster Supply Manifest | Artifact authenticity, mirror operation, or internal software composition |
| Immutable OCI identity and transport | OCI descriptor plus OCI Image and Distribution Specifications | Mixed OCI/HTTPS inventory, recovery phase, or provider-independent endpoint binding |
| Offline OCI export/import | OCI Image Layout | HTTPS files, a recovery plan, or assurance that every needed input was selected |
| HTTPS update trust | TUF repository metadata and client workflow | Native OCI repository semantics or Canon's cross-transport completeness model |
| Software composition | SPDX or CycloneDX SBOM | Exact deployable recovery closure and offline readiness |
| Claim envelope | in-toto Statement | The meaning or truth of the claim |
| Build origin | SLSA provenance predicate in an in-toto Statement | Artifact availability, mirroring, or recovery inventory |
| Air-gap packaging/mirroring | Zarf or `oc-mirror` | A provider-neutral Canon contract |

The distinction matters operationally. A digest lock identifies exact bytes. An
SBOM describes software composition. Provenance describes how an output was
produced. TUF authenticates a repository view and defends update clients from
rollback and freeze attacks. OCI Distribution retrieves content. A mirror or
air-gap bundle moves and retains it. None of those facts alone proves that the
set contains every input used by Canon's recovery procedure.

## OCI: reuse the descriptor, not the whole format

An OCI descriptor's required fields are exactly the common integrity metadata
Canon needs: `mediaType`, `digest`, and `size`; optional fields include URLs,
annotations, platform, and artifact type. The digest is a content identifier,
and consumers are expected to recalculate it after checking size. SHA-256 is the
mandatory digest algorithm. ([OCI Content Descriptors](https://github.com/opencontainers/image-spec/blob/v1.1.1/descriptor.md))

For an OCI-delivered item, the descriptor digest identifies the image manifest
or image index, while the repository name supplies the namespace needed by the
registry API. Tags are mutable pointers and may be retained only as display or
acquisition hints. The Distribution Specification standardizes manifest and
blob retrieval and is content-type agnostic. ([OCI Distribution Specification](https://github.com/opencontainers/distribution-spec/blob/v1.1.1/spec.md))

OCI 1.1 also supplies a standard way to associate metadata with an artifact.
An OCI manifest's optional `subject` descriptor associates it with another
manifest, and the Distribution referrers API lists manifests whose subject is a
given digest, optionally filtered by `artifactType`. This is the correct place
to publish OCI-hosted signatures, SBOMs, or provenance, when Canon later defines
which of those are required. It does not make those attachments part of the
base inventory unless policy explicitly requires and verifies them.
([OCI manifest `subject`](https://github.com/opencontainers/image-spec/blob/v1.1.1/manifest.md),
[OCI referrers API](https://github.com/opencontainers/distribution-spec/blob/v1.1.1/spec.md#listing-referrers))

An OCI Image Index can enumerate multiple descriptors, but its semantics are an
entry point to manifests in a registry or OCI Image Layout. Canon would still
need private conventions for HTTPS paths, endpoint indirection, consumers, and
recovery phases. It is therefore a poor canonical mixed-transport manifest.

OCI Image Layout is, however, the established portable form for an offline OCI
export: `oci-layout`, `index.json`, and content-addressed `blobs/<algorithm>/<digest>`.
The bytes at each blob path must match its digest. Use it when a mirror backup
or transfer archive claims OCI-layout compatibility, and validate it as a
backup/export format rather than treating it as Canon's supply declaration.
([OCI Image Layout](https://github.com/opencontainers/image-spec/blob/v1.1.1/image-layout.md))

## TUF: closest for HTTPS, but a larger trust system

TUF targets metadata is the closest existing record format for HTTPS artifacts.
It maps a repository-relative target path to an exact byte `length`, one or
more `hashes`, and an optional opaque `custom` object. A TUF client downloads no
more than the declared length and verifies the target against its trusted
metadata. ([TUF Specification 1.0.35, targets metadata and fetch workflow](https://theupdateframework.github.io/specification/v1.0.35/))

Using TUF means adopting more than a target list. Its root, targets, snapshot,
and timestamp roles, threshold signatures, key rotation, expiry checks,
consistent snapshots, and client state defend against wrong-content,
rollback, freeze, and mix-and-match attacks. TUF also permits full or partial
mirrors, but treats separate repositories as separate roots of trust.
([TUF roles and repository](https://theupdateframework.github.io/specification/v1.0.35/#the-repository),
[TUF client workflow](https://theupdateframework.github.io/specification/v1.0.35/#detailed-client-workflow))

That security is valuable only if Canon needs that threat model and is prepared
to operate its keys and metadata lifecycle. Expired timestamp, snapshot, or
targets metadata is rejected as a potential freeze attack, which is an important
constraint for long-disconnected disaster recovery. TUF should therefore be a
separate decision: it can secure the HTTPS artifact repository while the
Cluster Supply Manifest remains the cross-transport inventory. Encoding OCI
items in TUF's opaque `custom` field would merely create a private schema inside
TUF and would not remove the need for Canon's model.

## SPDX and CycloneDX: attach SBOMs; do not substitute them

SPDX 3.0 can represent packages such as archives, container images, collections,
and Git snapshots. Its package model has download locations, package URLs,
content identifiers, integrity methods, and relationships to distribution
artifacts. ([SPDX 3.0.1 Package](https://spdx.github.io/spdx-spec/v3.0.1/model/Software/Classes/Package/),
[SPDX 3.0 changes for distribution artifacts](https://spdx.github.io/using/diffs-from-previous-editions/#package-file-name))

CycloneDX 1.7 likewise models components, hashes, package URLs, dependency
relationships, and external references; a `distribution` external reference
may carry a URL and hashes. Its BOM lifecycle vocabulary also includes
operations and discovery inventories. ([CycloneDX 1.7 JSON reference](https://cyclonedx.org/docs/1.7/json/),
[CycloneDX external resource links](https://cyclonedx.org/use-cases/external-resource-links/))

Both are useful evidence attached to an artifact, especially for vulnerability,
license, and dependency analysis. Neither promises that every byte needed by a
specific recovery procedure is present at Canon's configured endpoints. Their
download-location models also do not supply Canon's desired indirection between
a logical endpoint and Rite's current serving implementation. Requiring either
as the manifest would conflate an SBOM with a deployment lock and still require
Canon extensions for the central contract.

## in-toto and SLSA: claims and provenance, not inventory

An in-toto Statement binds a typed predicate to immutable subjects identified
by digest. It intentionally leaves the predicate's semantics to its declared
`predicateType`. ([in-toto Statement v1](https://github.com/in-toto/attestation/blob/v1.2.0/spec/v1/statement.md))

SLSA provenance is one such predicate family. It records verifiable information
about where, when, and how an artifact was produced; build provenance traces a
build output back through its build process and source inputs. It does not say
that the artifact is mirrored, retrievable offline, or needed by a recovery
procedure. ([SLSA 1.2 provenance](https://slsa.dev/spec/v1.2/provenance),
[SLSA 1.2 build provenance](https://slsa.dev/spec/v1.2/build-provenance))

Consequently, a free-form required "upstream provenance" field would be weak
and ambiguous. Canon should either leave provenance out of the base schema or
later require typed, digest-bound attestations under a separately defined trust
policy. OCI referrers are a natural distribution mechanism for such evidence
when the subject is OCI-hosted.

## Air-gap tools are precedents, not general standards

Zarf packages are single disconnected-deployment archives defined by
`zarf.yaml`; their components may bring images, files, repositories, manifests,
charts, and executable actions. Zarf signs the package's internal `zarf.yaml`,
which contains checksums for package contents, and can represent images with an
OCI layout. ([Zarf packages](https://docs.zarf.dev/ref/packages/),
[Zarf components](https://docs.zarf.dev/ref/components/),
[Zarf package signing](https://docs.zarf.dev/ref/package-signing/))

That is evidence that a mixed air-gap closure benefits from names, hashes, and
an executable validation path. It is not an appropriate Canon contract because
it couples selection, packaging, deployment actions, cluster mutation, and a
specific tool.

`oc-mirror` v2's ImageSetConfiguration is declarative selection input for
OpenShift releases, operator catalogs, extra images, and Helm content. Its
mirror-to-disk workflow creates tar archives for later disk-to-registry import,
and it can generate configurations pinned to SHA-256 digests. It is an
OpenShift-specific mirroring workflow rather than a general inventory of the
exact output closure, and it does not cover Canon's arbitrary HTTPS recovery
files. ([`oc-mirror` v2 repository and workflow](https://github.com/openshift/oc-mirror))

Rite may use tools with these patterns internally. Canon's contract should not
require either tool.

## Recommended Canon v1 data model

Keep the model deliberately small. The containing Git tree already binds the
manifest to the exact Cluster Desired State revision; do not put that same
commit hash inside the file and create a self-reference problem.

```yaml
apiVersion: canon.fearn.cloud/v1alpha1
kind: ClusterSupplyManifest
metadata:
  name: homelab
items:
  - name: k3s-server-linux-amd64
    requiredBy:
      phase: cluster-bootstrap
      consumer: k3s-install
    source:
      type: https
      endpoint: artifacts
      path: k3s/v1.XX.Y+k3s1/k3s
    descriptor:
      mediaType: application/vnd.canon.executable
      digest: sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef
      size: 73400320
    platform:
      os: linux
      architecture: amd64

  - name: flux-source-controller
    requiredBy:
      phase: gitops-bootstrap
      consumer: flux
    source:
      type: oci
      endpoint: images
      repository: fluxcd/source-controller
    descriptor:
      mediaType: application/vnd.oci.image.manifest.v1+json
      digest: sha256:abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789
      size: 1987
    platform:
      os: linux
      architecture: amd64
```

The normative fields should be:

- `apiVersion`: exact Canon schema version.
- `kind`: exactly `ClusterSupplyManifest`.
- `metadata.name`: stable name of the Cluster supply set.
- `items`: non-empty array.
- `items[].name`: stable logical identifier, unique within the manifest.
- `items[].requiredBy.phase`: controlled recovery-phase identifier.
- `items[].requiredBy.consumer`: controlled consumer or procedure identifier.
- `items[].source`: a discriminated union:
  - `type: oci`, logical `endpoint`, and registry-relative `repository`; or
  - `type: https`, logical `endpoint`, and safe relative `path`.
- `items[].descriptor`: required OCI-compatible `mediaType`, `digest`, and
  non-negative integer `size`. Canon v1 should require
  `sha256:<64 lowercase hexadecimal characters>` even though OCI permits other
  algorithms.
- `items[].platform`: optional `os`, `architecture`, and `variant`; require it
  where the recovery consumer selects a platform-specific object.

Endpoint configuration outside the manifest maps `images` to an OCI registry
host and `artifacts` to an HTTPS base URL, along with TLS and authentication
material. The names can be schema-controlled rather than arbitrary if Canon
will always expose exactly those two endpoint classes.

Do not require provenance or signature identity in v1 without first defining a
trust policy. If that policy is adopted, add a typed `evidenceRequirements`
extension that names accepted predicate or artifact media types and verification
identities; do not use free-form strings. Human-readable versions, upstream
URLs, and tags may be non-authoritative acquisition annotations, but the
descriptor digest remains the sole content identity.

## Validation and readiness contract

Validation has four layers; schema validation alone cannot prove offline
readiness.

1. **Parse and schema-check.** Use a YAML 1.2 parser in JSON-compatible mode;
   reject duplicate keys, aliases, custom tags, non-string mapping keys, and
   non-JSON scalar values. Validate against a versioned JSON Schema with
   `additionalProperties: false`. Require unique item names, known phases and
   consumers, recognized logical endpoint names, valid media types, exact
   lowercase SHA-256 syntax, and non-negative sizes. Reject absolute HTTPS
   paths, `..` segments, backslashes, queries, fragments, and percent-encoded
   path traversal.
2. **Verify OCI closure.** Fetch the named repository manifest or index by
   digest, never by tag. Require its digest and byte size to match the
   descriptor, recursively fetch and verify every referenced manifest, config,
   and layer descriptor, and require the selected platform to exist when an
   index is used. If evidence is mandatory, retrieve and verify the required
   referrers rather than assuming their presence.
3. **Verify HTTPS bytes.** `HEAD` may provide an early length check, but the
   readiness test must `GET` every object, enforce the declared maximum and
   exact byte count, calculate SHA-256, and perform any format-specific sanity
   check. A successful TLS response is not artifact verification.
4. **Prove completeness.** Compare the manifest against all artifact references
   produced by rendering the selected Cluster Desired State and every recovery
   phase/consumer. Then execute the recovery or a supply-only rehearsal with WAN
   egress denied. An SBOM, registry catalog, or list of tags cannot prove this
   closure because scripts, dynamically selected images, installers, OS images,
   and operator tools can introduce inputs outside those inventories.

Run the same byte-level checks against restored backups or alternate serving
paths. For OCI backups exported as OCI Image Layout, additionally validate the
layout structure and every content-addressed blob. This turns "a backup exists"
into evidence that it can reconstruct the supply Canon actually consumes.

## Decision

Adopt a Canon-owned, schema-versioned YAML manifest with a strict JSON data
model and OCI descriptor semantics. Keep endpoint bindings external. Use OCI
Distribution for OCI retrieval and OCI Image Layout where applicable for mirror
exports. Treat SPDX/CycloneDX, in-toto/SLSA, and TUF as complementary evidence
or trust layers selected by later policy decisions, not as substitutes for the
Cluster Supply Manifest.
