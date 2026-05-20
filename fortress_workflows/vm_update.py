from __future__ import annotations

import shlex
from pathlib import Path

from fortress_inventory.entity_graph import InventoryEntityGraph
from fortress_inventory.model import load_inventory_tree
from fortress_inventory.service_runtime_intent import analyze_service_runtime_intent
from fortress_workflows.runner import CommandPhase, ConfirmationGate, OperatorWorkflowPlan
from fortress_workflows.service_update import service_units_active_check_command, service_update_units


def build_vm_update_plan(repo_root: Path, vm: str, reboot: bool = False) -> OperatorWorkflowPlan:
    model = load_inventory_tree(repo_root)
    if vm not in model.vms:
        raise ValueError(f"VM {vm!r} is not declared")

    steps = [
        CommandPhase(
            id="configure",
            display_name="VM Configure",
            command=[str(repo_root / "scripts" / "vm-configure"), vm],
            diagnostic_label=f"VM Configure failed for VM {vm}",
            streaming=True,
        ),
        CommandPhase(
            id="software-advancement",
            display_name="Routine Software Advancement",
            command=[str(repo_root / "scripts" / "vm-routine-software-advance"), vm],
            diagnostic_label=f"Routine Software Advancement failed for VM {vm}",
            streaming=True,
        ),
    ]
    if reboot:
        graph = InventoryEntityGraph(model)
        impact = graph.vm_update_reboot_impact(vm)
        resident_services = impact.resident_service_names if impact else ()
        steps.extend(
            _vm_reboot_steps(
                repo_root,
                vm,
                model.services,
                resident_services,
                runtime_intent=analyze_service_runtime_intent(model),
            )
        )

    return OperatorWorkflowPlan(
        id=f"vm-update:{vm}",
        steps=steps,
    )


def _vm_reboot_steps(repo_root, vm, services, resident_service_names, runtime_intent):
    steps = [
        ConfirmationGate(
            id="confirm-vm-reboot",
            display_name="Confirm VM reboot",
            prompt=(
                f"Resident fortress-managed Services on VM {vm}: "
                f"{_format_service_names(resident_service_names)}\n"
                f"Type 'reboot {vm}' to stop those Services, reboot VM {vm}, and restore them: "
            ),
            required_input=f"reboot {vm}",
        )
    ]
    service_units = []
    for service_name in resident_service_names:
        units = service_update_units(services[service_name], runtime_intent=runtime_intent)
        if not units:
            raise ValueError(f"Service {service_name!r} has no fortress-owned systemd units to stop before VM reboot")
        service_units.append((service_name, units))
        stop_units = list(reversed(units))
        steps.append(
            CommandPhase(
                id=f"stop-service:{service_name}",
                display_name=f"Stop Service {service_name}",
                command=[
                    str(repo_root / "scripts" / "vm-shell"),
                    vm,
                    "--",
                    "sudo",
                    "systemctl",
                    "stop",
                    *stop_units,
                ],
                diagnostic_label=f"Service stop failed for Service {service_name} before VM reboot",
                streaming=True,
            )
        )
        steps.append(
            CommandPhase(
                id=f"verify-service-stopped:{service_name}",
                display_name=f"Verify Service {service_name} stopped",
                command=[
                    str(repo_root / "scripts" / "vm-shell"),
                    vm,
                    "--",
                    "sh",
                    "-lc",
                    service_units_inactive_check_command(stop_units),
                ],
                diagnostic_label=f"Service stopped-state check failed for Service {service_name} before VM reboot",
                streaming=True,
            )
        )

    steps.extend(
        [
            CommandPhase(
                id="reboot-vm",
                display_name="Reboot VM",
                command=[str(repo_root / "scripts" / "vm-shell"), vm, "--", "sudo", "systemctl", "reboot"],
                diagnostic_label=f"VM reboot failed for VM {vm}",
                streaming=True,
            ),
            CommandPhase(
                id="verify-vm-reachable",
                display_name="Verify VM reachable",
                command=[str(repo_root / "scripts" / "vm-shell"), vm, "--", "true"],
                diagnostic_label=f"VM reachability check failed for VM {vm} after reboot",
                streaming=True,
            ),
        ]
    )
    for service_name, units in service_units:
        steps.append(
            CommandPhase(
                id=f"restore-service:{service_name}",
                display_name=f"Restore Service {service_name}",
                command=[
                    str(repo_root / "scripts" / "vm-shell"),
                    vm,
                    "--",
                    "sudo",
                    "systemctl",
                    "start",
                    *units,
                ],
                diagnostic_label=f"Service restore failed for Service {service_name} after VM reboot",
                streaming=True,
            )
        )
        steps.append(
            CommandPhase(
                id=f"verify-service-active:{service_name}",
                display_name=f"Verify Service {service_name} active",
                command=[
                    str(repo_root / "scripts" / "vm-shell"),
                    vm,
                    "--",
                    "sh",
                    "-lc",
                    service_units_active_check_command(units),
                ],
                diagnostic_label=f"Service active check failed for Service {service_name} after VM reboot",
                streaming=True,
            )
        )
    return steps


def service_units_inactive_check_command(units):
    unit_words = " ".join(shlex.quote(unit) for unit in units)
    return f'for unit in {unit_words}; do sudo systemctl is-active --quiet "$unit" && exit 1 || true; done'


def _format_service_names(service_names):
    return ", ".join(service_names) if service_names else "(none)"
