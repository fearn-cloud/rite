import re

from .errors import ValidationError


def validate_backup_policies(model):
    errors = []
    if not model.backup_policy_file_exists:
        errors.append(
            ValidationError(
                "missing_backup_policy_file",
                "inventory/backup-policies.yaml",
                "Inventory must declare fleet Backup Policies",
            )
        )
        return errors

    if "default" not in model.backup_policies:
        errors.append(
            ValidationError(
                "missing_default_backup_policy",
                "inventory/backup-policies.yaml.policies.default",
                "Inventory Backup Policies must declare default",
            )
        )

    for policy_name, policy in model.backup_policies.items():
        if not _valid_backup_policy(policy):
            errors.append(
                ValidationError(
                    "malformed_backup_policy",
                    f"inventory/backup-policies.yaml.policies.{policy_name}",
                    f"Backup Policy {policy_name} must declare a valid daily schedule and retention",
                )
            )

    for vm_name, vm in model.vms.items():
        backup = vm.get("backup") or {}
        if _requires_backup_declaration(vm) and "enabled" not in backup:
            errors.append(
                ValidationError(
                    "missing_production_backup_declaration",
                    f"inventory/vms/{vm_name}.yaml.backup.enabled",
                    f"Production VM {vm_name} must declare whether it is a Backup Target or an Unprotected VM",
                )
            )
        if _requires_backup_declaration(vm) and backup.get("enabled") is False and not backup.get("reason"):
            errors.append(
                ValidationError(
                    "missing_unprotected_vm_reason",
                    f"inventory/vms/{vm_name}.yaml.backup.reason",
                    f"Unprotected VM {vm_name} must declare an operator-facing reason",
                )
            )
        if backup.get("enabled") is True:
            policy_name = backup.get("policy", "default")
            if policy_name not in model.backup_policies:
                errors.append(
                    ValidationError(
                        "missing_backup_policy",
                        f"inventory/vms/{vm_name}.yaml.backup.policy",
                        f"Backup Target {vm_name} references missing Backup Policy {policy_name}",
                    )
                )

    return errors


def _requires_backup_declaration(vm):
    lifecycle = vm.get("lifecycle") or {}
    return lifecycle.get("kind", "ordinary") == "ordinary" and lifecycle.get("generated") is not True


def _valid_backup_policy(policy):
    schedule = policy.get("schedule") if isinstance(policy, dict) else None
    retention = policy.get("retention") if isinstance(policy, dict) else None
    if not isinstance(schedule, dict) or not isinstance(retention, dict):
        return False
    if schedule.get("cadence") != "daily":
        return False
    if not re.match(r"^([01][0-9]|2[0-3]):[0-5][0-9]$", str(schedule.get("time", ""))):
        return False
    if not re.match(r"^[A-Za-z_]+/[A-Za-z_]+$", str(schedule.get("timezone", ""))):
        return False
    if not re.match(r"^[1-9][0-9]*m$", str(schedule.get("stagger", ""))):
        return False
    return all(isinstance(retention.get(key), int) and retention[key] > 0 for key in ("daily", "weekly", "monthly"))
