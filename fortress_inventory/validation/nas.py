from .errors import ValidationError


def validate_nas_ingress_routes(model):
    errors = []
    domain = model.globals.get("domain")
    trusted_source_ranges = (model.globals.get("ingress") or {}).get("trusted_source_ranges") or []
    seen_hostnames = {
        service.get("hostname"): f"Service {service_name}"
        for service_name, service in model.services.items()
        if service.get("ingress", {}).get("enabled") and service.get("hostname")
    }
    for host_name, host in model.hosts.items():
        route = host.get("ingress", {}).get("proxmox_web_ui", {})
        hostname = route.get("hostname")
        if route.get("enabled") and hostname:
            seen_hostnames[hostname] = f"Host Ingress Route {host_name}"

    for endpoint_name, endpoint in model.nas_endpoints.items():
        route = endpoint.get("ingress", {}).get("web_ui", {})
        hostname = route.get("hostname")
        if hostname and not route.get("enabled"):
            errors.append(
                ValidationError(
                    "nas_ingress_hostname_without_enabled",
                    f"inventory/nas/{endpoint_name}.yaml.ingress.web_ui.hostname",
                    f"NAS Endpoint {endpoint_name} declares a hostname but does not enable NAS Ingress Route",
                )
            )
            continue
        if not route.get("enabled"):
            continue
        if not endpoint.get("management_address"):
            errors.append(
                ValidationError(
                    "missing_nas_ingress_management_address",
                    f"inventory/nas/{endpoint_name}.yaml.management_address",
                    f"NAS Ingress Route for {endpoint_name} must target the NAS Endpoint Management Address",
                )
            )
        if hostname in seen_hostnames:
            errors.append(
                ValidationError(
                    "duplicate_ingress_hostname",
                    f"inventory/nas/{endpoint_name}.yaml.ingress.web_ui.hostname",
                    f"{seen_hostnames[hostname]} and NAS Ingress Route {endpoint_name} both publish hostname {hostname}",
                )
            )
        elif hostname:
            seen_hostnames[hostname] = f"NAS Ingress Route {endpoint_name}"
        expected_hostname = f"{endpoint_name}.{domain}" if domain else None
        if hostname and expected_hostname and hostname != expected_hostname:
            errors.append(
                ValidationError(
                    "nas_ingress_hostname_mismatch",
                    f"inventory/nas/{endpoint_name}.yaml.ingress.web_ui.hostname",
                    f"NAS Ingress Route for {endpoint_name} must use hostname {expected_hostname}",
                )
            )
        if not trusted_source_ranges:
            errors.append(
                ValidationError(
                    "missing_nas_ingress_trusted_source_ranges",
                    "inventory/group_vars/all.yaml.ingress.trusted_source_ranges",
                    f"NAS Ingress Route for {endpoint_name} is Trusted-only but no Trusted source ranges are declared",
                )
            )
    return errors
