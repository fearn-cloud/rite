Status: ready-for-human

## What to build

Teach Ingress Regeneration and workflow planning to consume Service Ingress Routes end to end.

When a Service declares one or more Service Ingress Routes, Caddy route generation and Ingress DNS Record generation should produce one route and one DNS record per route hostname. Service launch and Service Group launch should require Ingress Regeneration when any launched Service has one or more Service Ingress Routes. Existing Host Ingress Routes and NAS Ingress Routes must keep their current behavior.

Do not edit Hermes implementation files as part of this issue.

## Acceptance criteria

- [ ] Caddy route model generation reads Service Ingress Routes and emits one route per declared route.
- [ ] Generated Service route targets use the route's resolved Backend VM static IPv4 address and VM host Published Port.
- [ ] Generated Ingress DNS Records include every Service Ingress Route hostname and remain ordered deterministically by hostname.
- [ ] A Service with two Service Ingress Routes renders two distinct Caddy server blocks and two DNS records.
- [ ] Service launch plans include Ingress Regeneration when the selected Service has one or more Service Ingress Routes.
- [ ] Service Group launch plans include Ingress Regeneration when any launched member Service has one or more Service Ingress Routes.
- [ ] Fast tests cover multi-route Service generation and preserve existing Host/NAS route generation behavior.

## Blocked by

- .scratch/service-ingress-routes/issues/01-service-ingress-route-inventory-contract.md
