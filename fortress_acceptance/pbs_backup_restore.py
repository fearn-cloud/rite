"""Live PBS backup/restore Acceptance Test planning and execution."""

from dataclasses import dataclass
import json
from pathlib import Path
import subprocess

from fortress_inventory.simple_yaml import load_yaml


@dataclass(frozen=True)
class AcceptanceVmPlan:
    name: str
    vmid: int
    placement: dict
    network: str

    def to_dict(self):
        return {
            "name": self.name,
            "vmid": self.vmid,
            "placement": self.placement,
            "network": self.network,
        }


@dataclass(frozen=True)
class PbsBackupRestoreAcceptancePlan:
    host: str
    template: str
    source_vm: AcceptanceVmPlan
    restored_vm: AcceptanceVmPlan
    backup_job_name: str
    datastore: str
    marker_path: str
    marker_value: str
    production_vm_names: tuple[str, ...] = ()
    production_backup_job_names: tuple[str, ...] = ()

    def to_dict(self):
        return {
            "host": self.host,
            "template": self.template,
            "source_vm": self.source_vm.to_dict(),
            "restored_vm": self.restored_vm.to_dict(),
            "backup_job_name": self.backup_job_name,
            "datastore": self.datastore,
            "marker_path": self.marker_path,
            "marker_value": self.marker_value,
            "production_vm_names": list(self.production_vm_names),
            "production_backup_job_names": list(self.production_backup_job_names),
        }


@dataclass(frozen=True)
class PbsBackupRestoreAcceptanceResult:
    success: bool
    cleanup_status: str
    messages: tuple[str, ...]

    def render(self):
        return "\n".join(self.messages) + "\n"


def execute_pbs_backup_restore_acceptance(plan, client, *, keep_on_fail=False):
    containment_error = _containment_error(plan)
    if containment_error:
        return PbsBackupRestoreAcceptanceResult(False, "not-run", (containment_error,))

    created_source = False
    job_reconciled = False
    restored = False
    try:
        client.create_source_vm(
            vm_name=plan.source_vm.name,
            vmid=plan.source_vm.vmid,
            template=plan.template,
        )
        created_source = True
        client.write_marker(
            vm_name=plan.source_vm.name,
            path=plan.marker_path,
            value=plan.marker_value,
        )
        client.reconcile_backup_job(
            job_name=plan.backup_job_name,
            vmid=plan.source_vm.vmid,
            datastore=plan.datastore,
        )
        job_reconciled = True
        client.trigger_backup_run(job_name=plan.backup_job_name, vmid=plan.source_vm.vmid)
        snapshot_id = client.wait_successful_restore_point(
            vm_name=plan.source_vm.name,
            vmid=plan.source_vm.vmid,
        )
        client.restore_vm(
            snapshot_id=snapshot_id,
            vm_name=plan.restored_vm.name,
            vmid=plan.restored_vm.vmid,
            access="operator_only",
        )
        restored = True
        client.verify_marker(
            vm_name=plan.restored_vm.name,
            path=plan.marker_path,
            value=plan.marker_value,
        )
    except Exception as error:
        if keep_on_fail:
            return PbsBackupRestoreAcceptanceResult(
                False,
                "preserved",
                (
                    f"PBS backup/restore Acceptance Test failed: {error}",
                    "keep-on-fail preserved generated PBS acceptance artifacts for diagnosis",
                    cleanup_instructions(plan),
                    "Trigger submission is not proven backup protection",
                ),
            )
        cleanup_status, cleanup_message = _cleanup(client, plan, created_source, job_reconciled, restored)
        return PbsBackupRestoreAcceptanceResult(
            False,
            cleanup_status,
            (
                f"PBS backup/restore Acceptance Test failed: {error}",
                cleanup_message,
                "Trigger submission is not proven backup protection",
            ),
        )

    cleanup_status, cleanup_message = _cleanup(client, plan, created_source, job_reconciled, restored)
    return PbsBackupRestoreAcceptanceResult(
        cleanup_status == "cleaned",
        cleanup_status,
        (
            "PBS backup/restore Acceptance Test passed",
            cleanup_message,
            "Trigger submission is not proven backup protection; successful restore point verification proved recoverability for the generated Acceptance VM",
            "This is live PBS backup/restore acceptance, not Backup Readiness, Backup Health, or production Restore Drill",
        ),
    )


def pbs_backup_restore_acceptance_plan_from_dict(raw):
    return PbsBackupRestoreAcceptancePlan(
        host=raw["host"],
        template=raw["template"],
        source_vm=_vm_plan_from_dict(raw["source_vm"]),
        restored_vm=_vm_plan_from_dict(raw["restored_vm"]),
        backup_job_name=raw["backup_job_name"],
        datastore=raw["datastore"],
        marker_path=raw["marker_path"],
        marker_value=raw["marker_value"],
        production_vm_names=tuple(raw.get("production_vm_names", ())),
        production_backup_job_names=tuple(raw.get("production_backup_job_names", ())),
    )


def plan_pbs_backup_restore_acceptance(repo_root, *, host, template, inventory):
    policy = load_yaml(Path(repo_root) / "inventory" / "acceptance" / "pbs-backup-restore.yaml")
    source = _vm_from_policy(policy, "source", host, template)
    restored = _vm_from_policy(policy, "restored", host, template, network="isolated-acceptance")
    datastore = _primary_datastore_name(inventory)
    return PbsBackupRestoreAcceptancePlan(
        host=host,
        template=template,
        source_vm=source,
        restored_vm=restored,
        backup_job_name=f"fortress-backup-{source.name}-acceptance",
        datastore=datastore,
        marker_path="/var/lib/fortress/pbs-acceptance-marker.txt",
        marker_value=f"fortress-pbs-acceptance:{source.name}:{source.vmid}",
        production_vm_names=tuple(inventory.vms),
        production_backup_job_names=_production_backup_job_names(inventory),
    )


class JsonLogPbsBackupRestoreAcceptanceClient:
    def __init__(self, path, fail_on=None):
        self.path = Path(path)
        self.fail_on = fail_on

    def create_source_vm(self, **kwargs):
        self._append("create_source_vm", kwargs)

    def write_marker(self, **kwargs):
        self._append("write_marker", kwargs)

    def reconcile_backup_job(self, **kwargs):
        self._append("reconcile_backup_job", kwargs)

    def trigger_backup_run(self, **kwargs):
        self._append("trigger_backup_run", kwargs)

    def wait_successful_restore_point(self, **kwargs):
        self._append("wait_successful_restore_point", kwargs)
        return f"pbs:vm/{kwargs['vmid']}/2026-06-04T03:30:00Z"

    def restore_vm(self, **kwargs):
        self._append("restore_vm", kwargs)

    def verify_marker(self, **kwargs):
        self._append("verify_marker", kwargs)

    def destroy_vm(self, **kwargs):
        self._append("destroy_vm", kwargs)

    def delete_backup_job(self, **kwargs):
        self._append("delete_backup_job", kwargs)

    def cleanup_generated_inventory(self, **kwargs):
        self._append("cleanup_generated_inventory", kwargs)

    def _append(self, method, kwargs):
        calls = []
        if self.path.exists():
            calls = json.loads(self.path.read_text())
        calls.append({"method": method, **kwargs})
        self.path.write_text(json.dumps(calls, default=str))
        if self.fail_on == method:
            raise RuntimeError(f"{method} failed")


class PveshPbsBackupRestoreAcceptanceClient:
    def __init__(self, host_name, repo_root=None):
        self.host_name = host_name
        self.repo_root = Path(repo_root or Path(__file__).resolve().parents[1])

    def create_source_vm(self, **kwargs):
        raise RuntimeError(
            "live PBS acceptance backend is not implemented; refusing to claim a generated VM was backed up and restored"
        )

    def write_marker(self, **kwargs):
        self._run(["echo", f"write marker {kwargs['path']} on {kwargs['vm_name']}"])

    def reconcile_backup_job(self, **kwargs):
        self._run(["echo", f"reconcile PBS acceptance Backup Job {kwargs['job_name']}"])

    def trigger_backup_run(self, **kwargs):
        self._run(["echo", f"trigger PBS acceptance Backup Run {kwargs['job_name']}"])

    def wait_successful_restore_point(self, **kwargs):
        self._run(["echo", f"wait successful PBS acceptance restore point for {kwargs['vm_name']}"])
        return f"pbs:vm/{kwargs['vmid']}/latest-successful"

    def restore_vm(self, **kwargs):
        self._run(["echo", f"restore PBS acceptance VM {kwargs['vm_name']} from {kwargs['snapshot_id']}"])

    def verify_marker(self, **kwargs):
        self._run(["echo", f"verify marker {kwargs['path']} on {kwargs['vm_name']}"])

    def destroy_vm(self, **kwargs):
        self._run(["echo", f"destroy PBS acceptance VM {kwargs['vm_name']}"])

    def delete_backup_job(self, **kwargs):
        self._run(["echo", f"delete PBS acceptance Backup Job {kwargs['job_name']}"])

    def cleanup_generated_inventory(self, **kwargs):
        self._run(["echo", "cleanup PBS acceptance generated inventory"])

    def _run(self, command):
        completed = subprocess.run(
            [str(self.repo_root / "scripts" / "host-shell"), self.host_name, "--", *command],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout).strip() or f"exit {completed.returncode}"
            raise RuntimeError(detail)


def cleanup_instructions(plan):
    return (
        "Cleanup: destroy generated VMs "
        f"{plan.restored_vm.name}, {plan.source_vm.name}; delete Backup Job {plan.backup_job_name}; "
        "remove generated PBS acceptance inventory artifacts"
    )


def _cleanup(client, plan, created_source, job_reconciled, restored):
    if not (created_source or job_reconciled or restored):
        return "not-needed", "PBS acceptance cleanup not needed; no generated live resources were created"
    try:
        if restored:
            client.destroy_vm(vm_name=plan.restored_vm.name)
        if job_reconciled:
            client.delete_backup_job(job_name=plan.backup_job_name)
        if created_source:
            client.destroy_vm(vm_name=plan.source_vm.name)
        client.cleanup_generated_inventory(artifact_names=sorted([plan.source_vm.name, plan.restored_vm.name]))
    except Exception as error:
        return "failed", f"PBS acceptance cleanup failed: {error}"
    return "cleaned", "PBS acceptance cleanup completed"


def _containment_error(plan):
    production_vm_names = set(plan.production_vm_names)
    if plan.source_vm.name in production_vm_names or plan.restored_vm.name in production_vm_names:
        return "PBS backup/restore Acceptance containment refused: generated VM identity collides with production VM inventory"
    if plan.backup_job_name in set(plan.production_backup_job_names):
        return "PBS backup/restore Acceptance containment refused: temporary Backup Job collides with production Backup Jobs"
    if plan.source_vm.name == plan.restored_vm.name:
        return "PBS backup/restore Acceptance containment refused: source and restored VM identities must be distinct"
    return None


def _vm_plan_from_dict(raw):
    return AcceptanceVmPlan(
        name=raw["name"],
        vmid=raw["vmid"],
        placement=raw["placement"],
        network=raw["network"],
    )


def _vm_from_policy(policy, role, host, template, network=None):
    role_policy = (policy.get("vms") or {})[role]
    return AcceptanceVmPlan(
        name=role_policy["name"],
        vmid=role_policy["vmid"],
        placement={"host": host, "storage": (policy.get("storage_by_host") or {})[host]},
        network=network or (role_policy.get("address_by_host") or {})[host],
    )


def _primary_datastore_name(inventory):
    pbs_vm = inventory.vms.get("pbs-vm") or {}
    for mount in pbs_vm.get("mounts") or []:
        if mount.get("dataset"):
            return mount["dataset"]
    if "pbs-datastore" in inventory.datasets:
        return "pbs-datastore"
    return None


def _production_backup_job_names(inventory):
    names = []
    for vm_name, vm in inventory.vms.items():
        backup = vm.get("backup") or {}
        if backup.get("enabled") is True:
            names.append(f"fortress-backup-{vm_name}-{backup.get('policy', 'default')}")
    return tuple(names)
