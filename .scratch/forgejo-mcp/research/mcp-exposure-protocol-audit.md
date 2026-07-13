# MCP exposure protocol audit

Researched: 2026-07-13

## Question

Which protocols and ingress behaviors are required to expose `goern/forgejo-mcp` as `https://mcp.git.fearn.cloud`?

## Summary

Expose **Streamable HTTP over HTTPS** as the primary MCP protocol. Do not expose stdio. Treat legacy SSE as optional compatibility only.

The intended client URL is:

```text
https://mcp.git.fearn.cloud/mcp
```

The Service should run:

```text
forgejo-mcp --transport http --http-port 8080 --url https://git.fearn.cloud
```

without `--token` or `FORGEJO_ACCESS_TOKEN`.

## Required protocol surfaces

### 1. Client to ingress: HTTPS

`mcp.git.fearn.cloud` should be a normal Service Ingress Route using `tls: letsencrypt_dns`.

Rationale:

- MCP HTTP authorization guidance requires protected HTTP transports to use the HTTP `Authorization` header, and authorization endpoints/tokens must not be sent over plaintext.
- This repo's Service Ingress model already terminates TLS at Caddy and reverse-proxies to a VM-local HTTP Published Port.

### 2. Ingress to Backend: HTTP reverse proxy

The Backend target can be plain HTTP from Caddy to `forgejo-vm:<published_port>`, matching existing Service Ingress Routes.

Current Rite ingress generation renders:

```caddy
mcp.git.fearn.cloud {
        tls {
                dns cloudflare {$CLOUDFLARE_API_TOKEN}
        }
        reverse_proxy http://<forgejo-vm-address>:8080
}
```

That is protocol-compatible with Streamable HTTP as long as Caddy forwards:

- `POST /mcp`
- optional `GET /mcp` for server-to-client SSE stream support
- optional `DELETE /mcp` if the server implements session termination for the pre-2026 stateless transport
- `Authorization`
- `Accept`
- `Content-Type`
- `Mcp-Session-Id` for current sessionful Streamable HTTP clients
- `MCP-Protocol-Version`, `Mcp-Method`, and `Mcp-Name` for newer stateless clients as upstream support lands

Caddy's ordinary `reverse_proxy` should preserve these methods and headers unless explicitly configured otherwise. The implementation should still smoke-test them because MCP clients are less forgiving than browser apps.

### 3. MCP Streamable HTTP endpoint

The MCP 2025-03-26 transport spec defines Streamable HTTP as a single HTTP endpoint, commonly `/mcp`, supporting POST and GET. Clients send JSON-RPC messages with `POST`; servers may respond with either `application/json` or `text/event-stream`.

Required client request characteristics:

- `POST /mcp`
- `Accept: application/json, text/event-stream`
- `Content-Type: application/json`
- JSON-RPC body
- `Authorization: Bearer <token>` or `Authorization: token <token>` for our selected upstream

Required response handling:

- `application/json` responses must pass normally.
- `text/event-stream` responses must not be buffered into a complete response before reaching the client.
- Long-lived streams must not be killed by an unexpectedly short reverse-proxy timeout during normal MCP operation.

### 4. Optional legacy SSE endpoint

`goern/forgejo-mcp` also supports `--transport sse`, whose client URL is `/sse`. We should not choose this as the primary deployment because Streamable HTTP is the modern remote MCP transport. It is useful only if a specific client cannot speak Streamable HTTP.

If legacy SSE is later needed, it should probably be a separate compatibility decision, because `goern/forgejo-mcp` runs either `http` or `sse` transport per process. Supporting both at once may require a second Service/process or an upstream change.

### 5. Stdio is out of scope

Stdio is for local clients that launch the MCP server as a subprocess. It cannot be exposed through Caddy/ingress and would require a global local process/token model, which conflicts with the chosen Service design.

## Auth implications

The selected upstream extracts per-request tokens from `Authorization` in both Streamable HTTP and SSE transports. In the inspected source, accepted schemes are case-insensitive `token` and `bearer`; bare tokens are treated as absent.

This means:

- Clients should prefer `Authorization: Bearer <forgejo token>` where possible because it matches MCP HTTP authorization guidance.
- Forgejo-style `Authorization: token <forgejo token>` should also work with `goern/forgejo-mcp`.
- The container must not receive a global token. If no per-request token is present, there should be no fallback identity.
- The live smoke test must include a no-header request and a bad-token request.

## Origin and browser risk

The MCP transport spec warns Streamable HTTP servers to validate `Origin` to prevent DNS rebinding attacks, especially for local listeners. This deployment is not a loopback developer server; it is a LAN/tailnet-reachable internal HTTPS Service. Still, browser-originated requests are plausible because the endpoint is a real hostname.

Initial posture:

- Do not rely on CORS/browser access for normal operation.
- Prefer MCP clients that send explicit `Authorization` headers outside browser ambient auth.
- Add an implementation check for how `goern/forgejo-mcp` handles `Origin`.
- If upstream does not validate Origin, consider adding Caddy request handling for suspicious browser origins before exposing beyond the same reachability boundary as Forgejo.

## Repo fit

Current Rite primitives are enough for the first deployment:

- Quadlet Service with one Published Port.
- Service Ingress Route with `tls: letsencrypt_dns`.
- Generated DNS record pointing `mcp.git.fearn.cloud` at the Ingress VM.
- Caddy `reverse_proxy` to `forgejo-vm`.

Potential gaps to test rather than pre-design:

- Whether Caddy's default reverse proxy behavior streams `text/event-stream` responses adequately for MCP.
- Whether any MCP client requires the endpoint URL to include `/mcp`; if so, the Service route still owns the hostname and clients configure the path.
- Whether goern's current `mcp-go` version requires `Mcp-Session-Id` for post-initialize calls and whether Caddy preserves it.
- Whether future MCP `2026-07-28` stateless headers are already supported by the chosen release; if not, this is an upstream-version compatibility concern, not an ingress protocol blocker.

## Sources

- MCP 2025-03-26 transport spec: <https://modelcontextprotocol.io/specification/2025-03-26/basic/transports>
- MCP 2025-03-26 authorization spec: <https://modelcontextprotocol.io/specification/2025-03-26/basic/authorization>
- MCP 2026-07-28 release candidate notes: <https://blog.modelcontextprotocol.io/posts/2026-07-28-release-candidate/>
- `goern/forgejo-mcp` README and source inspected from <https://github.com/goern/forgejo-mcp>
- Rite ingress generation: `fortress_ingress/generate.py`

