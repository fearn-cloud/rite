"""Live Backup Readiness evaluation for Backup Targets."""

from dataclasses import dataclass

from .backup_configure_plan import plan_host_backup_configure
from .pbs_substrate import inspect_pbs_substrate
from .validation.backups import _valid_backup_policy


@dataclass(frozen=True)
class BackupReadinessResult:
    vm_name: str
    host_name: str | None
    status: str
    reasons: tuple[str, ...]
    expected_job_name: str | None = None
    nas_backed_datasets: tuple[str, ...] = ()


@dataclass(frozen=True)
class BackupReadinessReport:
    results: tuple[BackupReadinessResult, ...]

    @property
    def ready(self):
        return all(result.status != "blocked" for result in self.results)

    @property
    def results_by_vm(self):
        return {result.vm_name: result for result in self.results}


def evaluate_backup_readiness(model, observed_jobs_by_host=None, successful_backup_runs_by_host=None):
    observed_jobs_by_host = observed_jobs_by_host or {}
    successful_backup_runs_by_host = successful_backup_runs_by_host or {}
    substrate = inspect_pbs_substrate(model)
    results = []

    for vm_name, vm in sorted(model.vms.items()):
        backup = vm.get("backup") or {}
        if backup.get("enabled") is False:
            results.append(
                BackupReadinessResult(
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

        host_name = (vm.get("placement") or {}).get("host")
        policy_name = backup.get("policy", "default")
        reasons = []

        policy = model.backup_policies.get(policy_name)
        policy_valid = bool(policy and _valid_backup_policy(policy))
        if not policy_valid:
            reasons.append(f"Backup Policy {policy_name} is not valid")

        if not substrate.primary_datastore_usable_for_backup_runs:
            reasons.append("Primary Datastore path is not usable for Backup Runs")

        if not substrate.recovery_secret_available:
            reasons.append("PBS encryption Recovery Secret is not available")

        expected_job_name = None
        if policy_valid:
            plan = plan_host_backup_configure(
                model,
                host_name,
                observed_jobs=observed_jobs_by_host.get(host_name, ()),
                successful_backup_runs=successful_backup_runs_by_host.get(host_name, ()),
            )
            target_actions = [action for action in plan.actions if action.vm_name == vm_name]
            expected_job_name = target_actions[0].job_name if target_actions else None
            if not target_actions or target_actions[0].action != "no-op":
                reasons.append("Expected Backup Job is not present")

        if vm_name not in set(successful_backup_runs_by_host.get(host_name, ())):
            reasons.append("No successful Backup Run has completed")

        results.append(
            BackupReadinessResult(
                vm_name=vm_name,
                host_name=host_name,
                status="blocked" if reasons else "ready",
                reasons=tuple(reasons),
                expected_job_name=expected_job_name,
                nas_backed_datasets=_nas_backed_datasets(vm, model),
            )
        )

    return BackupReadinessReport(tuple(results))


def render_backup_readiness_report(report, target=None):
    results = report.results
    if target:
        results = tuple(result for result in results if result.vm_name == target)

    lines = []
    for result in results:
        if result.status == "ready":
            lines.append(f"Backup Readiness ready {result.vm_name}")
        elif result.status == "excluded":
            lines.append(f"Backup Readiness excluded {result.vm_name}: {', '.join(result.reasons)}")
        else:
            lines.append(f"Backup Readiness blocked {result.vm_name}")
            for reason in result.reasons:
                lines.append(f"- {reason}")
        if result.status != "excluded" and result.nas_backed_datasets:
            lines.append(
                "Boundary: PBS protects VM recoverability and VM-local state only; "
                "NAS-backed Dataset history is not protected by PBS: "
                + ", ".join(result.nas_backed_datasets)
                + "."
            )
    return "\n".join(lines) + ("\n" if lines else "")


def _nas_backed_datasets(vm, model):
    dataset_names = {
        mount.get("dataset")
        for mount in vm.get("mounts") or []
        if mount.get("dataset") in model.datasets and mount.get("dataset") != "pbs-datastore"
    }
    return tuple(sorted(dataset_names))
