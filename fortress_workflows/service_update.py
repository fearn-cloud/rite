from __future__ import annotations

import shlex
import sys
from pathlib import Path

from fortress_inventory.entity_graph import InventoryEntityGraph
from fortress_inventory.model import load_inventory_tree
from fortress_services.deploy import service_start_units
from fortress_workflows.runner import CommandPhase, ConfirmationGate, OperatorWorkflowPlan, WorkflowResult


def build_service_update_plan(repo_root: Path, service: str) -> OperatorWorkflowPlan:
    model = load_inventory_tree(repo_root)
    selected_service = model.services.get(service)
    if selected_service is None:
        raise ValueError(f"Service {service!r} is not declared")

    graph = InventoryEntityGraph(model)
    backend_vm_name = graph.service_backend_vm_name(service)
    if not backend_vm_name:
        raise ValueError(f"Service {service!r} has no backend.vm")
    if backend_vm_name not in model.vms:
        raise ValueError(f"Backend VM {backend_vm_name!r} for Service {service!r} is not declared")

    units = service_update_units(selected_service)
    if not units:
        raise ValueError(f"Service {service!r} has no fortress-owned systemd units to update")

    return OperatorWorkflowPlan(
        id=f"service-update:{service}",
        steps=[
            CommandPhase(
                id="service-deploy",
                display_name="Service Deploy",
                command=[str(repo_root / "scripts" / "service-deploy"), service],
                diagnostic_label=f"Service Deploy failed for Service {service}",
                streaming=True,
            ),
            ConfirmationGate(
                id="confirm-restart",
                display_name="Confirm restart",
                prompt=f"Type 'update {service}' to restart Service {service} units: ",
                required_input=f"update {service}",
            ),
            CommandPhase(
                id="restart-service-units",
                display_name="Restart Service units",
                command=[
                    str(repo_root / "scripts" / "vm-shell"),
                    backend_vm_name,
                    "--",
                    "sudo",
                    "systemctl",
                    "restart",
                    *units,
                ],
                diagnostic_label=f"Service unit restart failed for Service {service}",
                streaming=True,
            ),
            CommandPhase(
                id="verify-service-units-active",
                display_name="Verify Service units are active",
                command=[
                    str(repo_root / "scripts" / "vm-shell"),
                    backend_vm_name,
                    "--",
                    "sh",
                    "-lc",
                    service_units_active_check_command(units),
                ],
                diagnostic_label=f"Service unit active check failed for Service {service}",
                streaming=True,
            ),
        ],
    )


def service_update_units(service: dict) -> list[str]:
    deploy = service.get("deploy", {})
    if deploy.get("type") == "native":
        unit = deploy.get("service_name")
        return [unit] if unit else []
    return service_start_units(service)


def service_units_active_check_command(units: list[str]) -> str:
    unit_words = " ".join(shlex.quote(unit) for unit in units)
    return f'for unit in {unit_words}; do sudo systemctl is-active --quiet "$unit" || exit $?; done'


def render_service_update_result(plan: OperatorWorkflowPlan, result: WorkflowResult, service: str) -> None:
    if result.success:
        return
    denied_gates = {gate.step_id for gate in result.gate_results if gate.status == "denied"}
    for step in plan.steps:
        if isinstance(step, ConfirmationGate) and step.id in denied_gates:
            print(f"Service Update denied for Service {service}", file=sys.stderr)
            return
    failed_phases = {phase.step_id: phase for phase in result.phase_results if phase.status == "failed"}
    for step in plan.steps:
        if isinstance(step, CommandPhase) and step.id in failed_phases:
            detail = failed_phases[step.id].failure_detail
            suffix = f": {detail}" if detail else ""
            print(f"{step.diagnostic_label}{suffix}", file=sys.stderr)
            return
