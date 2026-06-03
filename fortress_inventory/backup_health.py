"""Backup Health evaluation from PBS restore-point facts."""

from dataclasses import dataclass
import datetime as dt


DEFAULT_FRESHNESS_WINDOW = dt.timedelta(hours=36)


@dataclass(frozen=True)
class RestorePointFact:
    vm_name: str
    completed_at: dt.datetime
    successful: bool


@dataclass(frozen=True)
class BackupTargetHealth:
    vm_name: str
    host_name: str | None
    status: str
    reasons: tuple[str, ...]
    latest_successful_restore_point_at: dt.datetime | None = None
    nas_backed_datasets: tuple[str, ...] = ()


@dataclass(frozen=True)
class BackupHealthRollup:
    name: str
    status: str
    healthy_count: int
    unhealthy_count: int
    excluded_count: int


@dataclass(frozen=True)
class BackupHealthReport:
    targets: tuple[BackupTargetHealth, ...]
    hosts: tuple[BackupHealthRollup, ...] = ()
    fleet: BackupHealthRollup | None = None

    @property
    def targets_by_vm(self):
        return {target.vm_name: target for target in self.targets}

    @property
    def hosts_by_name(self):
        return {host.name: host for host in self.hosts}


def evaluate_backup_health(model, restore_points, now):
    successful_restore_points = {}
    for restore_point in restore_points:
        if not restore_point.successful:
            continue
        existing = successful_restore_points.get(restore_point.vm_name)
        if existing is None or restore_point.completed_at > existing.completed_at:
            successful_restore_points[restore_point.vm_name] = restore_point

    targets = []
    for vm_name, vm in sorted(model.vms.items()):
        backup = vm.get("backup") or {}
        if backup.get("enabled") is False:
            targets.append(
                BackupTargetHealth(
                    vm_name=vm_name,
                    host_name=(vm.get("placement") or {}).get("host"),
                    status="excluded",
                    reasons=(backup.get("reason") or "Unprotected VM",),
                    nas_backed_datasets=_nas_backed_datasets(vm, model),
                )
            )
            continue
        if backup.get("enabled") is not True:
            continue
        restore_point = successful_restore_points.get(vm_name)
        reasons = []
        if not restore_point:
            reasons.append("No successful restore point found")
        elif now - restore_point.completed_at > DEFAULT_FRESHNESS_WINDOW:
            reasons.append("Latest successful restore point is older than 36 hours")
        targets.append(
            BackupTargetHealth(
                vm_name=vm_name,
                host_name=(vm.get("placement") or {}).get("host"),
                status="unhealthy" if reasons else "healthy",
                reasons=tuple(reasons),
                latest_successful_restore_point_at=restore_point.completed_at if restore_point else None,
                nas_backed_datasets=_nas_backed_datasets(vm, model),
            )
        )
    return BackupHealthReport(
        tuple(targets),
        _roll_up_hosts(model, targets),
        _roll_up_fleet(targets),
    )


def render_backup_health_report(report, target=None):
    lines = [
        _render_rollup("Fleet Backup Health", report.fleet),
    ]
    for host in report.hosts:
        lines.append(_render_rollup(f"Host {host.name}", host))
    targets = report.targets
    if target:
        targets = tuple(result for result in targets if result.vm_name == target)
    for target_health in targets:
        if target_health.status == "excluded":
            lines.append(f"Unprotected VM {target_health.vm_name} excluded: {', '.join(target_health.reasons)}")
            continue
        lines.append(f"Backup Target {target_health.vm_name} {target_health.status}")
        for reason in target_health.reasons:
            lines.append(f"- {reason}")
        if target_health.nas_backed_datasets:
            lines.append(
                "Boundary: Backup Health checks PBS restore-point freshness only; "
                "it does not prove point-in-time consistency with NAS-backed Datasets: "
                + ", ".join(target_health.nas_backed_datasets)
                + "."
            )
    return "\n".join(lines) + "\n"


def _render_rollup(label, rollup):
    return (
        f"{label} {rollup.status} "
        f"healthy={rollup.healthy_count} "
        f"unhealthy={rollup.unhealthy_count} "
        f"excluded={rollup.excluded_count}"
    )


def _roll_up_hosts(model, targets):
    rollups = []
    for host_name in sorted(model.hosts):
        host_targets = [target for target in targets if target.host_name == host_name]
        healthy_count = _count_status(host_targets, "healthy")
        unhealthy_count = _count_status(host_targets, "unhealthy")
        excluded_count = _count_status(host_targets, "excluded")
        status = "unhealthy" if unhealthy_count else "healthy"
        rollups.append(
            BackupHealthRollup(
                name=host_name,
                status=status,
                healthy_count=healthy_count,
                unhealthy_count=unhealthy_count,
                excluded_count=excluded_count,
            )
        )
    return tuple(rollups)


def _roll_up_fleet(targets):
    unhealthy_count = _count_status(targets, "unhealthy")
    return BackupHealthRollup(
        name="fleet",
        status="unhealthy" if unhealthy_count else "healthy",
        healthy_count=_count_status(targets, "healthy"),
        unhealthy_count=unhealthy_count,
        excluded_count=_count_status(targets, "excluded"),
    )


def _count_status(targets, status):
    return sum(1 for target in targets if target.status == status)


def _nas_backed_datasets(vm, model):
    dataset_names = {
        mount.get("dataset")
        for mount in vm.get("mounts") or []
        if mount.get("dataset") in model.datasets and mount.get("dataset") != "pbs-datastore"
    }
    return tuple(sorted(dataset_names))
