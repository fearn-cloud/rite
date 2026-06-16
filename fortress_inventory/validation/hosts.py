from urllib.parse import urlparse

from .errors import ValidationError


def validate_host_proxmox_endpoints(model):
    errors = []
    management_address_hosts = {
        host.get("network", {}).get("management_address"): host_name
        for host_name, host in model.hosts.items()
        if host.get("network", {}).get("management_address")
    }
    seen_endpoints = {}
    for host_name, host in model.hosts.items():
        endpoint = host.get("proxmox", {}).get("endpoint")
        if not endpoint:
            continue

        endpoint_host = _endpoint_host(endpoint)
        if endpoint_host:
            target_host = management_address_hosts.get(endpoint_host)
            if target_host and target_host != host_name:
                errors.append(
                    ValidationError(
                        "host_proxmox_endpoint_points_at_other_host",
                        f"inventory/hosts/{host_name}.yaml.proxmox.endpoint",
                        f"Host {host_name} Proxmox endpoint points at Host {target_host} management address {endpoint_host}",
                    )
                )

        normalized_endpoint = _normalized_endpoint(endpoint)
        if normalized_endpoint in seen_endpoints:
            errors.append(
                ValidationError(
                    "duplicate_host_proxmox_endpoint",
                    f"inventory/hosts/{host_name}.yaml.proxmox.endpoint",
                    f"Hosts {seen_endpoints[normalized_endpoint]} and {host_name} both use Proxmox endpoint {normalized_endpoint}",
                )
            )
        else:
            seen_endpoints[normalized_endpoint] = host_name
    return errors


def _endpoint_host(endpoint):
    parsed = urlparse(endpoint if "://" in endpoint else f"//{endpoint}")
    return parsed.hostname


def _normalized_endpoint(endpoint):
    parsed = urlparse(endpoint if "://" in endpoint else f"//{endpoint}")
    host = parsed.hostname or endpoint
    port = parsed.port or 8006
    return f"{host.lower()}:{port}"


def validate_host_ingress_routes(model):
    errors = []
    domain = model.globals.get("domain")
    trusted_source_ranges = (model.globals.get("ingress") or {}).get("trusted_source_ranges") or []
    seen_hostnames = {}
    for service_name, service in model.services.items():
        for route in service.get("ingress_routes", []) or []:
            hostname = route.get("hostname")
            if hostname:
                seen_hostnames[hostname] = f"Service Ingress Route {service_name}/{route.get('name')}"
    for host_name, host in model.hosts.items():
        route = host.get("ingress", {}).get("proxmox_web_ui", {})
        if not route.get("enabled"):
            continue
        hostname = route.get("hostname")
        if not host.get("network", {}).get("management_address"):
            errors.append(
                ValidationError(
                    "missing_host_ingress_management_address",
                    f"inventory/hosts/{host_name}.yaml.network.management_address",
                    f"Host Ingress Route for {host_name} must target the Host management address",
                )
            )
        if hostname in seen_hostnames:
            errors.append(
                ValidationError(
                    "duplicate_ingress_hostname",
                    f"inventory/hosts/{host_name}.yaml.ingress.proxmox_web_ui.hostname",
                    f"{seen_hostnames[hostname]} and Host Ingress Route {host_name} both publish hostname {hostname}",
                )
            )
        elif hostname:
            seen_hostnames[hostname] = f"Host Ingress Route {host_name}"
        expected_hostname = f"{host_name}.{domain}" if domain else None
        if hostname and expected_hostname and hostname != expected_hostname:
            errors.append(
                ValidationError(
                    "host_ingress_hostname_mismatch",
                    f"inventory/hosts/{host_name}.yaml.ingress.proxmox_web_ui.hostname",
                    f"Host Ingress Route for {host_name} must use hostname {expected_hostname}",
                )
            )
        if not trusted_source_ranges:
            errors.append(
                ValidationError(
                    "missing_host_ingress_trusted_source_ranges",
                    "inventory/group_vars/all.yaml.ingress.trusted_source_ranges",
                    f"Host Ingress Route for {host_name} is Trusted-only but no Trusted source ranges are declared",
                )
            )
    return errors


def validate_vm_host_resources(model):
    errors = []
    for vm_name, vm in model.vms.items():
        host_name = vm.get("placement", {}).get("host")
        host = model.hosts.get(host_name)
        if not host:
            continue

        host_storage = {
            storage.get("name")
            for storage in host.get("hardware", {}).get("storage", []) or []
            if storage.get("name")
        }
        for index, disk in enumerate(vm.get("hardware", {}).get("disks", []) or []):
            storage_name = disk.get("storage")
            if storage_name and storage_name not in host_storage:
                errors.append(
                    ValidationError(
                        "missing_host_storage",
                        f"inventory/vms/{vm_name}.yaml.hardware.disks[{index}].storage",
                        f"VM {vm_name} uses storage {storage_name} not declared by Host {host_name}",
                    )
                )

        host_bridges = {
            bridge.get("name")
            for bridge in host.get("network", {}).get("bridges", []) or []
            if bridge.get("name")
        }
        for index, interface in enumerate(vm.get("network", {}).get("interfaces", []) or []):
            bridge_name = interface.get("bridge")
            if bridge_name and bridge_name not in host_bridges:
                errors.append(
                    ValidationError(
                        "missing_host_bridge",
                        f"inventory/vms/{vm_name}.yaml.network.interfaces[{index}].bridge",
                        f"VM {vm_name} uses bridge {bridge_name} not declared by Host {host_name}",
                    )
                )

    return errors
