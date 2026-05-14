Status: ready-for-human

## Parent

.scratch/initial-building-blocks/issues/10-caddy-ingress-ingress-regenerator.md

## What to build

Update the operator-facing documentation and perform the live proof for the Ingress Regeneration path. This slice stays human-owned because it requires real Cloudflare credentials, live DNS-01 certificate issuance, reachable VMs, and LAN validation.

The completed slice should update the new-Service and DNS runbooks plus relevant architecture notes, reconcile the parent issue 10 acceptance criteria against the split implementation work, run the live Caddy/Cloudflare/Pi-hole proof, and record any remaining operator caveats.

## Acceptance criteria

- [ ] `runbooks/new-service.md` explains how an Operator declares a new Ingress-enabled Service and runs Ingress Regeneration.
- [ ] The DNS runbook explains generated Ingress DNS Records, Ingress DNS Targets, the fortress-owned dnsmasq file, and what manual Pi-hole records remain outside fortress ownership.
- [ ] Architecture notes describe Service Ingress, Host Ingress Routes, Caddy generated-route ownership, and generated DNS ownership consistently with the ADRs.
- [ ] Parent issue 10 acceptance criteria are updated or commented with the split between AFK implementation issues and live human proof.
- [ ] Live proof issues a real Let's Encrypt DNS-01 certificate through Cloudflare for an Ingress hostname.
- [ ] Live proof reaches at least one Service Ingress hostname from the LAN with the expected certificate.
- [ ] Live proof reaches a Proxmox web UI Host Ingress Route from a Trusted source and confirms non-Trusted source ranges are denied where practical.
- [ ] Any live-only caveats or follow-up issues are recorded in the local issue tracker.

## Blocked by

- .scratch/ingress-regeneration/issues/06-make-ingress-regenerate-push-and-reload-generated-files.md
- .scratch/initial-building-blocks/issues/09-pi-hole-unbound-dns-vm.md

## Live proof checklist

Do not mark the live proof acceptance criteria complete until these checks have
actually run against live infrastructure.

- Confirm the Cloudflare API token for `fearn.cloud` is present only in the
  Ingress Service Sibling SOPS File and is deployed only to the Caddy VM
  environment.
- Run `just service-deploy internal-ingress` if the Caddy Native Service or
  Cloudflare environment changed.
- Run `just service-deploy dns-primary` if Pi-hole dnsmasq compatibility or the
  DNS Service declaration changed.
- Deploy or choose one Ingress-enabled Service with a LAN-only hostname.
- Run `just ingress-regenerate`.
- From a LAN client using fortress DNS, confirm the Service hostname resolves to
  the Ingress VM address and reaches the Service with the expected certificate.
- Confirm Caddy has issued a real Let's Encrypt DNS-01 certificate through
  Cloudflare for that hostname.
- From a Trusted source, reach a Proxmox web UI Host Ingress Route.
- From a non-Trusted source, confirm the same Host Ingress Route is denied where
  the available VLAN/client setup makes that practical.

## Live-only caveats

- Certificate issuance can be rate-limited by Let's Encrypt; use an existing
  low-risk Ingress hostname when possible.
- DNS validation depends on the live Cloudflare zone state and the token's
  scoped permissions, neither of which can be proven by local tests.
- LAN validation depends on the operator workstation's DNS path. A client using
  public DNS or Guest DNS will not prove the fortress Pi-hole record path.
- Non-Trusted denial requires a real client or route from a non-Trusted range;
  record the source range and observed status when performing the check.
