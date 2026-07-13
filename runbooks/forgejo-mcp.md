# Forgejo MCP

## Operator use

`forgejo-mcp` is an MCP Service on `forgejo-vm`, available to Trusted clients at
`https://mcp.git.fearn.cloud/mcp`.  It uses the Streamable HTTP transport; point
an MCP client at that exact `/mcp` path and have the client send the Forgejo
access token with each request (`Authorization: Bearer <token>` or
`Authorization: token <token>`).

The Service has **no global Forgejo token**.  It does not receive a Forgejo
administrator token, a shared automation token, or credentials from the
Forgejo Runner.  Forgejo determines the caller and its authority from the
token presented by the MCP client on that request.  A tool may write only when
the presented token's Forgejo scopes and repository membership permit that
write.

Operators supply a separate least-privilege token for each repository/client
pair.  Keep those tokens in a local, git-ignored environment file rather than
in Inventory, SOPS material for this Service, an MCP client configuration
committed to a repository, or a shell history.  For example, an operator may
use `.env/forgejo-mcp/<repository>.env` (the `.env/` directory is ignored):

```sh
export FORGEJO_MCP_URL=https://mcp.git.fearn.cloud/mcp
export FORGEJO_MCP_TOKEN=<token-scoped-for-this-repository-and-client>
```

Load the matching file only for the client session that needs it, and configure
that client to use `FORGEJO_MCP_URL` and send `FORGEJO_MCP_TOKEN` as a Bearer
or token-scheme authorization header.  Grant read-only scopes for exploration
and the narrowest repository write scopes only where the client genuinely must
mutate Forgejo state.  Revoke and replace the one repository/client token when
that client or its access changes; no service-wide credential rotation is
needed.

MCP client reachability matches Forgejo client reachability: Trusted clients,
including tailnet-routed Operator workstations acting as Trusted clients, use
the HTTPS ingress path.  It is not a public endpoint and clients must not use
the service's backend port directly.

`forgejo-mcp` is not in the Service Directory.  The directory is browser
navigation, while this endpoint is for non-browser MCP clients; the current
upstream transport does not enforce an Origin policy.  Do not add browser
navigation or browser-originated use until an explicit ingress Origin policy
has been designed and tested.

## Runner and deployment boundary

The Forgejo Runner is not the MCP runtime.  `forgejo-mcp` runs as a Service on
`forgejo-vm`; runner jobs remain on `forgejo-runner-vm` and retain their
phase-one, non-mutating repository-validation boundary.  This Service does
not give the Runner a Forgejo API token, deployment credentials, SOPS access,
or authority to converge Hosts, VMs, NAS, PBS, or Services.  A deployment
runner, if ever needed, requires a separate design.

## Prove HTTP authentication behavior

Run the proof only after `forgejo-mcp` and its ingress route are deployed. It uses the non-mutating `get_my_user_info` MCP tool and requires two distinct, least-privilege Forgejo identities so it can demonstrate that identity is selected on every request.

Set the endpoint and expected login names, then enter the tokens without putting either token in shell history:

```bash
export FORGEJO_MCP_URL=https://mcp.git.fearn.cloud/mcp
export FORGEJO_MCP_TOKEN_AUTH_LOGIN=<first-forgejo-login>
export FORGEJO_MCP_BEARER_AUTH_LOGIN=<second-forgejo-login>
read -rs -p 'Forgejo token-scheme token: ' FORGEJO_MCP_TOKEN_AUTH_TOKEN; echo
read -rs -p 'Forgejo bearer-scheme token: ' FORGEJO_MCP_BEARER_AUTH_TOKEN; echo
export FORGEJO_MCP_TOKEN_AUTH_TOKEN FORGEJO_MCP_BEARER_AUTH_TOKEN
./scripts/forgejo-mcp-auth-proof
unset FORGEJO_MCP_TOKEN_AUTH_TOKEN FORGEJO_MCP_BEARER_AUTH_TOKEN
```

The script sends Streamable HTTP `initialize` to `/mcp` with `Accept: application/json, text/event-stream` and `Content-Type: application/json`, keeps the returned `Mcp-Session-Id`, then invokes `get_my_user_info` in that same session with no header, `Authorization: token`, `Authorization: Bearer`, and a deliberately invalid Bearer token. It passes only when the two valid requests return their distinct expected logins and the missing and bad requests return an explicit rejection without either proof identity. It does not print supplied tokens or response bodies.

The final request records the behavior of a browser-style `Origin: https://fortress-origin-probe.invalid` header without sending credentials. At `goern/forgejo-mcp` v2.30.2, upstream and its `mcp-go` Streamable HTTP dependency do not validate `Origin`; a successful response therefore records an upstream limitation, not browser support. Fortress currently has no accepted browser-Origin policy or ingress-route field for a Caddy mitigation. Keep the endpoint for non-browser MCP clients; before allowing browser-originated use or widening its reachability, adopt an explicit allowed-origin or reject-all-Origin Caddy policy and test the generated route.
