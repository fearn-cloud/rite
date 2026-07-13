# Issue tracker: Forgejo via MCP

Issues and PRDs for this repo live in the Forgejo repository `fearn-cloud/rite` at `https://git.fearn.cloud`.

Use the configured `forgejo-mcp` server at `mcp.git.fearn.cloud` for all issue-tracker communication. Do not create tracker files under `.scratch/`.

## Authentication

Before communicating with the Forgejo MCP server, load the repository-local environment file:

```bash
source .env/forgejo-mcp/fortress.env
```

Use `FORGEJO_MCP_URL` as the MCP endpoint and send `FORGEJO_MCP_TOKEN` in the request `Authorization: Bearer` header. The environment file is secret material: never print, commit, log, or place either value in issue content, command output, or documentation.

## Workflow

- List or search work with the Forgejo MCP issue-listing tools.
- Read a ticket with the issue-by-index tool.
- Publish a new ticket with the issue-creation tool.
- Before applying or changing labels, list the repository labels and use their numeric IDs.
- Update a ticket with the issue-update tool; change open/closed state with the issue-state tool.
- Add discussion and progress updates with the issue-comment tool.

## When a skill says “publish to the issue tracker”

Create an issue in `fearn-cloud/rite` through the configured Forgejo MCP server. Include the completed specification, plan, or ticket body in that Forgejo issue.

## When a skill says “fetch the relevant ticket”

Read the referenced Forgejo issue through the configured Forgejo MCP server. The user will normally provide its issue number or URL.

## Pull requests

External pull requests are not a triage request surface. Triage operates on issues only.
