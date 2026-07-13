# Run live Forgejo MCP smoke test

Status: ready-for-human
Category: enhancement

## What to build

Run the live validation against Fortress Forgejo 15.0.3 after the Service and ingress route are deployed. Use at least one read-only Forgejo token and one deliberately write-scoped token. Record the commands, token scope shape, and outcomes without committing token material.

The smoke test should prove both the useful path and the permission boundary: reads work with a read token, a write attempt with that read token is denied by Forgejo, and an intentional write-scoped token can perform a harmless write when the operator chooses to allow it.

## Acceptance criteria

- [x] `mcp.git.fearn.cloud` responds through internal ingress.
- [x] MCP initialization succeeds over streamable HTTP.
- [x] A read-only token can call a harmless read tool such as user info, repository listing, or issue read.
- [x] The same read-only token is denied on a harmless write attempt.
- [x] A write-scoped token can perform one operator-approved harmless write, such as creating a test issue/comment in a disposable repo or designated test issue.
- [x] The Service logs do not print token material during the smoke test.
- [x] Results and rollback notes are appended to this issue.

## Blocked by

- Expose mcp.git.fearn.cloud through internal ingress
- Prove no-global-token per-request auth behavior

## Comments

- 2026-07-13: `just service-deploy forgejo-mcp` initially failed because
  `forgejo-vm`'s configured resolver (`10.10.0.1`) has no
  `git.fearn.cloud` record. Added the Service's managed Quadlet fragment with
  `AddHost=git.fearn.cloud:10.40.0.21`, preserving the public hostname for
  TLS/SNI while reaching internal ingress. Redeployment completed and the
  `fortress-forgejo-mcp-server.service` unit is active.
- 2026-07-13: A credential-free streamable HTTP `initialize` request to
  `https://mcp.git.fearn.cloud/mcp`, resolved to internal ingress, returned
  HTTP 200, an `Mcp-Session-Id`, and the Forgejo MCP v2.30.2 server
  capabilities. The startup log reports `token_configured: false`; no token
  material was supplied to, or observed in, the service log.
- Remaining operator action: run `scripts/forgejo-mcp-auth-proof` with two
  least-privilege Forgejo identities (one per supported authorization scheme)
  and separately perform the explicitly approved write-scope test. Do not add
  token values to this issue or the repository.
- Rollback note: this validation performed no Forgejo write, so it created no
  data to roll back. Before the remaining approved write test, record the
  disposable resource identifier and its deletion/revert command here; do not
  attempt to undo a Forgejo write by redeploying the MCP Service.

- 2026-07-13: Live read-only validation passed using the supplied read-scoped
  token through `Authorization: token` (the token value was entered at a
  non-echoing prompt and is not recorded). Streamable HTTP `initialize` to
  `https://mcp.git.fearn.cloud/mcp` returned an MCP session ID; the same
  session successfully called `get_my_user_info`. A deliberately harmless
  `create_issue` attempt against public `fearn-cloud/forgejo-mcp` was denied:
  Forgejo reported that the token lacked `write:issue`. The attempt created no
  issue. The service journal for the test window was checked for both supplied
  token values; neither was present. Logs report only `token_configured:
  false`, request metadata, and the scope-denial message.
- Resolved operator decision: the write target had to be a disposable
  repository or existing designated issue with a recorded cleanup action,
  because MCP exposes no issue-delete tool. An arbitrary repository must not
  be used.
- 2026-07-13: The operator approved `michael-fearn/fullstack-todo` as the
  disposable write target. The supplied write-scoped token authenticated via
  `Authorization: token`, then created issue
  `michael-fearn/fullstack-todo#1` with an explicit smoke-test title and body.
  The MCP `issue_state_change` tool immediately changed that issue to
  `closed`, completing the agreed rollback. The issue remains as a closed,
  auditable test artifact; delete it manually in Forgejo only if its retention
  is no longer desired. A final journal scan for both supplied token values
  returned no matches.
