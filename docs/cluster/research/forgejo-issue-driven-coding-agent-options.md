> Historical Canon source — migrated to Rite on 2026-07-31 from `docs/research/forgejo-issue-driven-coding-agent-options.md`. See [migration status](../README.md).

# Self-hosted coding agents driven by Forgejo issues

Research date: 2026-07-28. This note uses official documentation and source
repositories. The agent-product landscape is moving quickly; product status and
deployment claims below are those visible on the research date.

## Executive finding

There is not yet a mature, turnkey product whose documented path is exactly
"watch a self-hosted Forgejo repository for `ready-for-agent`, execute the issue
inside an isolated self-hosted Kubernetes worker, and open a Forgejo pull
request."

The pieces do exist, and Forgejo already supplies more of the control plane than
the question implies. A workflow can react directly to the `issues: labeled`
event, so polling is not required for the primary path. Forgejo Actions also
supports scheduled workflows for reconciliation, a per-run repository token,
workflow concurrency groups, and container-backed runners. Its generated API
supports the issue, label, branch, pull-request, review, status, and webhook
operations needed by an orchestrator. ([Forgejo Actions event and schedule
reference](https://forgejo.org/docs/v15.0/user/actions/reference/), [automatic
token](https://forgejo.org/docs/v16.0/user/actions/basic-concepts/), [Forgejo v15
API usage](https://forgejo.org/docs/v15.0/user/api-usage/), [Forgejo v15
OpenAPI](https://v15.next.forgejo.org/swagger.v1.json))

Two approaches are therefore credible:

1. **Start with a Forgejo Actions workflow that invokes a headless coding
   agent.** This is the shortest path to a working single-repository experiment.
2. **If the agent belongs inside a Canon-managed K3s Cluster, build a thin,
   deterministic Forgejo controller that launches one Kubernetes Job per
   claimed issue.** This is the better long-term boundary: Forgejo remains the
   durable Work State, the controller owns claims and state transitions, and the
   coding agent only works inside its isolated checkout.

OpenHands and Coder are the closest existing self-hosted agent platforms, but
both still require a Forgejo adapter. OpenHands is the lighter and more directly
automation-shaped option; Coder is the heavier option with the stronger
workspace/control-plane product.

## Options at a glance

| Option | Existing capability | Forgejo gap | K3s fit | Assessment |
|---|---|---|---|---|
| Forgejo Actions + headless agent CLI | Native issue-label trigger, schedules, secrets, run logs, repository token, runner dispatch | Workflow must implement claim/status/branch/PR protocol | Runner itself does not yet use Kubernetes Jobs as a stable backend | Best first proof of concept |
| Canon-managed Forgejo controller + Kubernetes Jobs | Forgejo webhooks/API plus any non-interactive agent | Small controller must be written | Native: controller Deployment and ephemeral worker Jobs | Best long-term fit |
| OpenHands Agent Canvas + Automation Service | Self-hosted agent server; cron and generic signed-webhook automations; multiple agent backends | No documented Forgejo SCM connector or ready-made issue-to-Forgejo-PR automation | Containerizable, but no simple open-source K3s chart was documented | Best platform to prototype before writing the whole agent layer |
| Coder Agents | Self-hosted agent loop, API, durable chat state, Kubernetes workspaces, governance | No documented Forgejo issue trigger/PR adapter | Excellent, with official Helm install and Kubernetes workspace templates | Strong but comparatively large; beta |
| Open SWE | Asynchronous issue/thread-to-draft-PR architecture, webhooks, sandboxes, follow-ups | GitHub/Linear/Slack-specific and its documented production path uses LangGraph Cloud | Not an own-cluster turnkey deployment | Useful design reference, poor direct fit |
| Codex CLI / OpenHands CLI / SWE-agent | Capable non-interactive worker engines | No durable ticket orchestration | Easy to put in a worker image | Components, not complete solutions |

## 1. Forgejo Actions is already an event-driven dispatcher

Forgejo Actions can trigger a workflow when an issue is labeled. A job can
inspect the event payload and continue only when the added label is
`ready-for-agent`. A scheduled workflow can periodically find ready but
unclaimed issues and recover missed events. The workflow exists on the default
branch, while the issue-specific work happens on a new branch. ([issue and
schedule events](https://forgejo.org/docs/v15.0/user/actions/reference/))

The automatic `FORGEJO_TOKEN` exists for the workflow's lifetime and, outside
untrusted fork pull-request runs, has repository write permission usable for Git
pushes and API calls. That is enough to update labels/comments, push a Work
Branch, and create a Work Pull Request without placing a broad, long-lived
personal token in the agent container. ([token behavior](https://forgejo.org/docs/v16.0/user/actions/basic-concepts/),
[Actions security](https://forgejo.org/docs/latest/user/actions/security/))

A workflow-level concurrency group can reduce duplicate runs, but Forgejo calls
its guarantee best-effort. The workflow must still perform an idempotent claim:
re-read the issue, verify it is open and ready, then make a deterministic state
change such as replacing `ready-for-agent` with `agent-running`, recording the
run identity in a comment, or assigning a dedicated bot. The controller—not the
LLM—should own that transition. ([concurrency semantics](https://forgejo.org/docs/v15.0/user/actions/reference/))

The important limitation is execution topology. Forgejo Runner currently runs
jobs through Docker/Podman, LXC, or directly on its host. A host runner has no
meaningful isolation; container isolation can also be defeated by dangerous
runner configuration. Forgejo supports ephemeral registrations, but that makes
the runner one-job, not the job a native Kubernetes Job. ([runner
configuration](https://forgejo.org/docs/latest/admin/actions/configuration/),
[runner security](https://forgejo.org/docs/v15.0/admin/actions/security/),
[ephemeral registration](https://forgejo.org/docs/v15.0/admin/actions/registration/))

As of May 2026, Forgejo described a pluggable backend architecture and a working
Kubernetes prototype, not a released, documented production backend. Running a
Docker-socket or privileged Docker-in-Docker runner Pod merely moves a powerful
container daemon into the Cluster and weakens the isolation story. ([Forgejo May
2026 report](https://forgejo.org/2026-05-monthly-report/), [Docker access threat
model](https://forgejo.org/docs/v15.0/admin/actions/docker-access/))

**Consequence:** Forgejo Actions plus a dedicated runner VM is a clean first
experiment. For a Canon-owned Cluster workload, a custom controller that creates
ordinary Kubernetes Jobs is a cleaner destination than forcing Forgejo Runner
into K3s today.

## 2. A small Forgejo-to-Kubernetes controller is the cleanest Canon workload

Forgejo supports repository, organization, and system webhooks. A controller can
receive the issue-labeled event immediately; a low-frequency API sweep can
reconcile missed events after downtime. ([Forgejo webhooks](https://forgejo.org/docs/latest/user/webhooks/))

The controller's deterministic responsibilities would be:

1. Validate the webhook and select only open issues carrying
   `ready-for-agent`.
2. Claim the issue idempotently and persist an issue-to-run identity.
3. Create an isolated Kubernetes Job from a pinned worker image, with resource,
   time, network, and filesystem limits.
4. Give the worker the issue body and comments plus a scoped, short-lived route
   to the repository.
5. Collect the exit result, test evidence, branch, and draft Work Pull Request;
   update Forgejo to `needs-review`, `blocked`, or `failed`.
6. Leave final merge behind a human review and protected branch.

The Forgejo API already exposes the needed issue, label, branch, PR, review,
status, and webhook surfaces. Canon would own this controller and its worker
declaration as Cluster Desired State, while Forgejo and the credentials needed
to recover it remain in the External Recovery Substrate. That respects Canon's
rule that no Cluster may be necessary to recover its own Git authority.
([Canon External Recovery Substrate](../../../CONTEXT.md), [Forgejo generated
OpenAPI](https://v15.next.forgejo.org/swagger.v1.json))

This is glue code, not a novel coding agent. The worker can initially invoke one
of the existing engines below and can later switch engines without changing the
claim/state protocol.

## 3. OpenHands: closest automation-shaped self-hosted platform

OpenHands' current architecture offers an Agent Server, an Agent Canvas, and a
separate Automation Service. The Agent Server is a REST/WebSocket server for
running agents in isolated local, Docker, VM, or remote workspaces; its SDK
describes Docker and Kubernetes deployment. It can run the OpenHands agent or
delegate to ACP-compatible agents. ([Agent Server overview](https://docs.openhands.dev/sdk/guides/agent-server/overview),
[OpenHands SDK](https://docs.openhands.dev/sdk/index), [ACP agent](https://docs.openhands.dev/sdk/guides/agent-acp))

The open-source Automation Service is explicitly beta. It supports cron and
event-driven runs, stores run history, and exposes custom webhook registration
with configurable sources, signing secrets, signature headers, and event-key
expressions. That generic webhook surface is unusually close to what Forgejo
needs: a Forgejo webhook can trigger an automation without first pretending to
be GitHub. ([Automation Service repository](https://github.com/OpenHands/automation),
[custom webhook implementation](https://github.com/OpenHands/automation/blob/main/openhands/automation/webhook_router.py))

What is missing is the other half of the integration. The built-in source-code
automation schemas and connectors are GitHub-oriented, and there is no
documented Forgejo connector that claims issues, clones with Forgejo credentials,
pushes branches, opens Forgejo draft PRs, and posts results. A custom automation
or a Forgejo MCP/tool adapter is still required. The open-source deployment
instructions are primarily local/VM/Docker; the separate OpenHands Cloud Helm
charts are under the Polyform Free Trial License and require a commercial
license beyond its trial allowance. ([OpenHands repository](https://github.com/OpenHands/OpenHands),
[OpenHands Cloud license and charts](https://github.com/OpenHands/OpenHands-Cloud))

**Assessment:** a good spike if the desired product includes a dashboard,
multiple agent backends, follow-up conversations, and generic automations. It is
more software and more change risk than a single purpose controller, and the
Forgejo Work State protocol still has to be designed.

## 4. Coder Agents: strongest self-hosted workspace platform, larger scope

Coder Agents runs its own agent loop in the self-hosted Coder control plane,
keeps model credentials out of workspaces, provisions a workspace on demand,
and exposes a chat API for automation. Coder documents support for external or
self-hosted model endpoints. The feature is beta. ([Coder Agents](https://coder.com/docs/ai-coder/agents))

Coder has an official Helm installation path and an official template that
provisions a Kubernetes Pod plus persistent home volume as a workspace. Its
security reference says ordinary control-plane and workspace Pods do not require
privilege, host mounts, or host networking. ([Kubernetes install](https://coder.com/docs/install/kubernetes),
[Kubernetes workspace template](https://registry.coder.com/templates/coder/kubernetes))

There is no documented Forgejo trigger or Forgejo PR integration. A controller
would still need to map an issue to a Coder chat, place Forgejo credentials in
the workspace through a narrow mechanism, and translate completion into branch,
PR, comments, and labels. Also avoid starting new work on the older Coder Tasks
API: Coder has announced its deprecation in favor of Coder Agents and the Chats
API. ([Tasks-to-Chats migration](https://coder.com/docs/ai-coder/agents/tasks-to-chats-migration))

**Assessment:** attractive if Canon should eventually host shared developer
workspaces, human handoff, audit/governance, and several agent types. It is
probably too large if the sole requirement is "one issue becomes one draft PR."

## 5. Open SWE: the right workflow shape, the wrong forge and deployment

Open SWE is an MIT-licensed asynchronous coding-agent framework. It accepts
GitHub/Linear/Slack webhooks, creates a persistent isolated sandbox for each
thread, supports mid-run follow-up messages and subagents, and instructs the
agent to commit, push, and open a draft PR. This is almost exactly the desired
user workflow. ([Open SWE repository](https://github.com/langchain-ai/open-swe))

Its integration is nevertheless GitHub-specific, including GitHub App OAuth and
GitHub operations in the sandbox. Its supported sandbox providers are hosted
services such as Modal, Daytona, Runloop, and LangSmith, and its documented
production installation uses LangGraph Cloud. Porting it means replacing both
the forge integration and likely the sandbox/deployment backend. ([Open SWE
installation](https://github.com/langchain-ai/open-swe/blob/main/INSTALLATION.md),
[customization and architecture](https://github.com/langchain-ai/open-swe/blob/main/CUSTOMIZATION.md))

**Assessment:** valuable source architecture to borrow from, but not the shortest
route to an all-own-infrastructure Forgejo agent.

## 6. Worker engines, not orchestrators

- **Codex CLI** is Apache-2.0 and supports non-interactive `codex exec`, including
  stdin prompts and ephemeral runs. It is straightforward to bake into a worker
  image. The official Codex Action adds API-key proxying and privilege controls,
  but is documented for GitHub Actions and includes GitHub-specific actor
  authorization. Forgejo explicitly says its Actions implementation is familiar,
  not compatible, so invoke the CLI directly before assuming the GitHub Action
  is portable. ([Codex CLI](https://github.com/openai/codex), [non-interactive
  execution](https://github.com/openai/codex/blob/main/codex-rs/README.md),
  [Codex Action](https://github.com/openai/codex-action), [Forgejo compatibility
  statement](https://forgejo.org/docs/latest/user/actions/overview/))
- **OpenHands CLI/SDK** supports headless scripting and remote Agent Servers and
  is provider-neutral. It is a good worker if OpenHands' full control plane is
  unnecessary. ([headless CLI](https://docs.openhands.dev/openhands/usage/cli/quick-start),
  [SDK remote execution](https://docs.openhands.dev/sdk/guides/agent-server/overview))
- **SWE-agent** can solve a supplied problem against a local repository and emit
  or apply a patch, but its official docs now say it is maintenance-only and
  superseded by mini-SWE-agent. Neither supplies the Forgejo claim/state/PR
  controller needed here. ([SWE-agent status](https://swe-agent.com/latest/installation/tips/),
  [local repository operation](https://swe-agent.com/latest/reference/repo/))

The choice of worker engine should therefore remain behind a narrow interface:
repository checkout + issue prompt in; structured result + changed worktree out.

## Recommended sequence

1. **Prove the workflow with Forgejo Actions and one dedicated, isolated runner.**
   Trigger on `issues: labeled`, check for `ready-for-agent`, make an idempotent
   claim, run a pinned headless-agent image, push a Work Branch, open a draft
   Work Pull Request, and stop before merge. Add a scheduled sweeper for missed
   or stale claims.
2. **Keep Forgejo mutations outside the model loop.** The deterministic wrapper
   claims work, prepares the prompt, interprets a structured result, posts Test
   Evidence, and changes state. The agent does code and tests; it does not decide
   whether it has authorization to merge or redefine Acceptance Criteria.
3. **Then move execution to a Canon-managed controller and Kubernetes Jobs** if
   the proof is useful. This removes the awkward Docker-daemon-in-K3s runner
   topology and gives each ticket a native Pod security, network policy, quota,
   timeout, and cleanup boundary.
4. **Spike OpenHands Automation in parallel only if its UI, conversations, and
   multi-agent backends are desired product capabilities.** Otherwise, use a
   CLI/SDK inside the Kubernetes Job and keep the control plane small.
5. **Treat pull requests as proposals.** Require human approval on the final PR,
   protected default branches, and independent validation for higher-risk work.

The minimal architecture is therefore:

`Forgejo issue label -> deterministic claim -> isolated worker -> tests -> draft
PR -> human/independent validation`, with polling only as reconciliation rather
than the main dispatch mechanism.
