# Forgejo MCP

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
