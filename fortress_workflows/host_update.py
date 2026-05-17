from __future__ import annotations

from pathlib import Path

from fortress_inventory.entity_graph import InventoryEntityGraph, InventoryEntityGraphError
from fortress_inventory.model import load_inventory_tree
from fortress_workflows.host_readiness import HOST_CONFIGURE_TAGS
from fortress_workflows.runner import CommandPhase, ConfirmationGate, OperatorWorkflowPlan


HOST_SOFTWARE_ADVANCEMENT_COMMAND = (
    "sudo apt-get update && "
    "sudo env DEBIAN_FRONTEND=noninteractive apt-get --assume-yes --with-new-pkgs --no-remove upgrade"
)


class HostUpdatePlanError(Exception):
    pass


def build_host_update_plan(repo_root: Path, host_name: str, reboot: bool = False) -> OperatorWorkflowPlan:
    inventory = load_inventory_tree(repo_root)
    if host_name not in inventory.hosts:
        raise HostUpdatePlanError(
            f"Host {host_name!r} is not declared at {repo_root / 'inventory' / 'hosts' / f'{host_name}.yaml'}"
        )

    steps = [
        CommandPhase(
            id="host-configure",
            display_name="Host Configure",
            command=[
                str(repo_root / "scripts" / "host-configure"),
                host_name,
                ",".join(HOST_CONFIGURE_TAGS),
            ],
            diagnostic_label=f"Host Configure failed for Host {host_name}",
            streaming=True,
        ),
        CommandPhase(
            id="software-advancement",
            display_name="Host Software Advancement",
            command=[
                str(repo_root / "scripts" / "host-shell"),
                host_name,
                "--",
                "bash",
                "-lc",
                HOST_SOFTWARE_ADVANCEMENT_COMMAND,
            ],
            diagnostic_label=f"Host Software Advancement failed for Host {host_name}",
            streaming=True,
        ),
    ]
    if reboot:
        steps.extend(_host_reboot_steps(repo_root, host_name, inventory))

    return OperatorWorkflowPlan(
        id=f"host-update:{host_name}",
        steps=steps,
    )


def _host_reboot_steps(repo_root: Path, host_name: str, inventory) -> list[CommandPhase | ConfirmationGate]:
    try:
        impact = InventoryEntityGraph(inventory).host_update_reboot_impact(host_name)
    except InventoryEntityGraphError as error:
        raise HostUpdatePlanError(str(error)) from error
    impacted_vms = impact.ordinary_vms
    prompt = _host_reboot_prompt(host_name, impacted_vms, impact.resident_service_names)
    steps: list[CommandPhase | ConfirmationGate] = [
        ConfirmationGate(
            id="confirm-host-reboot",
            display_name="Confirm Host reboot",
            prompt=prompt,
            required_input=f"reboot {host_name}",
        )
    ]
    for vm in impacted_vms:
        steps.append(
            CommandPhase(
                id=f"shutdown-vm:{vm.vm_name}",
                display_name=f"Shutdown VM {vm.vm_name}",
                command=[
                    str(repo_root / "scripts" / "host-shell"),
                    host_name,
                    "--",
                    "sudo",
                    "qm",
                    "shutdown",
                    str(vm.vmid),
                    "--timeout",
                    "300",
                ],
                diagnostic_label=f"Graceful shutdown failed for VM {vm.vm_name} on Host {host_name}",
                streaming=True,
            )
        )
    steps.extend(
        [
            CommandPhase(
                id="reboot-host",
                display_name="Reboot Host",
                command=[
                    str(repo_root / "scripts" / "host-shell"),
                    host_name,
                    "--",
                    "sudo",
                    "systemctl",
                    "reboot",
                ],
                diagnostic_label=f"Host reboot command failed for Host {host_name}",
                streaming=True,
            ),
            CommandPhase(
                id="verify-host-reachable",
                display_name="Verify Host reachable",
                command=[str(repo_root / "scripts" / "host-shell"), host_name, "--", "true"],
                diagnostic_label=f"Host reachability verification failed for Host {host_name}",
                streaming=True,
            ),
        ]
    )
    for vm in impacted_vms:
        steps.append(
            CommandPhase(
                id=f"start-vm:{vm.vm_name}",
                display_name=f"Start VM {vm.vm_name}",
                command=[
                    str(repo_root / "scripts" / "host-shell"),
                    host_name,
                    "--",
                    "sudo",
                    "qm",
                    "start",
                    str(vm.vmid),
                ],
                diagnostic_label=f"VM restoration failed for VM {vm.vm_name} on Host {host_name}",
                streaming=True,
            )
        )
    return steps


def _host_reboot_prompt(host_name: str, impacted_vms, resident_service_names: tuple[str, ...]) -> str:
    vm_names = ", ".join(vm.vm_name for vm in impacted_vms) or "none"
    service_names = ", ".join(resident_service_names) or "none"
    return (
        f"Ordinary VMs impacted on Host {host_name}: {vm_names}\n"
        f"Resident Services impacted through those VMs: {service_names}\n"
        f"Type 'reboot {host_name}' to confirm the Host Update maintenance-window reboot: "
    )
