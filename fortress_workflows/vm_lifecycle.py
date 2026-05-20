from __future__ import annotations

from pathlib import Path

from fortress_inventory.model import load_inventory_tree
from fortress_tofu.generate import hcl_identifier
from fortress_workflows.runner import CommandPhase, ConfirmationGate, OperatorWorkflowPlan


def build_vm_lifecycle_plan(repo_root: Path, vm: str) -> OperatorWorkflowPlan:
    target_args = selected_vm_target_args(repo_root, vm)
    prepare_phase = _prepare_phase(repo_root, vm)
    return OperatorWorkflowPlan(
        id=f"vm-lifecycle:{vm}",
        steps=[
            prepare_phase,
            CommandPhase(
                id="tofu-plan",
                display_name="tofu plan",
                command=[
                    str(repo_root / "scripts" / "tofu-wrap"),
                    "plan",
                    "-var",
                    f"selected_vm={vm}",
                    *target_args,
                ],
                diagnostic_label=f"tofu plan failed for VM {vm}",
                streaming=True,
            ),
            ConfirmationGate(
                id="confirm-apply",
                display_name="Confirm apply",
                prompt=f"Type 'apply {vm}' to apply the selected-VM plan: ",
                required_input=f"apply {vm}",
            ),
            CommandPhase(
                id="tofu-apply",
                display_name="tofu apply",
                command=[
                    str(repo_root / "scripts" / "tofu-wrap"),
                    "apply",
                    "-var",
                    f"selected_vm={vm}",
                    *target_args,
                    "-auto-approve",
                ],
                diagnostic_label=f"tofu apply failed for VM {vm}",
                streaming=True,
            ),
            CommandPhase(
                id="configure",
                display_name="Configure",
                command=[str(repo_root / "scripts" / "vm-configure"), vm],
                diagnostic_label=f"Configure failed for VM {vm}",
                streaming=True,
            ),
        ],
    )


def selected_vm_target_args(repo_root: Path, vm: str) -> list[str]:
    model = load_inventory_tree(repo_root)
    host = model.vms.get(vm, {}).get("placement", {}).get("host")
    if not host:
        raise ValueError(f"VM {vm!r} has no placement.host")
    host_alias = hcl_identifier(host)
    return [
        "-target",
        f'module.vms_{host_alias}.proxmox_virtual_environment_file.cloud_init_user_data["{vm}"]',
        "-target",
        f'module.vms_{host_alias}.proxmox_virtual_environment_vm.vm["{vm}"]',
    ]


def _prepare_phase(repo_root: Path, vm: str) -> CommandPhase:
    vm_sops = repo_root / "inventory" / "vms" / f"{vm}.sops.yaml"
    if vm_sops.is_file() and _has_ssh_bootstrap_block(vm_sops):
        return CommandPhase(
            id="prepare-satisfied",
            display_name="Prepare Satisfied",
            command=[str(repo_root / "scripts" / "vm-prepare-satisfied"), vm],
            diagnostic_label=f"Prepare satisfaction failed for VM {vm}",
            streaming=True,
        )
    return CommandPhase(
        id="prepare",
        display_name="Prepare",
        command=[str(repo_root / "scripts" / "vm-prepare"), vm],
        diagnostic_label=f"Prepare failed for VM {vm}",
        streaming=True,
    )


def _has_ssh_bootstrap_block(path: Path) -> bool:
    stack: list[tuple[int, str]] = []
    for raw_line in path.read_text().splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        indent = len(raw_line) - len(raw_line.lstrip(" "))
        text = raw_line.strip()
        if ":" not in text or text.startswith("- "):
            continue
        key = text.split(":", 1)[0].strip().strip("\"'")
        while stack and stack[-1][0] >= indent:
            stack.pop()
        stack.append((indent, key))
        if [entry_key for _entry_indent, entry_key in stack] == ["ssh_keys", "bootstrap"]:
            return True
    return False
