# Prove no-global-token per-request auth behavior

Status: ready-for-human
Category: enhancement

## What to build

Add automated or scriptable checks that prove the selected upstream server can run without a global Forgejo token and uses per-request `Authorization` headers for identity. This issue is about local/container behavior and request routing, not live write authority against production data.

Prefer a lightweight test harness around the selected container or a documented command sequence that can be run against a harmless Forgejo endpoint. The important boundary is that the Service must not silently act as a different global identity when a request omits or supplies a bad token.

## Acceptance criteria

- [x] The checked-in Service config does not pass a global Forgejo token.
- [ ] A Streamable HTTP initialize request can reach `/mcp` with the required MCP `Accept` and JSON `Content-Type` headers.
- [ ] A request without `Authorization` fails safely or cannot perform authenticated Forgejo work.
- [ ] A request with `Authorization: token <token>` or `Authorization: Bearer <token>` is forwarded as the client identity according to upstream behavior.
- [ ] A bad token does not fall back to a broader identity.
- [x] Browser-style `Origin` behavior is checked and any required Caddy/upstream mitigation is recorded.
- [x] The proof is documented as a command or test that future agents can rerun.
- [x] Any discovered upstream limitation is recorded with a recommendation before implementation proceeds to live rollout.

## Blocked by

- Declare the forgejo-mcp Service

## Comments

2026-07-13 — Implemented `scripts/forgejo-mcp-auth-proof` and documented it in `runbooks/forgejo-mcp.md`. The script takes endpoint, tokens, and expected logins from environment variables only; it never prints tokens or response bodies. It initializes Streamable HTTP with the required headers, retains `Mcp-Session-Id`, and calls `get_my_user_info` in the same session with no authorization, `token`, `Bearer`, and deliberately invalid Bearer authorization. Valid credentials must resolve to two distinct expected logins; missing and bad credentials must return an explicit rejection and must not resolve to either proof identity.

The checked-in service configuration has no `--token`, `FORGEJO_ACCESS_TOKEN`, `GITEA_ACCESS_TOKEN`, or secret source. This matters because upstream deliberately falls back to its global singleton for a missing or unrecognized request header; blank global-token configuration is the safety boundary.

Origin limitation recorded: `goern/forgejo-mcp` v2.30.2 and its `github.com/mark3labs/mcp-go` v0.44.0 Streamable HTTP server do not validate `Origin`. The proof sends a credential-free browser-style Origin request and records status, response type, and whether CORS is present. Fortress currently has no accepted browser-Origin policy or ingress schema for a Caddy mitigation. Keep the endpoint for non-browser MCP clients; before allowing browser-originated use or widening reachability, adopt and test an explicit allowed-origin or reject-all-Origin Caddy policy.

Focused verification: `python3 -m unittest tests.test_forgejo_mcp_auth_proof` proves that the command sends and evaluates the intended request sequence, not that the selected upstream container has done so. The workspace has no Docker or Podman runtime, so the remaining four live behavioral checks require an operator to deploy the Service and run the documented command with two least-privilege identities. Record those results here before marking this issue done; they can be collected alongside issue 04's smoke test.
