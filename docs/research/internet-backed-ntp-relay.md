# Internet-backed local NTP relay options

## Decision context

This note evaluates a single dedicated VM on a different Host from the k3s
control plane. It obtains time from Internet-backed sources and serves the
whole fleet locally. The availability goal is deliberately modest: keep normal
NTP requests local; if the relay fails, Hosts and VMs retain their last
disciplined time until it is repaired. There is no requirement for a second
relay or for the relay to present itself as a valid source after it loses all
upstreams.

## Recommendation

Use **chrony (`chronyd`)** for the relay. Configure several independent
upstreams (or a pool), persist the drift estimate, permit UDP/123 only from the
fleet networks, and do **not** enable `local`/orphan mode for this single-relay
design. Monitor synchronization state, selected source, offset, and root
dispersion; alert if it loses synchronization or its error bounds grow.

Chrony matches the required shape directly: it is simultaneously an NTP client
and, after explicit `allow` rules, a server. Its documentation gives a minimal
multi-upstream, persisted-drift configuration and supports NTS for upstream
authentication where the selected providers offer it. [chrony configuration:
sources, pools, `iburst`, NTS, and client/server relationship](https://chrony-project.org/doc/4.6/chrony.conf.html)
[chrony configuration: serving is deny-by-default and enabled per
subnet](https://chrony-project.org/doc/4.6/chrony.conf.html#allow)

The important constraint is operational rather than package-specific: a
single, Internet-backed relay cannot provide authoritative time through both an
upstream outage and a relay failure. Persisting a learned clock frequency makes
the relay's *own* clock drift more predictably during a short upstream outage,
but it does not establish correctness. Chrony's `local` mode intentionally
lets a server appear synchronized when it is not; that conflicts with the
chosen holdover-until-repair policy. Let an unhealthy relay become
unsynchronized instead, so clients retain their current clocks rather than
accepting claimed time of unknown accuracy. [chrony drift and fallback-drift
semantics](https://chrony-project.org/doc/4.6/chrony.conf.html#driftfile)
[chrony isolated-network and `local`-reference behavior](https://chrony-project.org/doc/4.6/chrony.conf.html#isolated)

## Options

| Implementation | Local serving and upstreams | Holdover / recovery | Operations and security | Fit |
| --- | --- | --- | --- | --- |
| **chrony** | A `server` is a hierarchical upstream; `pool` can maintain a chosen number of responding sources. `allow <fleet CIDR>` changes the daemon from client-only to client-and-server. | Stores measured rate in a drift file; `fallbackdrift` uses longer-term averages. On restart, `iburst` speeds initial sampling. Do not use `local` here. | Small, explicit serving and monitoring ACLs; NTS is available for upstreams. `chronyc tracking` and `sources` expose selected source, stratum, offset, frequency and error-related state. | **Best default.** Direct configuration model and good status surface with little extra machinery. |
| **NTPsec `ntpd`** | `pool`/`server` configure persistent client associations; it serves NTP in the normal daemon role. | Traditional NTP discipline and drift handling; use multiple sources. It has a richer NTP control/statistics toolset. | NTPsec deliberately removes insecure broadcast/anycast and peer behavior, requires authentication for remote configuration, and implements NTS. Its broader toolset (`ntpq`, `ntpmon`, `ntpviz`) is useful but creates more configuration and monitoring choices than this relay needs. | Good, security-conscious alternative if the fleet already standardizes on NTPsec; otherwise more operational surface than needed. |
| **OpenNTPD** | `server`/`servers` can use one or all addresses for a name; the daemon can redistribute local time as an NTP server. | Persists a drift file and continuously adjusts clock frequency. | Very small configuration. Its distinctive protection is HTTPS/TLS *constraints*: NTP measurements outside the authenticated date range are discarded. Its official documentation exposes a much smaller observability/control interface (`ntpctl` socket and syslog) than chrony/NTPsec. | Viable minimalist choice, especially when its HTTPS constraints are desired. Less attractive if detailed health metrics and automated alerting are a priority. |
| **NTP Classic `ntpd`** | Capable NTP server/client, but not recommended for a new deployment. | Not evaluated as a candidate. | NTPsec exists specifically as a security-hardened successor and documents removal of legacy, insecure, or vulnerable functionality. | Exclude from the new design. |

The option descriptions above are supported by the projects' own manuals:
[chrony `server`/`pool` and source-selection documentation](https://chrony-project.org/doc/4.6/chrony.conf.html)
[chrony server ACL and monitoring-command ACL documentation](https://chrony-project.org/doc/4.6/chrony.conf.html#ntp-server)
[NTPsec `ntp.conf`](https://docs.ntpsec.org/latest/ntp_conf.html)
[NTPsec security changes and monitoring tools](https://docs.ntpsec.org/latest/ntpsec.html)
[OpenNTPD daemon manual](https://man.openbsd.org/ntpd)
[OpenNTPD configuration and HTTPS constraints](https://man.openbsd.org/ntpd.conf)

## Operational model for the recommended relay

### Upstreams

- Use at least three independent Internet sources. A `pool` is appropriate when
  provider addresses are expected to rotate; chrony supports a desired number
  of responding sources with `maxsources`. A list of named `server` entries is
  appropriate when the operator wants a deliberately fixed provider set.
  Avoid overly short polls against public services: chrony's default minimum
  poll is 64 seconds and its documentation warns that shorter intervals can be
  abuse. [chrony pool and `maxsources`](https://chrony-project.org/doc/4.6/chrony.conf.html#pool)
  [chrony polling guidance](https://chrony-project.org/doc/4.6/chrony.conf.html#server)
- Prefer upstream NTS only when the provider documents NTS support and the VM
  has a working trust store. NTS authenticates upstream time using TLS-based
  NTS-KE without a shared key file; it protects that leg, not unauthenticated
  LAN client requests. [chrony NTS](https://chrony-project.org/doc/4.6/chrony.conf.html#server)

### Serving and failure behavior

- Bind/firewall UDP/123 only on the intended fleet-facing interface and CIDRs;
  configure matching narrow `allow` CIDRs. Chrony's default is no NTP clients.
  Do not expose this VM to the Internet. [chrony server access control](https://chrony-project.org/doc/4.6/chrony.conf.html#allow)
- Point every fleet client at the relay, and remove public NTP sources from
  their ordinary client configuration if “requests stay local” is literal. A
  relay failure then leaves their system clocks running on their own already
  learned frequency until service returns. This is the intended availability
  boundary, not clock accuracy assurance.
- Persist the drift file on durable VM storage and preserve it through normal
  upgrades/reboots. It records the rate at which the system clock gains or
  loses time; chrony can also retain long-term fallback drift estimates.
  [chrony drift persistence](https://chrony-project.org/doc/4.6/chrony.conf.html#driftfile)
- On repair, restore/rebuild the VM from its normal image/configuration,
  confirm upstream synchronization, then allow clients to resample it. A
  rebuild needs no timing secret when upstreams are unauthenticated; with NTS,
  it needs ordinary CA trust, not a per-client shared key. The drift file is an
  optimization, not recovery-critical state.

### Monitoring and alerting

- Check `chronyc tracking` for synchronized state, reference ID, stratum,
  system offset, RMS offset, frequency, skew, root delay and root dispersion;
  check `chronyc sources` for reachability and which upstream was selected.
  The `tracking` command is the authoritative local status view documented by
  chrony. [chronyc tracking fields](https://chrony-project.org/doc/4.6/chronyc.html#tracking)
- Alert on: no selected/reachable upstream, unsynchronized status, unexpected
  upstream/source change, excessive root dispersion/offset, a stopped daemon,
  and UDP/123 being unreachable from a representative client VLAN. Record the
  last healthy sync time so an Internet outage and a relay outage are visibly
  different incidents.
- Do not enable remote `chronyc` access by default. It is local-only unless a
  command socket/address and `cmdallow` are configured; if central monitoring
  needs it, allow only the observability endpoint and firewall it as a
  management protocol. [chrony monitoring-command ACL](https://chrony-project.org/doc/4.6/chrony.conf.html#cmdallow)

### Upgrade and security burden

The ongoing burden is one small VM, an OS package update cadence, a narrow
firewall rule, source-health alerting, and a periodic recovery drill. Treat the
relay as network infrastructure: test the configuration before restart, retain
the previous package/configuration for rollback, and verify that it regains a
real upstream before declaring recovery complete. There is no private LAN NTP
authentication requirement in this design; network segmentation and source-IP
ACLs are the practical controls. If the threat model includes a compromised
fleet client able to spoof or poison local UDP/123 traffic, add client/server
authentication as a separate decision rather than assuming Internet-side NTS
covers the LAN.

## Burden comparison

| Design | Additional infrastructure | Routine work | Failure response | Why it is not selected now |
| --- | --- | --- | --- | --- |
| One chrony relay | One Operational VM on a non-k3s-control-plane Host | Patch VM, check four upstreams and one local service, review alerts | Repair one VM; clients hold over | Selected: meets the stated boundary with the least new machinery. |
| Two relays with client failover | Second VM/Host plus DNS or two client entries | Everything above twice; test failover and avoid circular synchronization | Automatic relay failover | Outside the stated “hold over until repair” requirement. |
| Relay plus GNSS/reference clock | Hardware, antenna/site work, reference-clock integration | Hardware health, sky view, leap/receiver handling, plus VM/service work | Can remain independent of Internet, subject to hardware health | Outside the Internet-backed requirement. |

## Implementation decision to carry forward

Adopt a dedicated **chrony Time Authority VM** on a different Host from the
k3s control plane. It serves only fleet CIDRs; it selects from multiple
Internet-backed upstreams; its configuration preserves drift data; and it
intentionally does not advertise a fabricated local reference on upstream
loss. Fleet clients use it as their only normal NTP source and therefore hold
their last disciplined time if the VM is unavailable until the Operator repairs
it.
