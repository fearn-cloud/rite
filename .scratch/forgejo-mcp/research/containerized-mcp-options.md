# Containerized Forgejo/Gitea MCP server options

Researched: 2026-07-13

## Question

Which existing containerized MCP server is the best candidate for a mature `forgejo-mcp` Service on `forgejo-vm`, exposed through internal ingress on its own hostname?

## Recommendation

Start with `goern/forgejo-mcp`, pinned to an immutable release tag from `codeberg.org/goern/forgejo-mcp`, unless a live smoke test against Fortress Forgejo 15 exposes incompatibility.

Why:

- It is Forgejo-native, not merely Gitea-compatible.
- It supports `stdio`, legacy `sse`, and streamable HTTP transports, so it fits a network Service behind ingress.
- It has an OCI image published for releases, with documented immutable version tags, cosign signing, SLSA provenance, and a CycloneDX SBOM.
- It supports per-request token identity for HTTP/SSE via the `Authorization` header, which is a better fit for an internally shared MCP endpoint than baking one privileged token into the Service.
- The project is active: the checked GitHub mirror was at `v2.30.2` on 2026-07-13, with many 2.x tags and current README material covering streamable HTTP, multi-tenant auth, image verification, and operational caveats.

Use `gitea/gitea-mcp` as the strongest fallback. It has official Gitea ownership, multi-arch DockerHub images, read-only/tool filtering controls, and HTTP transport, but it is Gitea-first and its public README/configuration still uses `GITEA_*` terminology. For this repo's Forgejo-specific deployment, official Gitea provenance is less important than Forgejo-native behavior and the richer supply-chain/auth story in `goern/forgejo-mcp`.

Do not start with `raohwork/forgejo-mcp` / `ronmi/forgejo-mcp` or `minhcuongvu/forgejo-mcp` for the first mature Service. They are useful references, but weaker on release maturity or deployment fit.

## Deployment posture implied by the recommendation

- Run `goern/forgejo-mcp` as a normal Rite `Service` on `forgejo-vm`.
- Use streamable HTTP transport on an internal VM-local port and expose it through an internal ingress route on its own hostname.
- Prefer per-request `Authorization` tokens over a global Service token. If the chosen MCP client cannot send headers, use the narrowest possible global Forgejo token as an explicit temporary compromise.
- Pin an immutable image tag, not `latest`.
- Add a live acceptance check before considering the choice settled: initialize MCP, call `get_my_user_info`, list repos visible to a read-only token, read one issue, and attempt a deliberately forbidden write with a read-only token.

## Candidate comparison

### `goern/forgejo-mcp`

Primary sources:

- Source mirror inspected: <https://github.com/goern/forgejo-mcp>
- Canonical source/release URLs named by README: <https://codeberg.org/goern/forgejo-mcp> and <https://codeberg.org/goern/forgejo-mcp/releases>
- README container and transport docs: <https://github.com/goern/forgejo-mcp#readme>

Relevant facts:

- The README describes the project as a Forgejo MCP server for issues, pull requests, files, Actions runs, repositories, and related operations.
- It documents an OCI image at `codeberg.org/goern/forgejo-mcp`, immutable `vMAJOR.MINOR.PATCH` tags for production, and `latest` as moving convenience only.
- It documents `stdio`, `sse`, and streamable HTTP transport. Streamable HTTP uses `/mcp`; SSE uses `/sse`.
- It supports a centralized HTTP/SSE process where clients provide their own Forgejo token in the HTTP `Authorization` header. The README accepts both `Authorization: token <token>` and `Authorization: Bearer <token>`.
- The source contains an archived `stateless-http-auth` design/spec explaining per-request token extraction, request-scoped Forgejo clients, and the rule that a supplied request token must not silently fall back to the global token.
- The README documents cosign verification, image signing, SLSA provenance, and CycloneDX SBOM attestation for recent releases.
- The inspected mirror had tag `v2.30.2` at HEAD on 2026-07-13.
- Image caveat: README says the application image is single-arch `linux/amd64`. That is acceptable for the current Proxmox VM shape if `forgejo-vm` is amd64, but it is a real portability constraint.
- License: README points to the repository license; GitHub renders it as GPL-3.0.

Risks and follow-ups:

- The README says `go install codeberg.org/goern/forgejo-mcp/v2@latest` currently does not work because of a `replace` directive. This does not block container deployment but is a maintenance smell to keep an eye on.
- Need a live smoke test against Fortress's Forgejo 15.0.3, especially for repository-scoped tokens and any Forgejo/Gitea API differences in issue dependency, PR, Actions, and attachment tools.
- Need decide whether the ingress/auth layer should require client-provided `Authorization` headers and reject requests without them. The upstream design notes a strict no-global-token mode as a useful follow-up, but not necessarily an existing startup flag.

### `gitea/gitea-mcp`

Primary sources:

- Source: <https://gitea.com/gitea/gitea-mcp>
- Docker image tags surfaced by DockerHub: <https://hub.docker.com/r/gitea/gitea-mcp-server/tags>
- Gitea issue confirming official MCP server release: <https://github.com/go-gitea/gitea/issues/35506>

Relevant facts:

- The Gitea issue tracker states Gitea's official MCP server was released at `https://gitea.com/gitea/gitea-mcp`.
- The README documents `stdio` and HTTP mode, with HTTP clients connecting to `/mcp` and passing `Authorization: Bearer <token>`.
- The command help supports `-transport stdio|http`, `GITEA_ACCESS_TOKEN`, `GITEA_ACCESS_TOKEN_FILE`, `GITEA_HOST`, `GITEA_READONLY`, and `GITEA_TOOLS`.
- It has explicit least-surface controls: read-only mode and a comma-separated tool allowlist.
- The Dockerfile builds a static binary into a distroless Debian 12 nonroot final image and labels the source as `https://gitea.com/gitea/gitea-mcp`.
- Release workflows build and push multi-arch Docker images for `linux/amd64` and `linux/arm64` to DockerHub under `gitea/gitea-mcp-server:<version>` and `latest`; nightly pushes `nightly`.
- Git tags in the inspected source include releases through `v1.3.0`; DockerHub search results showed published version tags including `1.1.0`, `1.0.2`, and earlier, with `nightly` updated more recently.
- License: README says Gitea is MIT; the repo has a `LICENSE` file. Confirm exact MCP repo license during implementation if license matters for redistribution.

Risks and follow-ups:

- It is Gitea-first. It may work with Forgejo through the shared API lineage, but the source and configuration are not Forgejo-native.
- Need verify Forgejo 15.0.3 behavior for all tools we intend to expose, especially APIs that have diverged from Gitea.
- The DockerHub tags observed from search results may lag the source repo tags; implementation should pick from the actual registry available to `forgejo-vm` and pin a digest or immutable version tag.
- It has good local controls (`read-only`, tool allowlist) that `goern/forgejo-mcp` may not expose in the same way. If we need a read-only first deployment with hard tool filtering at the MCP layer, this candidate deserves a live prototype.

### `raohwork/forgejo-mcp` / `ronmi/forgejo-mcp`

Primary sources:

- Source: <https://github.com/raohwork/forgejo-mcp>
- Docker image named by README: <https://hub.docker.com/r/ronmi/forgejo-mcp>

Relevant facts:

- The README documents Docker usage via `ronmi/forgejo-mcp`.
- It supports `stdio` and HTTP server mode.
- HTTP mode exposes both `/sse` and streamable HTTP on `/`.
- It supports single-user mode with a startup token and multi-user mode using `Authorization: Bearer <token>` from each request.
- Feature coverage includes issues, labels, milestones, releases, release attachments, PR viewing, wiki pages, Actions tasks, and issue dependencies.
- The GitHub repo has tags through `v0.0.7`, a Dockerfile, and MPL-2.0 license.

Risks and follow-ups:

- The public image is under a personal DockerHub namespace (`ronmi`) rather than the GitHub org/repo name.
- Release maturity looks lower than `goern/forgejo-mcp` or `gitea/gitea-mcp`.
- The HTTP path for streamable mode is `/`, not `/mcp`, which is workable but less conventional for ingress and client config.
- It may be the same lineage as or a contributor to `goern/forgejo-mcp`; because `goern/forgejo-mcp` has newer release, auth, and supply-chain docs, prefer the latter.

### `minhcuongvu/forgejo-mcp`

Primary sources:

- Source: <https://github.com/minhcuongvu/forgejo-mcp>

Relevant facts:

- The README describes a Forgejo/Gitea MCP server with repository, branch, commit, issue, PR, and file tools.
- It includes a Dockerfile and docker-compose file, but the README's Docker path is to build the image locally.
- The README states the protocol is JSON-RPC 2.0 over stdio.
- It documents suggested token scopes such as `read:repository`, `read:issue`, `write:issue`, and `write:repository`.
- The inspected repo had no tags from `git ls-remote --tags` and only a small commit history.

Risks and follow-ups:

- Not suitable for an internal network Service without adding or fronting an HTTP transport.
- No evident published image/release posture from primary sources.
- Better treated as a code reference than as the deployed implementation.

### `Kunde21/forgejo-mcp`

Primary source:

- Source: <https://github.com/Kunde21/forgejo-mcp>

Relevant facts:

- README says it uses the official Model Context Protocol Go SDK and can target `gitea`, `forgejo`, or `auto` client type.
- It has tags through `v0.2.1`.
- It documents local/OpenCode-style invocation with a `serve` command and environment variables `FORGEJO_REMOTE_URL`, `FORGEJO_AUTH_TOKEN`, and `FORGEJO_CLIENT_TYPE`.

Risks and follow-ups:

- No Dockerfile or Containerfile was present in the inspected source.
- Public footprint is small compared with the leading candidates.
- Not a strong first deployment candidate for a containerized Rite Service.

## Decision gates before implementation

1. Choose whether the first deployment must be per-request token only. If yes, verify `goern/forgejo-mcp` can be run without a global token and fails closed when no `Authorization` header is present, or put that requirement at the ingress/proxy/client layer.
2. Choose initial tool exposure policy. If hard MCP-layer read-only/tool allowlisting is mandatory, prototype `gitea/gitea-mcp` alongside `goern/forgejo-mcp`.
3. Confirm `forgejo-vm` architecture is compatible with `goern/forgejo-mcp`'s single-arch image.
4. Run live smoke tests against Forgejo 15.0.3 with a least-privilege token.
5. Pin the selected image by immutable tag and ideally digest.

