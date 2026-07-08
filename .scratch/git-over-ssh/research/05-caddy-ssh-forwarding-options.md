# Caddy SSH Forwarding Options for git.fearn.cloud

## Summary

`internal-ingress-vm` can manage Git SSH traffic with Caddy, but only if the deployed Caddy binary is extended with `github.com/mholt/caddy-l4` and port ownership is changed so Caddy, not OpenSSH, owns the client-facing SSH socket.

The recommended fortress shape is to give `internal-ingress-vm` a second Infrastructure VLAN address dedicated to Git SSH, point `git.fearn.cloud` at that address for the SSH endpoint, and have Caddy layer4 bind `tcp/<git-ssh-address>:22` and proxy raw bytes to `10.40.0.12:2222`.

## Current State

- `git.fearn.cloud` currently resolves to `internal-ingress-vm` (`10.40.0.16`) for ingress HTTP.
- `internal-ingress-vm` Caddy is `v2.11.3`, listens on 80/443, and has only `dns.providers.cloudflare` as a non-standard module.
- `internal-ingress-vm` OpenSSH owns `0.0.0.0:22` and `[::]:22`.
- `forgejo-vm` exposes Forgejo web on `0.0.0.0:3000` and Forgejo SSH on `0.0.0.0:2222`.
- `inventory/services/internal-ingress.yaml` already declares `deploy.caddy_modules`, and `service-deploy` converges missing modules with `caddy add-package`.
- `fortress_ingress/generate.py` only renders HTTP-family Caddyfile site blocks today.

## Options

### Option A: Caddy layer4 on a second ingress address

Add a second static IPv4 address to `internal-ingress-vm`, for example `10.40.0.x/24`, reserve it as the Git SSH ingress address, and point the client-visible SSH endpoint at that address. Keep management OpenSSH on `10.40.0.16:22`; have Caddy layer4 bind only `tcp/10.40.0.x:22`.

This preserves the ordinary remote:

```text
git@git.fearn.cloud:michael-fearn/todo.git
```

It also avoids moving VM management SSH and avoids making Caddy own all port-22 traffic on the existing ingress address.

Recommended Caddyfile shape:

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

Inventory shape:

```yaml
ingress_tcp_routes:
  - name: git-ssh
    hostname: git.fearn.cloud
    listen:
      address_ref: git_ssh
      port: 22
    target:
      service: forgejo
      published_port: 2222
```

The exact schema can vary, but it should remain explicit that this is raw TCP forwarding, not a `Service Ingress Route`.

Deployment changes:

- Add `github.com/mholt/caddy-l4` to `inventory/services/internal-ingress.yaml` under `deploy.caddy_modules`, with expected module id `layer4`.
- Extend `Caddyfile.j2` or add another imported generated file for layer4 routes.
- Extend ingress regeneration to render the raw TCP route from inventory.
- Ensure validation rejects any raw TCP route trying to bind an address/port already owned by management SSH or HTTP Caddy.

Proof command:

```sh
ssh -F /dev/null -o BatchMode=yes -o ConnectTimeout=5 git@git.fearn.cloud
```

The proof should show the Forgejo SSH host key and fail or succeed at Forgejo auth, not expose the ingress VM OpenSSH host key. Then run:

```sh
GIT_SSH_COMMAND='ssh -F /dev/null -o BatchMode=yes -o ConnectTimeout=5' \
  git ls-remote git@git.fearn.cloud:michael-fearn/todo.git HEAD
```

Using `-F /dev/null` is important because the previous workspace-only SSH stanza can otherwise mask whether ingress is really working.

### Option B: Move ingress VM management SSH off port 22

Move `internal-ingress-vm` management SSH to another port, or bind it only to a management-only address, then let Caddy layer4 bind `10.40.0.16:22` and forward all Git SSH to Forgejo.

This uses the existing ingress address and DNS, but it has a larger operator blast radius: Ansible inventory, `scripts/vm-shell`, host key expectations, runbooks, and any break-glass SSH habits must all adapt before Caddy takes port 22.

This is viable, but less attractive than a second address.

### Option C: Do not use Caddy; use a host-level TCP forwarder

Keep standard Caddy as HTTP ingress and install a small systemd-managed forwarder on `internal-ingress-vm`, such as an nftables DNAT rule, HAProxy in TCP mode, or systemd socket/proxy plumbing.

This avoids caddy-l4's experimental status but splits ingress behavior across two mechanisms. It would require a new native service or network-firewall model in fortress. It is reasonable only if the project does not want a third-party experimental Caddy app in the ingress binary.

### Option D: Keep workspace SSH client config

The current workaround keeps the canonical remote text while routing only this workspace to `10.40.0.12:2222`.

This is useful as a temporary operator workaround, but it does not satisfy the destination because ordinary clients still reach `internal-ingress-vm` OpenSSH on port 22.

## Recommendation

Use Option A.

Model raw TCP ingress as a separate `ingress_tcp_routes` or equivalent inventory surface, not as a `Service Ingress Route`. Keep `Service Ingress Route` HTTP-family only. Let `service-deploy internal-ingress` converge the Caddy module and stable Caddyfile scaffolding; let `just ingress-regenerate` render and reload generated layer4 routes alongside HTTP routes.

## Sources

- Caddy install docs say official packages include only standard modules and third-party plugins need a custom build path: https://caddyserver.com/docs/install
- Caddy command docs describe `caddy add-package` as the mechanism that replaces the binary with one including additional packages: https://caddyserver.com/docs/command-line
- Caddy's project README describes Caddy as an extensible app platform and notes only `tls` and `http` ship standard: https://github.com/caddyserver/caddy
- caddy-l4 README describes the layer4 app as experimental, able to proxy raw bytes and match SSH/TLS/HTTP, and usable alongside HTTP/TLS apps: https://github.com/mholt/caddy-l4
- caddy-l4 server docs describe layer4 servers, address binding, and the Caddyfile `layer4` global directive: https://github.com/mholt/caddy-l4/blob/master/docs/servers.md
