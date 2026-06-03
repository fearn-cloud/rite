"""Pure Restore Drill planning from Inventory and selected PBS restore-point facts."""

from dataclasses import dataclass
import datetime as dt


DEFAULT_DRILL_NETWORK = "drill-network"


@dataclass(frozen=True)
class SelectedRestorePoint:
    backup_target_vm_name: str
    snapshot_id: str
    completed_at: dt.datetime


@dataclass(frozen=True)
class RestoredDrillVmPlan:
    name: str
    lifecycle: str
    placement: dict
    network: str


@dataclass(frozen=True)
class RestoreDrillPlan:
    workflow_family: str
    backup_target_vm_name: str
    restore_point: SelectedRestorePoint
    restored_vm: RestoredDrillVmPlan
    production_ingress: str = "disabled"
    production_dns: str = "disabled"
    production_nas_mutation: str = "disabled"
    protected_nas_datasets: tuple[str, ...] = ()
    service_volume_warnings: tuple[str, ...] = ()
    access: str = "operator_only"
    access_reason: str = "restored production secrets may be present"
    warnings: tuple[str, ...] = ()


def plan_restore_drill(model, restore_point, placement):
    backup_target = model.vms.get(restore_point.backup_target_vm_name)
    if not backup_target or (backup_target.get("backup") or {}).get("enabled") is not True:
        raise ValueError(
            f"Restore Drill requires a Backup Target restore point for {restore_point.backup_target_vm_name}"
        )
    if placement.get("host") not in model.hosts:
        raise ValueError("Restore Drill placement.host must select an Inventory Host")
    restored_vm_name = f"restored-drill-{restore_point.backup_target_vm_name}"
    if restored_vm_name in model.vms:
        raise ValueError(f"Restored Drill VM identity collides with production VM {restored_vm_name}")
    protected_nas_datasets = _protected_nas_datasets(backup_target, model)
    service_volume_warnings = _service_volume_warnings(restore_point.backup_target_vm_name, backup_target, model)
    warnings = tuple(
        f"Production NAS-backed Dataset {dataset_name} is not mutated by Restore Drill planning"
        for dataset_name in protected_nas_datasets
    )
    return RestoreDrillPlan(
        workflow_family="restore-drill",
        backup_target_vm_name=restore_point.backup_target_vm_name,
        restore_point=restore_point,
        restored_vm=RestoredDrillVmPlan(
            name=restored_vm_name,
            lifecycle="generated_disposable",
            placement=dict(placement),
            network=DEFAULT_DRILL_NETWORK,
        ),
        production_ingress="disabled",
        production_dns="disabled",
        production_nas_mutation="disabled",
        protected_nas_datasets=protected_nas_datasets,
        service_volume_warnings=service_volume_warnings,
        access="operator_only",
        access_reason="restored production secrets may be present",
        warnings=warnings,
    )


def render_restore_drill_plan(plan):
    lines = [
        f"Restore Drill plan for Backup Target {plan.backup_target_vm_name}\n"
        f"Selected restore point: {plan.restore_point.snapshot_id}\n"
        f"Restored Drill VM: {plan.restored_vm.name}\n"
        f"Placement: Host {plan.restored_vm.placement.get('host')}, "
        f"storage {plan.restored_vm.placement.get('storage')}\n"
        f"Network: {plan.restored_vm.network}\n"
        f"Production ingress: {plan.production_ingress}\n"
        f"Production DNS: {plan.production_dns}\n"
        f"Access: {plan.access} because {plan.access_reason}\n"
    ]
    for warning in plan.warnings:
        lines.append(f"Warning: {warning}\n")
    for warning in plan.service_volume_warnings:
        lines.append(f"Warning: Service {warning}; Restore Drill planning does not grant write access\n")
    return "".join(lines)


def restore_drill_plan_to_dict(plan):
    return {
        "workflow_family": plan.workflow_family,
        "backup_target_vm_name": plan.backup_target_vm_name,
        "restore_point": {
            "backup_target_vm_name": plan.restore_point.backup_target_vm_name,
            "snapshot_id": plan.restore_point.snapshot_id,
            "completed_at": plan.restore_point.completed_at.isoformat(),
        },
        "restored_vm": {
            "name": plan.restored_vm.name,
            "lifecycle": plan.restored_vm.lifecycle,
            "placement": plan.restored_vm.placement,
            "network": plan.restored_vm.network,
        },
        "production_ingress": plan.production_ingress,
        "production_dns": plan.production_dns,
        "production_nas_mutation": plan.production_nas_mutation,
        "protected_nas_datasets": list(plan.protected_nas_datasets),
        "service_volume_warnings": list(plan.service_volume_warnings),
        "access": plan.access,
        "access_reason": plan.access_reason,
        "warnings": list(plan.warnings),
    }


def restore_drill_plan_from_dict(raw):
    restore_point = raw["restore_point"]
    restored_vm = raw["restored_vm"]
    return RestoreDrillPlan(
        workflow_family=raw["workflow_family"],
        backup_target_vm_name=raw["backup_target_vm_name"],
        restore_point=SelectedRestorePoint(
            backup_target_vm_name=restore_point["backup_target_vm_name"],
            snapshot_id=restore_point["snapshot_id"],
            completed_at=dt.datetime.fromisoformat(restore_point["completed_at"]),
        ),
        restored_vm=RestoredDrillVmPlan(
            name=restored_vm["name"],
            lifecycle=restored_vm["lifecycle"],
            placement=restored_vm["placement"],
            network=restored_vm["network"],
        ),
        production_ingress=raw.get("production_ingress", "disabled"),
        production_dns=raw.get("production_dns", "disabled"),
        production_nas_mutation=raw.get("production_nas_mutation", "disabled"),
        protected_nas_datasets=tuple(raw.get("protected_nas_datasets", ())),
        service_volume_warnings=tuple(raw.get("service_volume_warnings", ())),
        access=raw.get("access", "operator_only"),
        access_reason=raw.get("access_reason", "restored production secrets may be present"),
        warnings=tuple(raw.get("warnings", ())),
    )


def _protected_nas_datasets(vm, model):
    dataset_names = {
        mount.get("dataset")
        for mount in vm.get("mounts") or []
        if mount.get("dataset") in model.datasets
        and (model.datasets[mount.get("dataset")] or {}).get("lifecycle", "adopted") == "adopted"
    }
    return tuple(sorted(dataset_names))


def _service_volume_warnings(vm_name, vm, model):
    mounts_by_name = {
        mount.get("name"): mount
        for mount in vm.get("mounts") or []
        if mount.get("name") and mount.get("dataset") in model.datasets
    }
    warnings = []
    for service_name, service in sorted(model.services.items()):
        if (service.get("backend") or {}).get("vm") != vm_name:
            continue
        for container in (service.get("deploy") or {}).get("containers", []) or []:
            for volume in container.get("volumes", []) or []:
                mount = mounts_by_name.get(volume.get("mount"))
                if not mount:
                    continue
                warnings.append(
                    f"{service_name} uses Dataset {mount.get('dataset')} through Mount {mount.get('name')}"
                )
    return tuple(warnings)
