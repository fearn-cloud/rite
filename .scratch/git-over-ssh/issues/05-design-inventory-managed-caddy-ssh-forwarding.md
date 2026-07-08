Status: done
Label: wayfinder:research
Parent: ../MAP.md
Assignee: Codex

# Design inventory-managed Caddy SSH forwarding

## Question

What inventory schema, Caddy module/runtime shape, and deployment workflow changes should let `internal-ingress-vm` forward raw SSH traffic for `git.fearn.cloud` to Forgejo through Caddy?

The design should preserve the canonical remote `git@git.fearn.cloud:michael-fearn/todo.git`, keep the configuration declared in inventory YAML, and identify how port ownership is handled on `internal-ingress-vm` where management SSH currently listens on TCP/22. It should also say whether the current Caddy package needs the `layer4` app or another module, how `just ingress-regenerate` or `service-deploy internal-ingress` should converge the config, and what proof command will show that clients are reaching Forgejo through ingress rather than through a workspace-only SSH host stanza.

## Blocked by

- .scratch/git-over-ssh/issues/02-make-git-fearn-cloud-ssh-reach-forgejo.md

## Comments

### Resolution

Research asset: [Caddy SSH Forwarding Options for git.fearn.cloud](../research/05-caddy-ssh-forwarding-options.md)

Decision: use Caddy on `internal-ingress-vm`, but add raw TCP forwarding as a separate inventory-managed ingress surface and give Git SSH its own ingress address. The durable target shape is:

```text
client git@git.fearn.cloud:22
  -> internal-ingress-vm Caddy layer4 on a dedicated Git SSH address
  -> forgejo-vm 10.40.0.12:2222
  -> Forgejo container SSH port 22
```

The current Caddy package is not enough by itself. Live check on `internal-ingress-vm` showed Caddy `v2.11.3` with only `dns.providers.cloudflare` as a non-standard module; no `layer4` modules are installed. Caddy docs say official packages include only standard modules, and this repo's native deploy path already uses `caddy add-package` for declared `deploy.caddy_modules`, so the inventory-managed module change should be:

```yaml
deploy:
  caddy_modules:
    - package: github.com/caddy-dns/cloudflare
      module: dns.providers.cloudflare
    - package: github.com/mholt/caddy-l4
      module: layer4
```

Port ownership should not move management SSH as the first choice. Live `ss -ltnp` showed OpenSSH owns `0.0.0.0:22` and `[::]:22` on `internal-ingress-vm`, while Caddy owns 80/443. Moving VM management SSH away from 22 is viable, but it has wider operator blast radius. The cleaner design is a second static address on `internal-ingress-vm` for Git SSH and a Caddy layer4 listener bound specifically to that address:

```caddyfile
{
	admin {$CADDY_ADMIN}

	layer4 {
		tcp/10.40.0.x:22 {
			route {
				proxy tcp/10.40.0.12:2222
			}
		}
	}
}

import /etc/caddy/fortress/generated-routes.caddy
```

Inventory should model this separately from HTTP `ingress_routes`, for example as `ingress_tcp_routes`, because `CONTEXT.md` currently defines Ingress as HTTP-family only and says non-HTTP published ports are direct backend exposures. This work should intentionally extend that model with a raw TCP ingress concept rather than overloading `Service Ingress Route`.

`service-deploy internal-ingress` should converge the stable Caddy scaffolding and install the `layer4` package extension. `just ingress-regenerate` should render generated raw TCP routes, push them to `internal-ingress-vm`, and reload Caddy just as it does for generated HTTP routes and DNS records.

Rejected or fallback options:

- Move `internal-ingress-vm` management SSH off port 22 and let Caddy own `10.40.0.16:22`; viable but larger operational blast radius.
- Use nftables DNAT, HAProxy TCP mode, or another host-level forwarder; viable if caddy-l4's experimental status is unacceptable, but it splits ingress management away from Caddy.
- Keep the workspace SSH config workaround; useful only temporarily and does not satisfy ordinary client reachability.

Proof command for the eventual implementation:

```sh
ssh -F /dev/null -o BatchMode=yes -o ConnectTimeout=5 git@git.fearn.cloud
GIT_SSH_COMMAND='ssh -F /dev/null -o BatchMode=yes -o ConnectTimeout=5' \
  git ls-remote git@git.fearn.cloud:michael-fearn/todo.git HEAD
```

The `-F /dev/null` flag is part of the proof because it prevents the current workspace-only SSH stanza from hiding whether ingress is really serving Forgejo SSH.
