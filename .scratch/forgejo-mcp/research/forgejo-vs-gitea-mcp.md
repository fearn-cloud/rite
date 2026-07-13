# `goern/forgejo-mcp` vs `gitea/gitea-mcp`

Researched: 2026-07-13  
Scope: feature and Forgejo-compatibility comparison, based on upstream documentation and source only. The source revisions inspected were [`goern/forgejo-mcp` `edb03d8`](https://codeberg.org/goern/forgejo-mcp/src/commit/edb03d8081863a84e6912f991fff76e8a1a2c466) and [`gitea/gitea-mcp` `bbde7ee`](https://gitea.com/gitea/gitea-mcp/src/commit/bbde7ee11063d3ea65edb2a5e08ea5bf0afb6bbb).

## Conclusion

Choose `goern/forgejo-mcp` when the target is Forgejo. It explicitly targets the Forgejo REST API, takes an arbitrary Forgejo instance URL, and has end-to-end demos against Codeberg. That is concrete compatibility evidence.

`gitea/gitea-mcp` may work for a subset of Forgejo APIs, but its upstream source makes no Forgejo compatibility claim or test declaration. It is Gitea-first (`gitea.dev/sdk`, `GITEA_*` configuration, and a Gitea default host). Forgejo's own documentation says Forgejo and Gitea are now diverging hard forks; it gives only a limited guarantee for tools designed for Gitea 1.22 and below on Forgejo 7+. Since `gitea-mcp` does not state that it targets that API level, **full compatibility with Forgejo, including Fortress Forgejo 15, cannot be established from the available primary sources.** Test each required tool against the deployed Forgejo version before selecting it.

## Feature differences

| Area | `goern/forgejo-mcp` | `gitea/gitea-mcp` |
| --- | --- | --- |
| Focus and API client | Explicitly a Forgejo/Codeberg REST API integration; uses a Forgejo SDK fork. | Explicitly a Gitea integration; imports `gitea.dev/sdk`. |
| Transports | stdio, streamable HTTP, and legacy SSE; also exposes a direct CLI mode. | stdio and streamable HTTP only. |
| HTTP identity | Documents a central, multi-tenant process accepting per-request `Authorization: token` or `Bearer` tokens. | Its HTTP handler also parses per-request `Bearer` or `token` headers, with a configured-token fallback. |
| MCP surface | Tools plus Forgejo resource templates for portable, read-only instance data. | Tools only; source registers tool capabilities, not MCP resources. |
| Safety/exposure controls | No equivalent upstream-documented read-only or explicit tool allowlist control found in the inspected README. | `--read-only`/`GITEA_READONLY` and an explicit comma-separated `--tools`/`GITEA_TOOLS` allowlist. |
| Notable coverage beyond shared repository/branch/file/issue/PR/release basics | Notification management, branch-protection CRUD, issue/comment/release attachments, release filtering and attachment operations, and a broad time-tracking/stopwatch set. It also supports workflow dispatch and workflow-run inspection. | Tags; directory-content reads; richer PR review lifecycle (add/remove reviewers, create/submit/delete/dismiss reviews); wiki CRUD and revision history; package operations; and a much broader Actions administration surface: secrets, variables, workflows, runs, jobs, cancellation/rerun, and job-log retrieval. |

The tool lists are the upstream projects' documented surface, not an assertion that every endpoint exists on every target server. See the [Forgejo MCP tool list](https://codeberg.org/goern/forgejo-mcp/src/commit/edb03d8081863a84e6912f991fff76e8a1a2c466/README.md#available-tools) and [Gitea MCP tool list](https://gitea.com/gitea/gitea-mcp/src/commit/bbde7ee11063d3ea65edb2a5e08ea5bf0afb6bbb/README.md#available-tools). The Gitea server's actual registration also includes notification, package, milestone, time-tracking, wiki, and Actions modules in addition to the README listing; see [`operation.go`](https://gitea.com/gitea/gitea-mcp/src/commit/bbde7ee11063d3ea65edb2a5e08ea5bf0afb6bbb/operation/operation.go).

## Compatibility evidence and limits

### `goern/forgejo-mcp`: established intent and practical evidence

- The project describes itself as interacting with the Forgejo REST API, specifically Codeberg; its README configures `--url https://your-forgejo-instance.org`, and describes resource URIs as instance-portable. [Project description](https://codeberg.org/goern/forgejo-mcp/src/commit/edb03d8081863a84e6912f991fff76e8a1a2c466) and [configuration/resources](https://codeberg.org/goern/forgejo-mcp/src/commit/edb03d8081863a84e6912f991fff76e8a1a2c466/README.md#quick-start).
- Its end-to-end demos use Codeberg, a Forgejo deployment. [README demos section](https://codeberg.org/goern/forgejo-mcp/src/commit/edb03d8081863a84e6912f991fff76e8a1a2c466/README.md#demos).
- Its module file directly depends on `codeberg.org/mvdkleijn/forgejo-sdk/forgejo/v3`, rather than the Gitea SDK. [Module definition](https://codeberg.org/goern/forgejo-mcp/src/commit/edb03d8081863a84e6912f991fff76e8a1a2c466/go.mod).

This is enough to establish intended Forgejo support and a real Forgejo test target. It is **not** a compatibility matrix: upstream does not specify supported Forgejo major versions. Forgejo promises API compatibility only within one Forgejo major and warns that major upgrades may remove endpoints. [Forgejo API policy](https://forgejo.org/docs/latest/user/api-usage/). Thus exact support for a particular deployment, including Forgejo 15, still needs a smoke test.

### `gitea/gitea-mcp`: limited inference only

- The code is explicitly oriented to Gitea: the module is `gitea.com/gitea/gitea-mcp`, it imports `gitea.dev/sdk`, defaults to `https://gitea.com`, and only names `GITEA_*` variables. [Module](https://gitea.com/gitea/gitea-mcp/src/commit/bbde7ee11063d3ea65edb2a5e08ea5bf0afb6bbb/go.mod), [client](https://gitea.com/gitea/gitea-mcp/src/commit/bbde7ee11063d3ea65edb2a5e08ea5bf0afb6bbb/pkg/gitea/gitea.go), and [command configuration](https://gitea.com/gitea/gitea-mcp/src/commit/bbde7ee11063d3ea65edb2a5e08ea5bf0afb6bbb/cmd/cmd.go).
- No inspected README or source file mentions Forgejo or declares Forgejo tests/support. Absence of such a claim is not proof of failure, but it prevents an affirmative support conclusion.
- Forgejo documents that, as of Forgejo 7, tools made for Gitea 1.22 or earlier work without modification. It also says Forgejo became a hard fork in early 2024 and its codebase is diverging from Gitea. [Forgejo numbering/API compatibility](https://forgejo.org/docs/latest/user/versions/) and [Forgejo's comparison statement](https://forgejo.org/compare-to-gitea/).

Therefore, a Gitea-oriented MCP client may be a reasonable candidate for a narrowly tested API subset, but not a proven all-tool Forgejo solution. This is especially important for newer or divergent areas such as Actions administration, packages, wiki, branch protection, and attachment APIs.

## Suggested acceptance check

For either server, run against the exact Forgejo instance and least-privilege token intended for production: initialize MCP; authenticate; list repositories; read a file and issue; exercise each required write operation in a disposable repository; and exercise every planned Actions/package/wiki endpoint. Record the Forgejo major/minor and server API version with the result. Do not treat a successful basic read test as proof that the broader tool surface is compatible.
