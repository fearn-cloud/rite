Status: done
Label: wayfinder:task
Parent: ../MAP.md
Assignee: Codex

# Implement inventory-managed Caddy SSH forwarding

## Question

Can the accepted raw TCP ingress design be implemented through inventory and deployment workflows so ordinary clients reach Forgejo SSH through `git.fearn.cloud` without a workspace SSH stanza?

Apply the smallest durable implementation of the design from **Design inventory-managed Caddy SSH forwarding**: add the Caddy layer4 module declaration, add the inventory surface for the Forgejo SSH TCP route, render and deploy the Caddy layer4 listener on a non-conflicting ingress address/port, and prove with `ssh -F /dev/null` that `git.fearn.cloud:22` reaches Forgejo rather than `internal-ingress-vm` OpenSSH.

## Blocked by

- .scratch/git-over-ssh/issues/05-design-inventory-managed-caddy-ssh-forwarding.md

## Comments

### Resolution

Implemented the accepted Caddy layer4 ingress design for Forgejo SSH.

Repo/inventory changes:

- Added `ingress_tcp_routes` as a Service inventory surface for raw TCP ingress, with schema validation and generator support.
- Declared Forgejo's SSH route in `inventory/services/forgejo.yaml`: `git.fearn.cloud` on `10.40.0.21:22` proxies to `forgejo-vm` at `10.40.0.12:2222`.
- Added `github.com/mholt/caddy-l4` / `layer4` to `inventory/services/internal-ingress.yaml`.
- Updated the internal-ingress base Caddyfile to import `/etc/caddy/fortress/generated-layer4.caddy` inside the global options block.
- Updated ingress regeneration to push generated layer4 routes before generated HTTP routes and to prove DNS records per generated hostname/address, because `git.fearn.cloud` now intentionally resolves to the SSH listener address while other routes remain on `10.40.0.16`.
- Updated domain/docs/tests for Service TCP Ingress Route and the `10.40.0.21` Forgejo SSH ingress address.

Live changes performed on `internal-ingress-vm`:

- Added `10.40.0.21/24` to `eth0` and persisted it in `/etc/netplan/50-cloud-init.yaml`; a backup was left at `/etc/netplan/50-cloud-init.yaml.fortress-before-git-ssh`.
- Added `/etc/ssh/sshd_config.d/99-fortress-ingress-listen-address.conf` with `ListenAddress 10.40.0.16`, validated with `sshd -t`, and restarted `ssh` so management SSH no longer owns wildcard `0.0.0.0:22`.
- Ran `./scripts/ingress-regenerate`, which pushed `/etc/caddy/fortress/generated-layer4.caddy`, pushed generated HTTP routes, reloaded Caddy, pushed DNS records to both DNS Services, restarted Pi-hole on each, and proved both DNS targets.
- Ran `./scripts/service-deploy internal-ingress`, which installed the missing Caddy `layer4` module, rendered `/etc/caddy/Caddyfile`, and restarted Caddy.

Proof:

- `getent hosts git.fearn.cloud` returns `10.40.0.21`.
- On `internal-ingress-vm`, `ss -ltnp` shows Caddy listening on `10.40.0.21:22` and OpenSSH listening on `10.40.0.16:22`.
- `caddy list-modules` includes both `dns.providers.cloudflare` and `layer4`.
- `curl -k -I https://git.fearn.cloud/` returns `HTTP/2 200`, so moving the hostname DNS record to `10.40.0.21` did not break HTTPS.
- Bare `ssh -F /dev/null -o BatchMode=yes -o ConnectTimeout=5 git@git.fearn.cloud` reaches the new endpoint but stops at host key verification in this non-interactive workspace.
- With host-key prompts disabled, `ssh -F /dev/null -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o BatchMode=yes -o ConnectTimeout=5 git@git.fearn.cloud` reaches Forgejo and fails at `Permission denied (publickey)`, not connection refusal or ingress VM management SSH.
- `ssh-keyscan` normalized public keys prove `git.fearn.cloud:22` matches direct Forgejo SSH at `10.40.0.12:2222` and differs from `internal-ingress-vm` management SSH at `10.40.0.16:22`.

Remaining blocker for pull/push proof is repository SSH authorization/key selection, covered by **Confirm Forgejo SSH authorization for todo**.
