# Ingress Live Proof TDD Handbook

Use this guide to work through the live Caddy/Cloudflare/Pi-hole proof one
behavior at a time. The goal is not to make a big batch of infra changes and
hope. Each cycle has:

- RED: prove the live behavior is currently missing or failing.
- GREEN: make the smallest change that should satisfy that behavior.
- VERIFY: rerun the same check and record the result.
- REFLECT: update the issue tracker before moving on.

Do not print secret values. It is fine to prove a token exists by checking for a
non-empty variable or successful Caddy validation.

## Current Known State

The first live preflight found two blockers:

- `internal-ingress-vm` is reachable and `caddy` is active.
- `dns-primary-vm` is reachable and Pi-hole/Unbound are active.
- Caddy does not currently have `CLOUDFLARE_API_TOKEN` in its runtime
  environment.
- The installed Caddy build does not include `dns.providers.cloudflare`.

Do not run `just ingress-regenerate` for the live proof until both Caddy
blockers are fixed. The generated routes require:

```caddy
tls {
	dns cloudflare {$CLOUDFLARE_API_TOKEN}
}
```

## Cycle 1: Caddy Has Cloudflare DNS Module

### RED

Prove the currently installed Caddy cannot satisfy Cloudflare DNS-01:

```sh
./scripts/vm-shell internal-ingress-vm -- caddy list-modules | grep -F dns.providers.cloudflare
```

Expected current result: non-zero exit.

### GREEN

Install or deploy a Caddy build that includes the Cloudflare DNS provider module
on `internal-ingress-vm`.

Candidate approaches:

- Package a custom Caddy binary built with `github.com/caddy-dns/cloudflare`.
- Replace the native package installation path with a repo-owned Caddy build
  workflow.
- Temporarily install a custom binary manually for live proof, then record a
  follow-up issue to make the packaging repo-owned.

### VERIFY

```sh
./scripts/vm-shell internal-ingress-vm -- caddy list-modules | grep -F dns.providers.cloudflare
```

Expected result: prints `dns.providers.cloudflare`.

### REFLECT

Record what changed in:

```text
.scratch/ingress-regeneration/issues/07-document-and-live-proof-ingress-regeneration-path.md
```

If the module was installed manually, create or record a follow-up issue for a
repo-owned Caddy packaging path.

## Cycle 2: Caddy Has A Cloudflare Token Without Leaking It

### RED

Prove Caddy currently has no usable token without printing any secret:

```sh
./scripts/vm-shell internal-ingress-vm -- sudo sh -c 'test -s /etc/default/caddy && grep -q "^CLOUDFLARE_API_TOKEN=." /etc/default/caddy'
./scripts/vm-shell internal-ingress-vm -- sudo systemctl show caddy -p Environment
```

Expected current result: first command exits non-zero, and the second command
does not show a token-bearing environment.

### GREEN

Add the Cloudflare token through the intended fortress secret path.

Preferred repo-owned shape:

- Add `inventory/services/internal-ingress.sops.yaml`.
- Store a structured Service Secret for the Cloudflare token.
- Update `inventory/services/internal-ingress.yaml` and/or
  `inventory/services/internal-ingress.native.d/caddy.env.j2` so Service Deploy
  renders `CLOUDFLARE_API_TOKEN` into Caddy's environment without printing it.
- Run:

```sh
just service-deploy internal-ingress
```

Temporary manual option:

- Add `CLOUDFLARE_API_TOKEN=<secret>` directly on `internal-ingress-vm` in the
  Caddy environment file.
- Restart Caddy.
- Record a follow-up issue because the secret path is not repo-owned.

### VERIFY

Use a non-printing check:

```sh
./scripts/vm-shell internal-ingress-vm -- sudo sh -c 'grep -q "^CLOUDFLARE_API_TOKEN=." /etc/default/caddy'
./scripts/vm-shell internal-ingress-vm -- sudo systemctl is-active caddy
```

Expected result: both commands exit zero.

### REFLECT

Update the live proof issue with:

- where the token is stored,
- whether deployment is repo-owned or manual,
- whether any follow-up issue is needed.

## Cycle 3: Generated Caddy Routes Validate Before Reload

### RED

Print generated routes and confirm they contain Cloudflare DNS-01 stanzas:

```sh
./scripts/ingress-regenerate --print
```

Then test validation without reloading by pushing the generated file only if
needed, or by using a temporary file on `internal-ingress-vm`.

Current generated routes include:

- `dns-primary.fearn.cloud`
- `forgejo.fearn.cloud`
- `grafana.fearn.cloud`
- `headscale.fearn.cloud`
- `files.fearn.cloud`
- Host Ingress Routes such as `wintermute.fearn.cloud`

### GREEN

If validation fails, fix the smallest missing part:

- missing Cloudflare module,
- missing token environment,
- invalid generated Caddy syntax,
- missing imported generated file path.

### VERIFY

After the generated file is present on the VM:

```sh
./scripts/vm-shell internal-ingress-vm -- sudo caddy validate --config /etc/caddy/Caddyfile
```

Expected result: validation succeeds.

### REFLECT

Record the validation command and result in the live proof issue.

## Cycle 4: Ingress Regeneration Pushes And Reloads Live Targets

### RED

Before mutation, confirm target services are active:

```sh
./scripts/vm-shell internal-ingress-vm -- systemctl is-active caddy
./scripts/vm-shell dns-primary-vm -- systemctl is-active fortress-dns-primary-pihole.service fortress-dns-primary-unbound.service
```

### GREEN

Run the actual workflow:

```sh
just ingress-regenerate
```

This should:

- install generated Caddy routes on `internal-ingress-vm`,
- reload Caddy,
- install `/etc/dnsmasq.d/99-fortress-ingress.conf` on `dns-primary-vm`,
- reload Pi-hole DNS.

### VERIFY

```sh
./scripts/vm-shell internal-ingress-vm -- systemctl is-active caddy
./scripts/vm-shell dns-primary-vm -- sudo test -s /etc/dnsmasq.d/99-fortress-ingress.conf
./scripts/vm-shell dns-primary-vm -- sudo podman exec fortress-dns-primary-pihole pihole status
```

Expected result: all commands succeed.

### REFLECT

Record whether `just ingress-regenerate` completed cleanly. If it fails, record
the failing step exactly and stop the live proof until that failure is fixed.

## Cycle 5: Pi-hole Resolves Ingress DNS Records

### RED

Choose one Service Ingress hostname. Prefer `dns-primary.fearn.cloud` because it
is on the Infrastructure VLAN and is already an Ingress-enabled Service.

From the operator workstation or another LAN client using fortress reachability:

```sh
dig @10.40.0.11 dns-primary.fearn.cloud A
```

### GREEN

If resolution fails:

- check `/etc/dnsmasq.d/99-fortress-ingress.conf`,
- rerun `just ingress-regenerate`,
- reload Pi-hole DNS,
- confirm firewall access to `10.40.0.11:53`.

### VERIFY

Expected answer: `dns-primary.fearn.cloud` resolves to `10.40.0.16`, the Ingress
VM address.

Also check one non-DNS Service hostname if available:

```sh
dig @10.40.0.11 forgejo.fearn.cloud A
```

Expected answer: also `10.40.0.16`.

### REFLECT

Record hostname, resolver used, answer IP, and client/source network.

## Cycle 6: Service Ingress Issues A Real Certificate And Serves HTTPS

### RED

Before curling, choose a low-risk Service hostname. `dns-primary.fearn.cloud` is
acceptable if the Pi-hole web UI route is expected to be reachable through
Ingress.

```sh
curl -v https://dns-primary.fearn.cloud/
```

### GREEN

If it fails:

- check Caddy logs:

```sh
./scripts/vm-shell internal-ingress-vm -- sudo journalctl -u caddy --no-pager -n 200
```

- fix the smallest observed issue: DNS-01 failure, token scope, module, Backend
  reachability, or DNS resolution.

### VERIFY

Expected result:

- HTTPS succeeds from the LAN.
- Certificate subject/SAN matches the hostname.
- Issuer is Let's Encrypt.
- Caddy logs do not show ACME failure for that hostname.

Useful certificate check:

```sh
echo | openssl s_client -connect dns-primary.fearn.cloud:443 -servername dns-primary.fearn.cloud 2>/dev/null | openssl x509 -noout -issuer -subject -dates
```

### REFLECT

Record hostname, certificate issuer, validity dates, and HTTP result.

## Cycle 7: Host Ingress Route Allows Trusted Source

### RED

From a Trusted VLAN source, choose a Host Ingress Route:

```sh
curl -vk https://wintermute.fearn.cloud/
```

### GREEN

If denied from Trusted:

- confirm the source client is actually in `10.20.0.0/24`,
- inspect generated Caddy route matcher,
- confirm Host management address is reachable from the Ingress VM.

### VERIFY

Expected result: the Trusted source reaches the Proxmox web UI route. A login
page, redirect, or Proxmox HTTP response is enough; do not authenticate unless
needed.

### REFLECT

Record source IP/range, Host route hostname, and observed status.

## Cycle 8: Host Ingress Route Denies Non-Trusted Source

### RED

From a non-Trusted client where practical:

```sh
curl -vk https://wintermute.fearn.cloud/
```

### GREEN

If the client can still reach the Host route:

- confirm the request did not originate from `10.20.0.0/24`,
- inspect Caddy route ordering,
- confirm the generated route ends with `respond 403`.

### VERIFY

Expected result: HTTP 403 from Caddy or equivalent denial before the Proxmox UI.

### REFLECT

Record the non-Trusted source range and observed denial. If no non-Trusted test
client is available, record why the check was not practical and leave the
acceptance criterion unchecked or partially noted.

## Completion Checklist

Only after the relevant VERIFY steps pass, update:

```text
.scratch/ingress-regeneration/issues/07-document-and-live-proof-ingress-regeneration-path.md
```

Record:

- Caddy module proof.
- Cloudflare token path proof, without secret value.
- `just ingress-regenerate` result.
- DNS hostname and answer IP.
- Service Ingress HTTPS/certificate result.
- Host Ingress Trusted result.
- Host Ingress non-Trusted denial result or caveat.
- Any follow-up issue paths.

Then check off only the acceptance criteria that were actually proven live.
