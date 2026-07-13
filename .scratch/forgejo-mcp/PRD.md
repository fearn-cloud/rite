# Forgejo MCP Service

## Goal

Deploy a mature containerized Forgejo MCP server as a first-class Rite Service so authorized agents and operator clients can interact with Forgejo through MCP.

## Decisions

- Runtime placement: new `forgejo-mcp` Service on `forgejo-vm`.
- Upstream implementation: `goern/forgejo-mcp`, pinned to an immutable release tag such as `codeberg.org/goern/forgejo-mcp:v2.30.2`.
- Endpoint: separate hostname `mcp.git.fearn.cloud`.
- Exposure: internal ingress route with the same client reachability boundary as Forgejo itself.
- Forgejo target URL: `https://git.fearn.cloud`.
- Auth model: no global Forgejo token in the Service. Clients must send their own Forgejo token through the MCP HTTP `Authorization` header.
- Permission model: the MCP server may expose the full upstream tool surface; read/write authority comes from each client's Forgejo token scopes.

## Research

See [containerized-mcp-options.md](research/containerized-mcp-options.md).
See [mcp-exposure-protocol-audit.md](research/mcp-exposure-protocol-audit.md).

## Non-goals

- Do not run MCP on the Forgejo Runner VM.
- Do not make the Forgejo Runner VM a deployment or Forgejo API principal.
- Do not build a custom MCP server unless live validation shows the selected upstream cannot work.
- Do not bake a broad service-owned Forgejo token into the container.

## Open implementation gates

- Confirm `forgejo-vm` can run the selected `linux/amd64` image.
- Confirm `goern/forgejo-mcp` fails safely when no per-request `Authorization` header is supplied.
- Confirm Caddy preserves the MCP Streamable HTTP method/header/streaming behavior required by `/mcp`.
- Run live smoke tests against Forgejo 15.0.3 with read-only and write-scoped tokens.
- Decide whether the placement/auth decision deserves an ADR after the implementation details are known.
