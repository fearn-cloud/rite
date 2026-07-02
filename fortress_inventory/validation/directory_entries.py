from .errors import ValidationError


SERVICE_ROUTE_NOT_ROUTABLE_CODES = {
    "missing_service_ingress_route_published_port",
    "non_tcp_service_ingress_route_published_port",
}


def validate_directory_entries(model, runtime_intent):
    errors = []
    unroutable_service_route_paths = {
        diagnostic.path
        for diagnostic in runtime_intent.diagnostics
        if diagnostic.code in SERVICE_ROUTE_NOT_ROUTABLE_CODES
    }

    for service_name, service in model.services.items():
        for route_index, route in enumerate(service.get("ingress_routes", []) or []):
            entry = route.get("directory_entry") or {}
            if not entry.get("enabled"):
                continue
            published_port_path = f"inventory/services/{service_name}.yaml.ingress_routes[{route_index}].published_port"
            if published_port_path in unroutable_service_route_paths:
                errors.append(
                    ValidationError(
                        "directory_entry_route_not_routable",
                        f"inventory/services/{service_name}.yaml.ingress_routes[{route_index}].directory_entry.enabled",
                        f"Directory Entry for Service Ingress Route {service_name}/{route.get('name', route_index)} "
                        "is enabled but the owning route is not routable",
                    )
                )

    for host_name, host in model.hosts.items():
        route = host.get("ingress", {}).get("proxmox_web_ui", {}) or {}
        entry = route.get("directory_entry") or {}
        if not entry.get("enabled"):
            continue
        if not route.get("enabled"):
            errors.append(
                ValidationError(
                    "directory_entry_route_not_routable",
                    f"inventory/hosts/{host_name}.yaml.ingress.proxmox_web_ui.directory_entry.enabled",
                    f"Directory Entry for Host Ingress Route {host_name} is enabled but the owning route is disabled",
                )
            )
        elif not host.get("network", {}).get("management_address"):
            errors.append(
                ValidationError(
                    "directory_entry_route_not_routable",
                    f"inventory/hosts/{host_name}.yaml.ingress.proxmox_web_ui.directory_entry.enabled",
                    f"Directory Entry for Host Ingress Route {host_name} is enabled but the owning route has no target",
                )
            )

    for endpoint_name, endpoint in model.nas_endpoints.items():
        route = endpoint.get("ingress", {}).get("web_ui", {}) or {}
        entry = route.get("directory_entry") or {}
        if not entry.get("enabled"):
            continue
        if not route.get("enabled"):
            errors.append(
                ValidationError(
                    "directory_entry_route_not_routable",
                    f"inventory/nas/{endpoint_name}.yaml.ingress.web_ui.directory_entry.enabled",
                    f"Directory Entry for NAS Ingress Route {endpoint_name} is enabled but the owning route is disabled",
                )
            )
        elif not endpoint.get("management_address"):
            errors.append(
                ValidationError(
                    "directory_entry_route_not_routable",
                    f"inventory/nas/{endpoint_name}.yaml.ingress.web_ui.directory_entry.enabled",
                    f"Directory Entry for NAS Ingress Route {endpoint_name} is enabled but the owning route has no target",
                )
            )

    return errors
