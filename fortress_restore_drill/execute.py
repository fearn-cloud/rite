"""Restore Drill execution against an approved plan."""

from dataclasses import dataclass
import json
from pathlib import Path
import subprocess


@dataclass(frozen=True)
class RestoreDrillExecutionResult:
    success: bool
    verification_status: str
    cleanup_status: str
    messages: tuple[str, ...]

    def render(self):
        return "\n".join(self.messages) + "\n"


def execute_restore_drill(plan, client, *, keep_on_fail=False, keep_on_success=False):
    containment_error = _containment_error(plan)
    if containment_error:
        return RestoreDrillExecutionResult(
            success=False,
            verification_status="not-run",
            cleanup_status="not-run",
            messages=(containment_error,),
        )

    vm_name = plan.restored_vm.name
    try:
        client.restore_drill_vm(
            snapshot_id=plan.restore_point.snapshot_id,
            vm_name=vm_name,
            placement=plan.restored_vm.placement,
            network=plan.restored_vm.network,
            preserve_production_secrets=True,
            access=plan.access,
        )
        client.verify_drill_vm(vm_name=vm_name)
    except Exception as error:
        if keep_on_fail:
            return RestoreDrillExecutionResult(
                success=False,
                verification_status="failed",
                cleanup_status="preserved",
                messages=(
                    f"Restore Drill failed during verification: {error}",
                    "keep-on-fail preserved Restored Drill VM for diagnosis",
                    "Restore Drill verification is not production Service health",
                ),
            )
        cleanup_status, cleanup_message = _destroy(client, vm_name)
        return RestoreDrillExecutionResult(
            success=False,
            verification_status="failed",
            cleanup_status=cleanup_status,
            messages=(
                f"Restore Drill failed during verification: {error}",
                cleanup_message,
                "Restore Drill verification is not production Service health",
            ),
        )

    if keep_on_success:
        return RestoreDrillExecutionResult(
            success=True,
            verification_status="passed",
            cleanup_status="preserved",
            messages=(
                "Restore Drill verification passed",
                "Restored Drill VM preserved by explicit request",
                "Restore Drill verification is not production Service health",
            ),
        )
    cleanup_status, cleanup_message = _destroy(client, vm_name)
    return RestoreDrillExecutionResult(
        success=cleanup_status == "destroyed",
        verification_status="passed",
        cleanup_status=cleanup_status,
        messages=(
            "Restore Drill verification passed",
            cleanup_message,
            "Restore Drill verification is not production Service health",
        ),
    )


class JsonLogRestoreDrillClient:
    def __init__(self, path, fail_on=None):
        self.path = Path(path)
        self.fail_on = fail_on

    def restore_drill_vm(self, **kwargs):
        self._append({"method": "restore", **kwargs})
        if self.fail_on == "restore":
            raise RuntimeError("restore failed")

    def verify_drill_vm(self, *, vm_name):
        self._append({"method": "verify", "vm_name": vm_name})
        if self.fail_on == "verify":
            raise RuntimeError("verification failed")

    def destroy_drill_vm(self, *, vm_name):
        self._append({"method": "destroy", "vm_name": vm_name})
        if self.fail_on == "destroy":
            raise RuntimeError("destroy failed")

    def _append(self, call):
        calls = []
        if self.path.exists():
            calls = json.loads(self.path.read_text())
        calls.append(call)
        self.path.write_text(json.dumps(calls, default=str))


class PveshRestoreDrillClient:
    def __init__(self, host_name, repo_root=None):
        self.host_name = host_name
        self.repo_root = Path(repo_root or Path(__file__).resolve().parents[1])

    def restore_drill_vm(self, *, snapshot_id, vm_name, placement, network, preserve_production_secrets, access):
        self._run(
            [
                "echo",
                (
                    "restore drill placeholder: "
                    f"{snapshot_id} {vm_name} host={placement.get('host')} "
                    f"storage={placement.get('storage')} network={network} access={access}"
                ),
            ]
        )

    def verify_drill_vm(self, *, vm_name):
        self._run(["echo", f"verify restore drill placeholder: {vm_name}"])

    def destroy_drill_vm(self, *, vm_name):
        self._run(["echo", f"destroy restore drill placeholder: {vm_name}"])

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


def _containment_error(plan):
    if plan.restored_vm.lifecycle != "generated_disposable":
        return "Restore Drill containment refused: Restored Drill VM must be generated disposable"
    if plan.production_ingress != "disabled":
        return "Restore Drill containment refused: production ingress must stay disabled"
    if plan.production_dns != "disabled":
        return "Restore Drill containment refused: production DNS must stay disabled"
    if plan.production_nas_mutation != "disabled":
        return "Restore Drill containment refused: production NAS-backed Dataset mutation must stay disabled"
    if plan.access != "operator_only":
        return "Restore Drill containment refused: restored production secrets require operator-only access"
    return None


def _destroy(client, vm_name):
    try:
        client.destroy_drill_vm(vm_name=vm_name)
    except Exception as error:
        return "failed", f"Restored Drill VM cleanup failed: {error}"
    return "destroyed", "Restored Drill VM destroyed"
