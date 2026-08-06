# Issue tracker: Forgejo via MCP

Issues and PRDs for this repo live in the Forgejo repository `fearn-cloud/rite` at `https://git.fearn.cloud`.

Use Codex's configured host-local `forgejo-mcp` stdio server for all issue-tracker communication. Codex starts it through `scripts/forgejo-mcp-local`, which runs the `forgejo-mcp` executable installed on this host. Do not communicate with the remote MCP endpoint directly and do not create tracker files under `.scratch/`.

## Authentication

The launcher loads `.env/forgejo-mcp/fortress.env` and supplies `FORGEJO_MCP_TOKEN` to the host-local server as `FORGEJO_ACCESS_TOKEN`. The token is passed through the process environment, never as a command-line argument. The environment file is secret material: never print, commit, log, or place its values in issue content, command output, or documentation.

The configured token must be least-privilege for this repository. Restart Codex after changing the launcher, MCP configuration, or token so the stdio server and its tools are rediscovered.

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
