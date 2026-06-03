"""Pure Backup Configure planning."""

from dataclasses import dataclass
import datetime as dt
import hashlib


@dataclass(frozen=True)
class ObservedBackupJob:
    name: str
    vmid: int
    datastore: str | None
    scheduled_time: dt.time
    fortress_owned: bool


@dataclass(frozen=True)
class BackupConfigureAction:
    action: str
    vm_name: str | None
    vmid: int
    policy_name: str | None
    primary_datastore: str | None
    job_name: str
    scheduled_time: dt.time
    retention: dict | None = None


@dataclass(frozen=True)
class BackupConfigurePlan:
    host_name: str
    actions: tuple[BackupConfigureAction, ...]
    pending_first_successful_runs: tuple[str, ...] = ()


def plan_host_backup_configure(model, host_name, observed_jobs, successful_backup_runs=None):
    successful_backup_runs = set(successful_backup_runs or [])
    primary_datastore = _primary_datastore_name(model)
    observed_by_name = {job.name: job for job in observed_jobs}
    actions = []
    desired_job_names = set()
    pending_first_successful_runs = []
    for vm_name, vm in sorted(model.vms.items()):
        if (vm.get("placement") or {}).get("host") != host_name:
            continue
        backup = vm.get("backup") or {}
        if backup.get("enabled") is not True:
            continue
        if vm_name not in successful_backup_runs:
            pending_first_successful_runs.append(vm_name)
        policy_name = backup.get("policy", "default")
        policy = model.backup_policies[policy_name]
        desired = BackupConfigureAction(
            action="create",
            vm_name=vm_name,
            vmid=vm["vmid"],
            policy_name=policy_name,
            primary_datastore=primary_datastore,
            job_name=_job_name(vm_name, policy_name),
            scheduled_time=_scheduled_time(vm_name, vm["vmid"], policy),
            retention=policy.get("retention"),
        )
        desired_job_names.add(desired.job_name)
        observed = observed_by_name.get(desired.job_name)
        if observed and _matches_desired_job(observed, desired):
            desired = BackupConfigureAction(
                action="no-op",
                vm_name=desired.vm_name,
                vmid=desired.vmid,
                policy_name=desired.policy_name,
                primary_datastore=desired.primary_datastore,
                job_name=desired.job_name,
                scheduled_time=desired.scheduled_time,
                retention=desired.retention,
            )
        elif observed and observed.fortress_owned:
            desired = BackupConfigureAction(
                action="update",
                vm_name=desired.vm_name,
                vmid=desired.vmid,
                policy_name=desired.policy_name,
                primary_datastore=desired.primary_datastore,
                job_name=desired.job_name,
                scheduled_time=desired.scheduled_time,
                retention=desired.retention,
            )
        actions.append(desired)
    for observed in observed_jobs:
        if not observed.fortress_owned or observed.name in desired_job_names:
            continue
        actions.append(
            BackupConfigureAction(
                action="prune",
                vm_name=_vm_name_for_vmid(model, observed.vmid),
                vmid=observed.vmid,
                policy_name=_policy_name_from_job_name(observed.name),
                primary_datastore=observed.datastore,
                job_name=observed.name,
                scheduled_time=observed.scheduled_time,
                retention=None,
            )
        )
    return BackupConfigurePlan(
        host_name=host_name,
        actions=tuple(actions),
        pending_first_successful_runs=tuple(pending_first_successful_runs),
    )


def plan_fleet_backup_configure(model, observed_jobs_by_host=None, successful_backup_runs_by_host=None):
    observed_jobs_by_host = observed_jobs_by_host or {}
    successful_backup_runs_by_host = successful_backup_runs_by_host or {}
    return tuple(
        plan_host_backup_configure(
            model,
            host_name,
            observed_jobs=observed_jobs_by_host.get(host_name, []),
            successful_backup_runs=successful_backup_runs_by_host.get(host_name, set()),
        )
        for host_name in sorted(model.hosts)
    )


def render_backup_configure_plan(plan):
    lines = [
        f"Backup Configure plan for Host {plan.host_name}",
        "Backup Policy boundary: PBS protects VM recoverability and VM-local state only.",
    ]
    for action in plan.actions:
        lines.append(
            f"{action.action} {action.vm_name} "
            f"policy={action.policy_name} "
            f"datastore={action.primary_datastore} "
            f"job={action.job_name} "
            f"scheduled={action.scheduled_time.strftime('%H:%M')}"
        )
    if plan.pending_first_successful_runs:
        lines.append(
            "Pending first successful Backup Run: "
            + ", ".join(plan.pending_first_successful_runs)
        )
    return "\n".join(lines) + "\n"


def backup_configure_plan_to_dict(plan):
    return {
        "host_name": plan.host_name,
        "actions": [
            {
                "action": action.action,
                "vm_name": action.vm_name,
                "vmid": action.vmid,
                "policy_name": action.policy_name,
                "primary_datastore": action.primary_datastore,
                "job_name": action.job_name,
                "scheduled_time": action.scheduled_time.isoformat(timespec="minutes"),
                "retention": action.retention,
            }
            for action in plan.actions
        ],
        "pending_first_successful_runs": list(plan.pending_first_successful_runs),
    }


def _matches_desired_job(observed, desired):
    return (
        observed.fortress_owned
        and observed.vmid == desired.vmid
        and observed.datastore == desired.primary_datastore
        and observed.scheduled_time == desired.scheduled_time
    )


def _job_name(vm_name, policy_name):
    return f"fortress-backup-{vm_name}-{policy_name}"


def _primary_datastore_name(model):
    pbs_vm = model.vms.get("pbs-vm") or {}
    for mount in pbs_vm.get("mounts") or []:
        if mount.get("dataset"):
            return mount["dataset"]
    if "pbs-datastore" in model.datasets:
        return "pbs-datastore"
    return None


def _vm_name_for_vmid(model, vmid):
    for vm_name, vm in model.vms.items():
        if vm.get("vmid") == vmid:
            return vm_name
    return None


def _policy_name_from_job_name(job_name):
    if job_name.startswith("fortress-backup-") and "-" in job_name:
        return job_name.rsplit("-", 1)[-1]
    return None


def _scheduled_time(vm_name, vmid, policy):
    schedule = policy["schedule"]
    base_hour, base_minute = [int(part) for part in schedule["time"].split(":")]
    base = dt.datetime.combine(dt.date(2000, 1, 1), dt.time(base_hour, base_minute))
    offset_minutes = _stable_offset_minutes(f"{vm_name}:{vmid}", _stagger_minutes(schedule["stagger"]))
    return (base + dt.timedelta(minutes=offset_minutes)).time()


def _stable_offset_minutes(identity, stagger_minutes):
    digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()
    return int(digest[:8], 16) % stagger_minutes


def _stagger_minutes(value):
    if value.endswith("m"):
        return int(value[:-1])
    raise ValueError(f"Unsupported stagger value: {value}")
