from .errors import ValidationError


def validate_acceptance_policy_host_coverage(model):
    errors = []
    template_hosts = {
        host_name
        for host_name, host in model.hosts.items()
        if host.get("proxmox", {}).get("templates")
    }
    for policy_name, policy in model.acceptance_policies.items():
        storage_by_host = policy.get("storage_by_host", {}) or {}
        for host_name in sorted(template_hosts - set(storage_by_host)):
            errors.append(
                ValidationError(
                    "missing_acceptance_policy_host_storage",
                    f"inventory/acceptance/{policy_name}.yaml.storage_by_host.{host_name}",
                    f"Acceptance Policy {policy_name} has no storage_by_host entry for Host {host_name}",
                )
            )
        for role_name, role in (policy.get("vms", {}) or {}).items():
            address_by_host = role.get("address_by_host", {}) or {}
            for host_name in sorted(template_hosts - set(address_by_host)):
                errors.append(
                    ValidationError(
                        "missing_acceptance_policy_host_address",
                        f"inventory/acceptance/{policy_name}.yaml.vms.{role_name}.address_by_host.{host_name}",
                        f"Acceptance Policy {policy_name} has no {role_name} address_by_host entry for Host {host_name}",
                    )
                )
    return errors
