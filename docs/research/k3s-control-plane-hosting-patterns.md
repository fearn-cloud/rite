# K3s control-plane hosting patterns

## Scope

This note compares common self-hosted K3s control-plane topologies for a small
fleet of independent Proxmox Hosts. “Host” below means the physical Proxmox
failure domain, not merely a VM: placing two VMs on one Host does not make them
independent of a Host failure. That last point is an architectural inference
from the topology, rather than a claim made by K3s.

## Patterns

| Pattern | Shape | Availability and recovery boundary | Fit for four independent Hosts |
| --- | --- | --- | --- |
| Single K3s server | One server VM, running control-plane components and the default embedded SQLite datastore; agents/workloads may be elsewhere. | The server VM and its Host are a control-plane/datastore single point of failure. Repair or restore it from the datastore backup and the server token. | Good when control-plane downtime until operator repair is acceptable; least operational machinery. |
| Three-server, embedded-etcd HA | Three K3s server VMs; each combines Kubernetes control-plane services with one embedded etcd member. Put one on each of three Hosts. | Three is the normal smallest odd quorum: one server/Host can fail while quorum remains. Losing two prevents quorum. Retain snapshots and token for disaster recovery. | The usual small-fleet HA pattern. The fourth Host is available for a Time Authority VM, API endpoint, or workloads. |
| Role-separated embedded etcd | Dedicated embedded-etcd K3s servers plus dedicated control-plane K3s servers. | Separates etcd and API/control-plane roles, but makes a viable HA design consume more VMs and failure domains. The datastore still needs an odd, quorum-capable membership. | Usually too costly in a four-Host fleet unless the extra separation, not just HA, is the objective. |
| Multiple K3s servers with external datastore | Two or more K3s server VMs connect to an external etcd, PostgreSQL, MySQL, or MariaDB service. | Server availability is separate from datastore availability. The database is an independently operated recovery and availability boundary; K3s delegates its backup/restore to the database operator. | Appropriate only if that datastore already has a credible HA and backup design. It otherwise moves the single point of failure rather than removing it. |

K3s describes a single-server installation as fully functional, and uses SQLite
by default; SQLite cannot support a multiple-server cluster. Its official
guidance for embedded-etcd HA is three or more **odd-numbered** server nodes.
[K3s datastore options](https://docs.k3s.io/datastore)
[K3s embedded-etcd HA](https://docs.k3s.io/datastore/ha-embedded)

K3s also supports separating the embedded-etcd and control-plane roles by
disabling the corresponding components on a server. A control-plane-only node
cannot be the cluster's first server: an etcd-role node must exist first.
[K3s server roles](https://docs.k3s.io/installation/server-roles)

For an external datastore topology, K3s requires two or more server nodes and
supports etcd, PostgreSQL, MySQL, and MariaDB. The Kubernetes topology guidance
captures the general trade-off: stacked control plane plus etcd is simpler but
a node failure loses both replicas; separate etcd reduces that coupling but a
fully HA external-etcd layout normally needs three control-plane and three etcd
Hosts. [K3s external-database HA](https://docs.k3s.io/datastore/ha)
[Kubernetes HA topology options](https://kubernetes.io/docs/setup/production-environment/tools/kubeadm/ha-topology/)

## Stable API endpoint

Once there is more than one server, do not make agents and operators depend on
one server VM address. K3s recommends a stable registration address in front of
the servers; supported approaches include a TCP load balancer, round-robin DNS,
or a virtual/elastic IP. The address must be included in the server certificate
with `--tls-san`. [K3s external-database HA: fixed registration address](https://docs.k3s.io/datastore/ha#4-optional-configure-a-fixed-registration-address)

This endpoint is another availability component. In this fleet, a single
load-balancer VM is acceptable only if its outage is within the selected
control-plane recovery boundary; otherwise it needs a separately designed
failover scheme.

## Time Authority placement implication

For the three-server embedded-etcd pattern, place the three server VMs on three
different Proxmox Hosts and the Time Authority VM on the remaining Host. This
gives a clear anti-affinity rule: a single Host failure cannot remove both an
embedded-etcd server and the Time Authority. It does **not** promise time
service availability through the Time Authority Host's failure; clients follow
the separately chosen holdover-until-repair policy.

For a single-server pattern, state the exact control-plane Host in inventory
and place the Time Authority VM on any other Host. The result is anti-affinity,
not high availability: a Host failure still removes the only control plane.

## Recovery requirements that apply to every pattern

HA is not a backup plan. K3s says backup/restore differs by datastore: embedded
etcd uses its snapshot tooling, while external-database backup and restore are
the database operator's responsibility. For any K3s datastore restore, retain
the server token from `/var/lib/rancher/k3s/server/token`; K3s states that a
snapshot restored with a different token is unusable because the token encrypts
confidential datastore data. [K3s backup and restore](https://docs.k3s.io/datastore/backup-restore)

## Decision shortcut

Choose **one server plus tested restore** when modest downtime is explicitly
acceptable. Choose **three embedded-etcd servers on distinct Hosts** when
surviving one Host failure is required and the fleet can spend three Hosts on
the control plane. Choose **role separation or an external datastore** only
when its additional isolation or an already-operated database is a real
requirement; neither is a free upgrade to HA in a four-Host fleet.
