# Document Forgejo MCP operations and boundary

Status: ready-for-agent
Category: enhancement

## What to build

Document how operators and agents should use the `forgejo-mcp` Service, including endpoint, token model, expected reachability, and the boundary from Forgejo Runner/deployment automation. Update the firewall matrix or related network docs if the new endpoint changes documented client reachability.

Consider an ADR only if the final implementation confirms the placement/auth decision is hard to reverse or surprising enough that future readers would wonder why MCP lives on `forgejo-vm` without a global token.

## Acceptance criteria

- [ ] A runbook or existing Forgejo doc explains `mcp.git.fearn.cloud`, supported transport path, and client token expectations.
- [ ] Documentation states that the Service has no global Forgejo token and that write authority comes from per-client Forgejo token scopes.
- [ ] Documentation preserves the Forgejo Runner boundary: the runner is not the MCP runtime and does not gain Forgejo API/deployment authority through this work.
- [ ] Firewall matrix or reachability docs show that MCP reachability matches Forgejo client reachability.
- [ ] Service Directory opt-in is added if that is consistent with existing operator navigation policy.
- [ ] An ADR is added only if the implementation uncovers a durable architectural trade-off worth preserving.

## Blocked by

- Run live Forgejo MCP smoke test

