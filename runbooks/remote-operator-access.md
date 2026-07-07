# Remote Operator Access

Use this runbook to bring up the immediate Hosted Tailnet path for running fortress Operator workflows away from the local network.

## Tailnet Subnet Router

The initial Tailnet Subnet Router is `tailnet-subnet-router-vm`, an ordinary VM on the `molly` Host attached to the Trusted VLAN at `10.20.0.20/24`.

Create a Tailscale auth key for this VM, then store it in the VM's Sibling SOPS File:

```yaml
tailnet:
  auth_key:
    type: tailscale_auth_key
    created: 2026-05-12T00:00:00Z
    value: tskey-auth-...
```

Bring the VM up through the ordinary VM lifecycle:

```sh
just vm-up vm=tailnet-subnet-router-vm
```

After Configure completes, approve the advertised subnet routes in the Tailscale admin console. During early bring-up, this VM advertises all fortress VLANs so the Operator can recover or continue implementation work remotely.

If `tailnet_subnet_router.advertise_exit_node` is enabled in Inventory, also approve the advertised exit node in the Tailscale admin console. Only Remote Operator Workstations should be eligible to use it.

For a Remote Operator Session on an untrusted public network:

1. Connect the Remote Operator Workstation to the Hosted Tailnet.
2. Manually select `tailnet-subnet-router-vm` as the exit node for the session.
3. Confirm fortress hostnames resolve through the DNS VMs.
4. Run the needed Operator Workflows.
5. Disable exit-node use when the Remote Operator Session ends.

The exit node secures general IPv4 internet egress through the fortress Trusted VLAN. DNS still belongs to the DNS VMs; the Tailnet Subnet Router is not a resolver.

The router VM is routing-only. Do not use it as a remote shell, editor, or credential-holding Operator environment.
