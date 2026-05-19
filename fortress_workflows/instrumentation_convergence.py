from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from fortress_inventory.entity_graph import InventoryEntityGraph
from fortress_inventory.model import load_inventory_tree
from fortress_workflows.runner import CommandPhase, OperatorWorkflowPlan, WorkflowResult


OBSERVABILITY_SERVICE_NAME = "observability"


def build_instrumentation_convergence_plan(repo_root: Path) -> OperatorWorkflowPlan:
    model = load_inventory_tree(repo_root)
    if OBSERVABILITY_SERVICE_NAME not in model.services:
        raise ValueError(f"Service {OBSERVABILITY_SERVICE_NAME!r} is not declared")

    graph = InventoryEntityGraph(model)
    instrumented_vm_facts = graph.instrumented_vm_facts()
    live_absent_vm_names = _live_absent_vm_names(repo_root, model, instrumented_vm_facts)
    steps = [
        CommandPhase(
            id=f"vm-configure:{fact.vm_name}",
            display_name="VM Configure",
            command=[str(repo_root / "scripts" / "vm-configure"), fact.vm_name],
            diagnostic_label=f"VM Configure failed for VM {fact.vm_name}",
            streaming=True,
        )
        for fact in instrumented_vm_facts
        if fact.vm_name not in live_absent_vm_names
    ]
    service_update_command = [
        str(repo_root / "scripts" / "service-update"),
        OBSERVABILITY_SERVICE_NAME,
        "--auto-confirm",
    ]
    if live_absent_vm_names:
        service_update_command = [
            "env",
            f"FORTRESS_OBSERVABILITY_EXCLUDED_VMS={','.join(live_absent_vm_names)}",
            *service_update_command,
        ]
    steps.append(
        CommandPhase(
            id="service-update:observability",
            display_name="Observability Service Update",
            command=service_update_command,
            diagnostic_label="Observability Service Update failed",
            streaming=True,
        )
    )
    return OperatorWorkflowPlan(id="instrumentation-convergence", steps=steps)


def render_instrumentation_convergence_result(plan: OperatorWorkflowPlan, result: WorkflowResult) -> None:
    if result.success:
        return
    failed_phases = {phase.step_id: phase for phase in result.phase_results if phase.status == "failed"}
    for step in plan.steps:
        if isinstance(step, CommandPhase) and step.id in failed_phases:
            detail = failed_phases[step.id].failure_detail
            suffix = f": {detail}" if detail else ""
            print(f"{step.diagnostic_label}{suffix}", file=sys.stderr)
            return


def _live_absent_vm_names(repo_root: Path, model, instrumented_vm_facts) -> tuple[str, ...]:
    absent = []
    for fact in instrumented_vm_facts:
        vm = model.vms[fact.vm_name]
        vmid = vm.get("vmid")
        host_name = (vm.get("placement") or {}).get("host")
        if vmid is None or not host_name:
            continue
        result = subprocess.run(
            [
                str(repo_root / "scripts" / "host-shell"),
                host_name,
                "--",
                "qm",
                "config",
                str(vmid),
            ],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if result.returncode == 0:
            continue
        detail = (result.stderr or result.stdout).strip()
        if _looks_like_absent_qm_config(detail):
            print(f"Skipping VM {fact.vm_name}: VMID {vmid} is absent on Host {host_name}")
            absent.append(fact.vm_name)
            continue
        raise ValueError(
            f"failed to check live VM {fact.vm_name} VMID {vmid} on Host {host_name}: {detail or result.returncode}"
        )
    return tuple(absent)


def _looks_like_absent_qm_config(output: str) -> bool:
    normalized = output.lower()
    return "configuration file" in normalized and "does not exist" in normalized
