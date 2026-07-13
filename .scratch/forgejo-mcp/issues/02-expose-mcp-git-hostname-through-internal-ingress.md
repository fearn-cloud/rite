# Expose mcp.git.fearn.cloud through internal ingress

Status: done
Category: enhancement

## What to build

Expose the `forgejo-mcp` Service through internal ingress at `mcp.git.fearn.cloud`, targeting the Service's streamable HTTP Published Port. Reachability should match the existing Forgejo client boundary: if a client can access Forgejo, it can access the MCP endpoint.

The route should remain a separate hostname from `git.fearn.cloud` so MCP is visible as its own protocol surface and security boundary.

## Acceptance criteria

- [x] `forgejo-mcp` declares a Service Ingress Route for `mcp.git.fearn.cloud`.
- [x] The route targets the MCP streamable HTTP Published Port on `forgejo-vm`.
- [x] The intended public MCP URL is `https://mcp.git.fearn.cloud/mcp`.
- [x] The route uses the same exposure/auth posture as the existing Forgejo client route unless the implementation discovers a stronger existing convention.
- [x] Ingress preserves `POST`, optional `GET`, `Authorization`, `Accept`, `Content-Type`, `Mcp-Session-Id`, `MCP-Protocol-Version`, `Mcp-Method`, and `Mcp-Name` headers for the upstream.
- [x] Ingress does not buffer `text/event-stream` responses in a way that breaks Streamable HTTP streaming.
- [x] Generated ingress config includes the new hostname and target.
- [x] Generated DNS or route-local directory artifacts are updated if this repo's existing ingress workflow requires them.
- [x] Tests or existing validation prove the route target resolves to the declared Published Port.

## Blocked by

- Declare the forgejo-mcp Service

## Comments

Implemented 2026-07-13.

`forgejo-mcp` now declares the standard Service Ingress Route for
`mcp.git.fearn.cloud`, targeting its TCP Published Port `8080` on
`forgejo-vm`.  It deliberately uses the same `lan_only`, Let's Encrypt DNS,
and no-extra-auth posture as the Forgejo web client route.  Clients configure
the upstream-preserved path as `https://mcp.git.fearn.cloud/mcp`.

No MCP-specific Caddy rule or ingress schema was added.  The generated route
uses Caddy's ordinary `reverse_proxy` with no method matcher, path rewrite, or
`header_up`/`header_down` directives: it therefore forwards POST and optional
GET requests and does not remove the MCP or HTTP authorization headers.  The
same Caddy reverse-proxy behavior streams event-stream responses; a real
request/stream proof remains part of the live smoke-test issue.

Ingress regeneration already owns both generated Caddy configuration and the
Pi-hole DNS record set, so no static generated artifact is committed.  Focused
inventory/generator tests assert the Caddy target
`http://10.40.0.12:8080`, generated TLS hostname, and generated DNS record;
the existing runtime validator proves an ingress route references a declared
TCP Published Port.
