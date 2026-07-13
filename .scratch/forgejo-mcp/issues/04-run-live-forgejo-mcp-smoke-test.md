# Run live Forgejo MCP smoke test

Status: ready-for-human
Category: enhancement

## What to build

Run the live validation against Fortress Forgejo 15.0.3 after the Service and ingress route are deployed. Use at least one read-only Forgejo token and one deliberately write-scoped token. Record the commands, token scope shape, and outcomes without committing token material.

The smoke test should prove both the useful path and the permission boundary: reads work with a read token, a write attempt with that read token is denied by Forgejo, and an intentional write-scoped token can perform a harmless write when the operator chooses to allow it.

## Acceptance criteria

- [ ] `mcp.git.fearn.cloud` responds through internal ingress.
- [ ] MCP initialization succeeds over streamable HTTP.
- [ ] A read-only token can call a harmless read tool such as user info, repository listing, or issue read.
- [ ] The same read-only token is denied on a harmless write attempt.
- [ ] A write-scoped token can perform one operator-approved harmless write, such as creating a test issue/comment in a disposable repo or designated test issue.
- [ ] The Service logs do not print token material during the smoke test.
- [ ] Results and rollback notes are appended to this issue.

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
