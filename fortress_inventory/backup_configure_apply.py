"""Apply Backup Configure plans through a small PVE client interface."""

from dataclasses import dataclass
import datetime as dt
from pathlib import Path
import subprocess

from fortress_inventory.backup_configure_plan import BackupConfigureAction, BackupConfigurePlan


@dataclass(frozen=True)
class BackupConfigureApplyResult:
    success: bool
    message: str = ""
    applied_actions: tuple[str, ...] = ()


def apply_backup_configure_plan(
    plan,
    client,
    confirm_prune=None,
    auto_confirm_prune=False,
    reporter=None,
):
    _report(reporter, f"Applying Backup Configure plan for Host {plan.host_name} ({len(plan.actions)} action(s))")
    prune_actions = tuple(action for action in plan.actions if action.action == "prune")
    prune_confirmed = (
        not prune_actions
        or auto_confirm_prune
        or (confirm_prune and confirm_prune(plan, prune_actions))
    )
    if prune_actions and not prune_confirmed:
        _report(reporter, f"Host {plan.host_name}: prune refused by operator")
        return BackupConfigureApplyResult(
            success=False,
            message=f"Prune refused for Host {plan.host_name}",
        )
    applied_actions = []
    if not plan.actions:
        _report(reporter, f"Host {plan.host_name}: no Backup Configure actions")
    for action in plan.actions:
        try:
            completed_action = action.action
            _report(reporter, f"Host {plan.host_name}: {action.action} {_action_summary(action)}")
            if action.action == "create":
                try:
                    client.create_backup_job(
                        job_name=action.job_name,
                        vmid=action.vmid,
                        datastore=action.primary_datastore,
                        scheduled_time=action.scheduled_time,
                        retention=action.retention,
                    )
                    applied_actions.append(action.action)
                except Exception as error:
                    if not _backup_job_already_exists(error, action.job_name):
                        raise
                    _report(
                        reporter,
                        f"Host {plan.host_name}: Backup Job {action.job_name} already exists; updating instead",
                    )
                    client.update_backup_job(
                        job_name=action.job_name,
                        vmid=action.vmid,
                        datastore=action.primary_datastore,
                        scheduled_time=action.scheduled_time,
                        retention=action.retention,
                    )
                    applied_actions.append("update")
                    completed_action = "update"
            if action.action == "update":
                client.update_backup_job(
                    job_name=action.job_name,
                    vmid=action.vmid,
                    datastore=action.primary_datastore,
                    scheduled_time=action.scheduled_time,
                    retention=action.retention,
                )
                applied_actions.append(action.action)
            if action.action == "prune" and prune_confirmed:
                client.delete_backup_job(job_name=action.job_name)
                applied_actions.append(action.action)
            _report(reporter, f"Host {plan.host_name}: {completed_action} complete for Backup Job {action.job_name}")
        except Exception as error:
            _report(reporter, f"Host {plan.host_name}: {action.action} failed for Backup Job {action.job_name}")
            return BackupConfigureApplyResult(
                success=False,
                message=(
                    f"Backup Configure apply failed for Host {plan.host_name}; "
                    f"Backup Target {action.vm_name}; "
                    f"Backup Job {action.job_name}; "
                    f"action {action.action}: {error}"
                ),
                applied_actions=tuple(applied_actions),
            )
    _report(reporter, f"Backup Configure apply complete for Host {plan.host_name}")
    return BackupConfigureApplyResult(success=True, applied_actions=tuple(applied_actions))


class PveshBackupJobClient:
    def __init__(self, host_name, repo_root=None):
        self.host_name = host_name
        self.repo_root = Path(repo_root or Path(__file__).resolve().parents[1])

    def create_backup_job(self, *, job_name, vmid, datastore, scheduled_time, retention=None):
        self._run(
            [
                "pvesh",
                "create",
                "/cluster/backup",
                "--id",
                job_name,
                "--storage",
                datastore,
                "--vmid",
                str(vmid),
                "--schedule",
                _pve_schedule(scheduled_time),
                *(_pve_retention_args(retention) if retention else []),
                "--enabled",
                "1",
            ]
        )

    def update_backup_job(self, *, job_name, vmid, datastore, scheduled_time, retention=None):
        self._run(
            [
                "pvesh",
                "set",
                f"/cluster/backup/{job_name}",
                "--storage",
                datastore,
                "--vmid",
                str(vmid),
                "--schedule",
                _pve_schedule(scheduled_time),
                *(_pve_retention_args(retention) if retention else []),
                "--enabled",
                "1",
            ]
        )

    def delete_backup_job(self, *, job_name):
        self._run(["pvesh", "delete", f"/cluster/backup/{job_name}"])

    def _run(self, command):
        completed = subprocess.run(
            [
                str(self.repo_root / "scripts" / "host-shell"),
                self.host_name,
                "--",
                *command,
            ],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout).strip() or f"exit {completed.returncode}"
            raise RuntimeError(detail)


def backup_configure_plan_from_dict(raw):
    return BackupConfigurePlan(
        host_name=raw["host_name"],
        actions=tuple(
            BackupConfigureAction(
                action=action["action"],
                vm_name=action.get("vm_name"),
                vmid=action["vmid"],
                policy_name=action.get("policy_name"),
                primary_datastore=action.get("primary_datastore"),
                job_name=action["job_name"],
                scheduled_time=dt.time.fromisoformat(action["scheduled_time"]),
                retention=action.get("retention"),
            )
            for action in raw.get("actions", [])
        ),
        pending_first_successful_runs=tuple(raw.get("pending_first_successful_runs", [])),
    )


def backup_configure_plans_from_dict(raw):
    if isinstance(raw, list):
        return tuple(backup_configure_plan_from_dict(plan) for plan in raw)
    return (backup_configure_plan_from_dict(raw),)


def _pve_schedule(scheduled_time):
    return scheduled_time.strftime("%H:%M")


def _pve_retention_args(retention):
    keep_parts = []
    for key, value in sorted(retention.items()):
        keep_parts.append(f"keep-{key}={value}")
    return ["--prune-backups", ",".join(keep_parts)]


def _backup_job_already_exists(error, job_name):
    return f"Job '{job_name}' already exists" in str(error)


def _report(reporter, message):
    if reporter:
        reporter(message)


def _action_summary(action):
    target = action.vm_name or f"VMID {action.vmid}"
    scheduled = action.scheduled_time.strftime("%H:%M")
    return (
        f"Backup Target {target}; "
        f"Backup Job {action.job_name}; "
        f"datastore={action.primary_datastore}; "
        f"schedule={scheduled}"
    )
