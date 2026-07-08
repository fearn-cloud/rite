Status: ready-for-agent
Label: wayfinder:map

# Git over SSH to git.fearn.cloud

## Destination

`git.fearn.cloud` supports ordinary Git-over-SSH operations for the `michael-fearn/todo` repository through inventory-managed ingress on `internal-ingress-vm`: Caddy forwards SSH traffic to Forgejo, pull/fetch works from this workspace using the canonical remote, and a harmless push proof can be performed and verified.

## Notes

- Domain: Forgejo Service on `forgejo-vm`, reached by clients as `git.fearn.cloud`.
- Use the `diagnosing-bugs` skill for live connectivity failures, because existing evidence separates hostname routing from Forgejo's local listener.
- Execution is in scope for task tickets: this map is allowed to perform live checks and small operator changes needed to make the proof pass.
- Relevant existing facts:
  - `inventory/services/forgejo.yaml` declares `FORGEJO__server__SSH_DOMAIN=git.fearn.cloud` and `FORGEJO__server__SSH_PORT=2222`.
  - Forgejo publishes container port `22` on `forgejo-vm` host port `2222`.
  - `.scratch/forgejo-upgrade/issues/05-verify-forgejo-15-and-record-rollback-state.md` records that `git.fearn.cloud` resolved to `10.40.0.16` while Forgejo is on `10.40.0.12`; `git.fearn.cloud:2222` was refused, but direct SSH to `10.40.0.12:2222` reached Forgejo and failed at public-key auth.

## Decisions so far

<!-- the index -- one line per closed ticket -->

- [Confirm canonical Git SSH remote](issues/01-confirm-canonical-git-ssh-remote.md) — use `git@git.fearn.cloud:michael-fearn/todo.git`; the environment must avoid requiring an explicit port in ordinary remotes.
- [Make git.fearn.cloud SSH reach Forgejo](issues/02-make-git-fearn-cloud-ssh-reach-forgejo.md) — interim workspace SSH config proves Forgejo's listener is reachable at `10.40.0.12:2222`; the durable endpoint should still be inventory-managed ingress/Caddy forwarding.
- [Design inventory-managed Caddy SSH forwarding](issues/05-design-inventory-managed-caddy-ssh-forwarding.md) — use Caddy with `caddy-l4`, modeled as separate raw TCP ingress, bound to a dedicated Git SSH ingress address to avoid moving ingress VM management SSH.
- [Implement inventory-managed Caddy SSH forwarding](issues/06-implement-inventory-managed-caddy-ssh-forwarding.md) — `git.fearn.cloud` now resolves to `10.40.0.21`; Caddy layer4 owns `10.40.0.21:22` and forwards to Forgejo at `10.40.0.12:2222`, while VM management SSH remains on `10.40.0.16:22`.

## Ready for agent

- [Model ingress VM live host edits in inventory](issues/07-model-ingress-vm-live-host-edits-in-inventory.md) — live netplan and sshd changes required by the staged layer4 work should become inventory-declared facts converged by Rite.

## Not yet specified

- Whether the proof push should leave a trace in `michael-fearn/todo` or use a temporary branch that is deleted after verification. This graduates once repository authorization is confirmed.

## Out of scope

- Exposing Forgejo SSH to the public internet unless explicitly chosen later; the current destination is client reachability where HTTPS already works.
- Broader Forgejo upgrade acceptance items such as browser login, avatar EXIF decisions, or rollback state.
