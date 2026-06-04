"""Explicit initial Backup Run triggering."""

from dataclasses import dataclass
import json
from pathlib import Path
import subprocess

from fortress_inventory.backup_configure_apply import _pve_retention_args


@dataclass(frozen=True)
class InitialBackupRunTriggerResult:
    success: bool
    submitted_targets: tuple[str, ...] = ()
    submission_outputs: tuple[tuple[str, str], ...] = ()
    pending_first_successful_runs: tuple[str, ...] = ()
    message: str = ""

    def render(self):
        if self.message:
            return self.message + "\n"
        outputs_by_target = dict(self.submission_outputs)
        lines = []
        for target in self.submitted_targets:
            lines.append(f"Submitted initial Backup Run for Backup Target {target}; submitted now")
            output = outputs_by_target.get(target)
            if output:
                lines.append(f"PVE submission output for Backup Target {target}: {output}")
        if self.pending_first_successful_runs:
            lines.append(
                "Pending first successful Backup Run: "
                + ", ".join(self.pending_first_successful_runs)
            )
        lines.append("Trigger submission is not proven backup protection")
        return "\n".join(lines) + "\n"


def trigger_initial_backup_runs(plan, client, *, target_name=None):
    pending_targets = set(plan.pending_first_successful_runs)
    if target_name and target_name not in pending_targets:
        return InitialBackupRunTriggerResult(
            success=False,
            message=(
                f"Backup Target {target_name} does not have a pending first successful "
                f"Backup Run on Host {plan.host_name}"
            ),
        )
    if not target_name and not plan.pending_first_successful_runs:
        return InitialBackupRunTriggerResult(
            success=True,
            message=f"No pending first successful Backup Runs on Host {plan.host_name}",
        )
    target_names = (target_name,) if target_name else plan.pending_first_successful_runs
    actions_by_target = {action.vm_name: action for action in plan.actions}
    submitted_targets = []
    submission_outputs = []
    for name in target_names:
        action = actions_by_target.get(name)
        if action:
            output = client.trigger_backup_job_now(
                job_name=action.job_name,
                vmid=action.vmid,
                datastore=action.primary_datastore,
                retention=action.retention,
            )
            submitted_targets.append(action.vm_name)
            if output:
                submission_outputs.append((action.vm_name, output))
    if submitted_targets:
        return InitialBackupRunTriggerResult(
            success=True,
            submitted_targets=tuple(submitted_targets),
            submission_outputs=tuple(submission_outputs),
            pending_first_successful_runs=tuple(plan.pending_first_successful_runs),
        )
    return InitialBackupRunTriggerResult(
        success=False,
        message=f"Backup Target {target_name} is not in Host {plan.host_name} Backup Configure plan",
    )


class PveshInitialBackupRunClient:
    def __init__(self, host_name, repo_root=None):
        self.host_name = host_name
        self.repo_root = Path(repo_root or Path(__file__).resolve().parents[1])

    def trigger_backup_job_now(self, *, job_name, vmid, datastore, retention=None):
        completed = subprocess.run(
            [
                str(self.repo_root / "scripts" / "host-shell"),
                self.host_name,
                "--",
                "pvesh",
                "create",
                f"/nodes/{self.host_name}/vzdump",
                "--vmid",
                str(vmid),
                "--storage",
                datastore,
                "--mode",
                "snapshot",
                "--job-id",
                job_name,
                *(_pve_retention_args(retention) if retention else []),
            ],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout).strip() or f"exit {completed.returncode}"
            raise RuntimeError(detail)
        return _submission_output(completed)


class JsonLogInitialBackupRunClient:
    def __init__(self, host_name, path):
        self.host_name = host_name
        self.path = Path(path)

    def trigger_backup_job_now(self, *, job_name, vmid, datastore=None, retention=None):
        calls = []
        if self.path.exists():
            calls = json.loads(self.path.read_text())
        calls.append(
            {
                "host": self.host_name,
                "job_name": job_name,
                "vmid": vmid,
                "datastore": datastore,
                "retention": retention,
            }
        )
        self.path.write_text(json.dumps(calls))
        return None


def _submission_output(completed):
    parts = [
        text.strip()
        for text in (completed.stdout, completed.stderr)
        if text and text.strip()
    ]
    return "\n".join(parts) or None
