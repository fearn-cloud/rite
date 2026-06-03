"""PBS substrate facts derived from Inventory."""

from dataclasses import dataclass

from .validation.errors import ValidationError


PBS_VM_NAME = "pbs-vm"


@dataclass(frozen=True)
class PbsSubstrate:
    vm_name: str | None
    host_name: str | None
    service_name: str | None
    service_vm_name: str | None
    service_package: str | None
    systemd_service_name: str | None
    primary_datastore_name: str | None
    primary_datastore_dataset_path: str | None
    primary_datastore_backup_run_path: str | None
    primary_datastore_usable_for_backup_runs: bool
    recovery_secret_available: bool
    unprotected_vm_name: str | None
    unprotected_reason: str | None

    def operator_summary(self):
        secret_status = "available" if self.recovery_secret_available else "missing"
        return (
            "PBS substrate readiness\n"
            f"PBS VM: {self.vm_name or 'missing'}\n"
            f"Primary Datastore: {self.primary_datastore_name or 'missing'}\n"
            f"Recovery Secret: {secret_status}\n"
            "Boundary: local PBS does not back up itself.\n"
            "Backup Target readiness: not evaluated in substrate check"
        )


def inspect_pbs_substrate(model):
    vm = model.vms.get(PBS_VM_NAME)
    service_name = "pbs" if "pbs" in model.services else None
    service = model.services.get("pbs") or {}
    deploy = service.get("deploy") or {}
    primary_mount = _primary_datastore_mount(vm or {})
    primary_datastore_name = primary_mount.get("dataset")
    primary_datastore = model.datasets.get(primary_datastore_name) or {}
    recovery_secret_available = _recovery_secret_available(model)
    backup = (vm or {}).get("backup") or {}
    unprotected_vm_name = PBS_VM_NAME if backup.get("enabled") is False else None
    unprotected_reason = backup.get("reason") if unprotected_vm_name else None
    if not vm:
        return PbsSubstrate(
            vm_name=None,
            host_name=None,
            service_name=service_name,
            service_vm_name=(service.get("backend") or {}).get("vm"),
            service_package=deploy.get("package"),
            systemd_service_name=deploy.get("service_name"),
            primary_datastore_name=primary_datastore_name,
            primary_datastore_dataset_path=primary_datastore.get("path"),
            primary_datastore_backup_run_path=primary_mount.get("mount_point"),
            primary_datastore_usable_for_backup_runs=_usable_datastore_mount(primary_mount),
            recovery_secret_available=recovery_secret_available,
            unprotected_vm_name=unprotected_vm_name,
            unprotected_reason=unprotected_reason,
        )
    return PbsSubstrate(
        vm_name=PBS_VM_NAME,
        host_name=(vm.get("placement") or {}).get("host"),
        service_name=service_name,
        service_vm_name=(service.get("backend") or {}).get("vm"),
        service_package=deploy.get("package"),
        systemd_service_name=deploy.get("service_name"),
        primary_datastore_name=primary_datastore_name,
        primary_datastore_dataset_path=primary_datastore.get("path"),
        primary_datastore_backup_run_path=primary_mount.get("mount_point"),
        primary_datastore_usable_for_backup_runs=_usable_datastore_mount(primary_mount),
        recovery_secret_available=recovery_secret_available,
        unprotected_vm_name=unprotected_vm_name,
        unprotected_reason=unprotected_reason,
    )


def validate_pbs_substrate(model):
    if not _declares_pbs_substrate(model):
        return []
    substrate = inspect_pbs_substrate(model)
    errors = []
    if substrate.vm_name != PBS_VM_NAME:
        errors.append(
            ValidationError(
                "missing_pbs_vm",
                "inventory/vms/pbs-vm.yaml",
                "Inventory must declare pbs-vm as the PBS VM",
            )
        )
    if (
        substrate.service_name != "pbs"
        or substrate.service_vm_name != PBS_VM_NAME
        or substrate.service_package != "proxmox-backup-server"
        or substrate.systemd_service_name != "proxmox-backup-proxy"
    ):
        errors.append(
            ValidationError(
                "invalid_pbs_service",
                "inventory/services/pbs.yaml",
                "PBS Service must configure and run Proxmox Backup Server on pbs-vm",
            )
        )
    if (
        substrate.primary_datastore_name != "pbs-datastore"
        or not substrate.primary_datastore_dataset_path
        or not substrate.primary_datastore_usable_for_backup_runs
    ):
        errors.append(
            ValidationError(
                "unusable_pbs_primary_datastore",
                "inventory/vms/pbs-vm.yaml.mounts",
                "PBS Primary Datastore must be discoverable and mounted read-write for Backup Runs",
            )
        )
    if not substrate.recovery_secret_available:
        errors.append(
            ValidationError(
                "missing_pbs_recovery_secret",
                "inventory/vms/pbs-vm.sops.yaml.recovery_secrets.pbs_encryption_key",
                "PBS encryption Recovery Secret must be available without exposing secret material",
            )
        )
    if substrate.unprotected_vm_name != PBS_VM_NAME or not substrate.unprotected_reason:
        errors.append(
            ValidationError(
                "pbs_vm_must_be_unprotected",
                "inventory/vms/pbs-vm.yaml.backup",
                "pbs-vm must remain an Unprotected VM because local PBS does not back itself up",
            )
        )
    return errors


def _declares_pbs_substrate(model):
    return PBS_VM_NAME in model.vms or "pbs" in model.services or "pbs-datastore" in model.datasets


def _primary_datastore_mount(vm):
    for mount in vm.get("mounts") or []:
        if mount.get("dataset") == "pbs-datastore":
            return mount
    return {}


def _usable_datastore_mount(mount):
    return (
        isinstance(mount.get("mount_point"), str)
        and mount["mount_point"].startswith("/")
        and mount.get("access") == "read_write"
    )


def _recovery_secret_available(model):
    path = model.root / "inventory" / "vms" / "pbs-vm.sops.yaml"
    if not path.is_file():
        return False
    return "pbs_encryption_key" in path.read_text()
