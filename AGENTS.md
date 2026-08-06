## Agent skills

### Issue tracker

Issues live in Forgejo for `fearn-cloud/rite`, accessed through the configured host-local `forgejo-mcp` server. Its launcher loads the repository-scoped credential from `.env/forgejo-mcp/fortress.env`; do not bypass MCP or print that file. External PRs are not a triage surface. See `docs/agents/issue-tracker.md`.

### Triage labels

Canonical Forgejo labels: `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, and `wontfix`. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context layout — one `CONTEXT.md` and `docs/adr/` at the repo root. See `docs/agents/domain.md`.
