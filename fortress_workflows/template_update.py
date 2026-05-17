from __future__ import annotations

from pathlib import Path

from fortress_inventory.entity_graph import InventoryEntityGraph
from fortress_inventory.model import load_inventory_tree
from fortress_workflows.runner import CommandPhase, OperatorWorkflowPlan


class TemplateUpdatePlanError(Exception):
    pass


def build_template_update_plan(
    repo_root: Path,
    host_name: str,
    template_name: str,
    keep_on_fail: bool,
) -> OperatorWorkflowPlan:
    inventory = load_inventory_tree(repo_root)
    graph = InventoryEntityGraph(inventory)
    if template_name not in inventory.templates:
        raise TemplateUpdatePlanError(
            f"Template {template_name!r} is not declared at "
            f"{repo_root / 'inventory' / 'templates' / f'{template_name}.yaml'}"
        )

    if host_name == "all":
        host_names = graph.host_names_declaring_template(template_name)
        if not host_names:
            raise TemplateUpdatePlanError(f"No Host declares Template {template_name} under proxmox.templates")
        return OperatorWorkflowPlan(
            id=f"template-update:all:{template_name}",
            steps=[
                step
                for selected_host_name in host_names
                for step in template_update_steps(
                    repo_root,
                    selected_host_name,
                    template_name,
                    keep_on_fail,
                    include_host_in_step_id=True,
                )
            ],
        )

    host = inventory.hosts.get(host_name)
    if host is None:
        raise TemplateUpdatePlanError(
            f"Host {host_name!r} is not declared at {repo_root / 'inventory' / 'hosts' / f'{host_name}.yaml'}"
        )
    if template_name not in (host.get("proxmox", {}).get("templates", []) or []):
        raise TemplateUpdatePlanError(f"Host {host_name} does not declare Template {template_name} under proxmox.templates")

    return OperatorWorkflowPlan(
        id=f"template-update:{host_name}:{template_name}",
        steps=template_update_steps(repo_root, host_name, template_name, keep_on_fail),
    )


def template_update_steps(
    repo_root: Path,
    host_name: str,
    template_name: str,
    keep_on_fail: bool,
    include_host_in_step_id: bool = False,
):
    return [
        CommandPhase(
            id=f"template-rebuild:{host_name}" if include_host_in_step_id else "template-rebuild",
            display_name="Template Rebuild",
            command=[
                str(repo_root / "scripts" / "templates-build"),
                host_name,
                template_name,
                "--replace-existing",
            ],
            diagnostic_label=f"Template Rebuild {template_name}@{host_name}",
            streaming=True,
        ),
        CommandPhase(
            id=f"template-verify:{host_name}" if include_host_in_step_id else "template-verify",
            display_name="Template Verification",
            command=[
                str(repo_root / "scripts" / "template-verify"),
                f"host={host_name}",
                f"template={template_name}",
                f"keep_on_fail={bool_arg(keep_on_fail)}",
            ],
            diagnostic_label=f"Template Verification {template_name}@{host_name}",
            streaming=True,
        ),
    ]


def template_update_lineage_report(repo_root: Path, template_name: str):
    graph = InventoryEntityGraph(load_inventory_tree(repo_root))
    lines = [
        f"Template Update lineage for {template_name}:",
        "Existing durable VMs are lineage context only; Template Update does not change them.",
    ]
    lineage_vms = graph.template_lineage_vms(template_name)
    if not lineage_vms:
        lines.append("- no existing VMs declare this Template")
        return lines
    lines.extend(
        f"- {vm.vm_name} (vmid {vm.vmid}, host {vm.placement_host_name})"
        for vm in lineage_vms
    )
    return lines


def bool_arg(value: bool) -> str:
    return "true" if value else "false"
