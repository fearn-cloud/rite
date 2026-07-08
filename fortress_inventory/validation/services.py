from ipaddress import ip_address

from fortress_inventory.service_runtime_intent import analyze_service_runtime_intent

from .errors import ValidationError


BACKEND_RUNTIME_DIAGNOSTICS = {
    "service_backend_not_singular",
    "missing_service_backend_vm",
}
PUBLISHED_PORT_RUNTIME_DIAGNOSTICS = {
    "published_port_collision",
    "missing_service_ingress_route_published_port",
    "non_tcp_service_ingress_route_published_port",
}
TELEMETRY_TARGET_RUNTIME_DIAGNOSTICS = {
    "missing_telemetry_target_published_port",
    "unreachable_telemetry_target_published_port",
}
SERVICE_SECRET_RUNTIME_DIAGNOSTICS = {
    "service_secret_reference_not_sibling_sops_secret",
    "service_secret_env_not_file",
}
SHARE_BACKED_VOLUME_RUNTIME_DIAGNOSTICS = {
    "missing_service_volume_mount",
    "unsafe_service_volume_source",
    "service_volume_widens_mount_access",
}
NATIVE_ENVIRONMENT_SECRET_RUNTIME_DIAGNOSTICS = {
    "native_environment_secret_reference_not_sibling_sops_secret",
}
SERVICE_OBSERVABILITY_VIEW_PROFILES = {"prometheus_generic"}


def validate_service_ingress_contract(model):
    errors = []
    for service_name, service in model.services.items():
        seen_route_names = {}
        for route_index, route in enumerate(service.get("ingress_routes", []) or []):
            route_name = route.get("name")
            if not route_name:
                continue
            if route_name in seen_route_names:
                errors.append(
                    ValidationError(
                        "duplicate_service_ingress_route_name",
                        f"inventory/services/{service_name}.yaml.ingress_routes[{route_index}].name",
                        f"Service {service_name} declares duplicate Service Ingress Route name {route_name}",
                    )
                )
            else:
                seen_route_names[route_name] = route_index
            hostname = route.get("hostname")
            if (
                route.get("exposure") == "lan_only"
                and model.globals.get("domain")
                and not _hostname_is_under_domain(hostname, model.globals["domain"])
            ):
                errors.append(
                    ValidationError(
                        "service_ingress_route_hostname_not_fleet_fqdn",
                        f"inventory/services/{service_name}.yaml.ingress_routes[{route_index}].hostname",
                        f"Service Ingress Route {service_name}/{route_name} hostname {hostname} "
                        f"must be an explicit FQDN under {model.globals['domain']}",
                    )
                )
    return errors


def validate_service_tcp_ingress_contract(model):
    errors = []
    listeners = {}
    ingress_owned_addresses = _ingress_vm_owned_ipv4_addresses(model)
    for service_name, service in model.services.items():
        seen_route_names = {}
        published_ports = _service_published_ports(service)
        for route_index, route in enumerate(service.get("ingress_tcp_routes", []) or []):
            route_name = route.get("name")
            route_path = f"inventory/services/{service_name}.yaml.ingress_tcp_routes[{route_index}]"
            if route_name:
                if route_name in seen_route_names:
                    errors.append(
                        ValidationError(
                            "duplicate_service_tcp_ingress_route_name",
                            f"{route_path}.name",
                            f"Service {service_name} declares duplicate Service TCP Ingress Route name {route_name}",
                        )
                    )
                else:
                    seen_route_names[route_name] = route_index

            hostname = route.get("hostname")
            if model.globals.get("domain") and not _hostname_is_under_domain(hostname, model.globals["domain"]):
                errors.append(
                    ValidationError(
                        "service_tcp_ingress_route_hostname_not_fleet_fqdn",
                        f"{route_path}.hostname",
                        f"Service TCP Ingress Route {service_name}/{route_name} hostname {hostname} "
                        f"must be an explicit FQDN under {model.globals['domain']}",
                    )
                )

            published_port = route.get("published_port")
            published_port_key = (published_port, "tcp")
            if published_port and published_port_key not in published_ports:
                errors.append(
                    ValidationError(
                        "missing_service_tcp_ingress_route_published_port",
                        f"{route_path}.published_port",
                        f"Service TCP Ingress Route {service_name}/{route_name} references missing TCP Published Port {published_port}",
                    )
                )

            listener = (route.get("listen_address"), route.get("listen_port"))
            listen_address = _normalized_bare_ipv4_address(route.get("listen_address"))
            if listen_address and ingress_owned_addresses and listen_address not in ingress_owned_addresses:
                errors.append(
                    ValidationError(
                        "service_tcp_ingress_listener_address_not_ingress_vm_owned",
                        f"{route_path}.listen_address",
                        f"Service TCP Ingress Route {service_name}/{route_name} listener address "
                        f"{listen_address} is not declared on the Ingress VM",
                    )
                )
            existing_route = listeners.setdefault(listener, (service_name, route_name))
            if existing_route != (service_name, route_name):
                existing_service, existing_name = existing_route
                errors.append(
                    ValidationError(
                        "duplicate_service_tcp_ingress_listener",
                        f"{route_path}.listen_port",
                        f"Service TCP Ingress Route {service_name}/{route_name} listener "
                        f"{listener[0]}:{listener[1]} collides with {existing_service}/{existing_name}",
                    )
                )
    return errors


def _ingress_vm_owned_ipv4_addresses(model):
    ingress_service = model.services.get("internal-ingress") or {}
    backend = ingress_service.get("backend") if isinstance(ingress_service, dict) else {}
    vm_name = backend.get("vm") if isinstance(backend, dict) else None
    vm = model.vms.get(vm_name)
    if not vm:
        return set()
    addresses = set()
    for interface in vm.get("network", {}).get("interfaces", []) or []:
        for value in [interface.get("address"), *(interface.get("secondary_addresses", []) or [])]:
            address = _normalized_vm_interface_ipv4_address(value)
            if address:
                addresses.add(address)
    return addresses


def validate_ingress_dns_targets(model):
    errors = []
    for service_name, service in model.services.items():
        dns = service.get("dns") or {}
        if not dns.get("ingress_records", {}).get("enabled"):
            continue
        provider = dns.get("provider")
        if not provider:
            errors.append(
                ValidationError(
                    "missing_ingress_dns_target_provider",
                    f"inventory/services/{service_name}.yaml.dns.provider",
                    f"Service {service_name} enables Ingress DNS Records but does not declare dns.provider",
                )
            )
            continue
        if provider != "pihole":
            errors.append(
                ValidationError(
                    "unsupported_ingress_dns_target_provider",
                    f"inventory/services/{service_name}.yaml.dns.provider",
                    f"Service {service_name} declares unsupported Ingress DNS Target provider {provider}",
                )
            )
    return errors


def validate_service_backends(model, runtime_intent=None):
    return _runtime_diagnostics_as_validation_errors(
        runtime_intent or analyze_service_runtime_intent(model),
        BACKEND_RUNTIME_DIAGNOSTICS,
    )


def validate_quadlet_services(model, runtime_intent=None):
    errors = []
    runtime_intent = runtime_intent or analyze_service_runtime_intent(model)
    errors.extend(_validate_published_ports(model, runtime_intent))
    errors.extend(_validate_service_telemetry_targets(model, runtime_intent))
    errors.extend(validate_service_observability_view_requests(model))
    errors.extend(_validate_service_images(model))
    errors.extend(_validate_service_networks(model))
    errors.extend(_validate_container_dependencies(model))
    errors.extend(_validate_service_secrets(model, runtime_intent))
    return errors


def validate_service_observability_view_requests(model):
    errors = []
    for service_name, service in model.services.items():
        instrumentation = service.get("instrumentation") or {}
        requests = instrumentation.get("observability_views") or []
        if len(requests) > 1:
            errors.append(
                ValidationError(
                    "multiple_service_observability_view_requests",
                    f"inventory/services/{service_name}.yaml.instrumentation.observability_views",
                    f"Service {service_name} requests more than one Service-level Observability View",
                )
            )
        telemetry_targets = instrumentation.get("telemetry_targets") or []
        for request_index, request in enumerate(requests):
            profile = request.get("profile") if isinstance(request, dict) else None
            path = f"inventory/services/{service_name}.yaml.instrumentation.observability_views[{request_index}].profile"
            if profile not in SERVICE_OBSERVABILITY_VIEW_PROFILES:
                errors.append(
                    ValidationError(
                        "unsupported_service_observability_view_profile",
                        path,
                        f"Service {service_name} requests unsupported Observability View Profile {profile}",
                    )
                )
                continue
            if profile == "prometheus_generic" and not any(
                target.get("type") == "prometheus_metrics"
                for target in telemetry_targets
                if isinstance(target, dict)
            ):
                errors.append(
                    ValidationError(
                        "incompatible_service_observability_view_profile",
                        path,
                        (
                            f"Service {service_name} requests prometheus_generic Observability View Profile "
                            "without a prometheus_metrics Telemetry Target"
                        ),
                    )
                )
    return errors


def validate_native_services(model, runtime_intent=None):
    errors = []
    apt_repos = model.globals.get("apt_repos") or {}
    for service_name, service in model.services.items():
        deploy = service.get("deploy", {})
        if deploy.get("type") != "native":
            continue
        apt_repo = deploy.get("apt_repo")
        if apt_repo and apt_repo not in apt_repos:
            errors.append(
                ValidationError(
                    "missing_native_service_apt_repo",
                    f"inventory/services/{service_name}.yaml.deploy.apt_repo",
                    f"Service {service_name} references missing apt repository {apt_repo}",
                )
            )
    errors.extend(
        _runtime_diagnostics_as_validation_errors(
            runtime_intent or analyze_service_runtime_intent(model),
            NATIVE_ENVIRONMENT_SECRET_RUNTIME_DIAGNOSTICS,
        )
    )
    return errors


def _validate_published_ports(model, runtime_intent=None):
    return _runtime_diagnostics_as_validation_errors(
        runtime_intent or analyze_service_runtime_intent(model),
        PUBLISHED_PORT_RUNTIME_DIAGNOSTICS,
    )


def _service_published_ports(service):
    ports = set()
    if service.get("deploy", {}).get("type") != "quadlet":
        return ports
    for container in service.get("deploy", {}).get("containers", []) or []:
        for published_port in container.get("published_ports", []) or []:
            host_port = published_port.get("host", published_port.get("container"))
            protocol = published_port.get("protocol", "tcp")
            if protocol in ("tcp", "tcp_udp"):
                ports.add((host_port, "tcp"))
            if protocol in ("udp", "tcp_udp"):
                ports.add((host_port, "udp"))
    return ports


def _normalized_vm_interface_ipv4_address(value):
    if not value:
        return None
    try:
        parsed = ip_address(str(value).split("/", 1)[0])
    except (TypeError, ValueError):
        return None
    if parsed.version != 4:
        return None
    return str(parsed)


def _normalized_bare_ipv4_address(value):
    try:
        parsed = ip_address(value)
    except (TypeError, ValueError):
        return None
    if parsed.version != 4:
        return None
    return str(parsed)


def _validate_service_telemetry_targets(model, runtime_intent=None):
    return _runtime_diagnostics_as_validation_errors(
        runtime_intent or analyze_service_runtime_intent(model),
        TELEMETRY_TARGET_RUNTIME_DIAGNOSTICS,
    )


def _runtime_diagnostics_as_validation_errors(intent, codes):
    return [
        ValidationError(diagnostic.code, diagnostic.path, diagnostic.message)
        for diagnostic in intent.diagnostics
        if diagnostic.code in codes
    ]


def _validate_service_images(model):
    errors = []
    for service_name, service in model.services.items():
        if service.get("deploy", {}).get("type") != "quadlet":
            continue
        for container_index, container in enumerate(service.get("deploy", {}).get("containers", []) or []):
            image = container.get("image")
            if image and not _image_is_pinned(image):
                errors.append(
                    ValidationError(
                        "unpinned_service_image",
                        f"inventory/services/{service_name}.yaml.deploy.containers[{container_index}].image",
                        f"Service {service_name} container {container.get('name', container_index)} "
                        f"uses unpinned image {image}",
                    )
                )
    return errors


def _image_is_pinned(image):
    if "@sha256:" in image:
        return True
    remainder = image.rsplit("/", 1)[-1]
    if ":" not in remainder:
        return False
    return not remainder.endswith(":latest")


def _validate_service_networks(model):
    errors = []
    network_backend_vms = {}
    aliases_by_network = {}
    for service_name, service in model.services.items():
        if service.get("deploy", {}).get("type") != "quadlet":
            continue
        group_name = service.get("service_group")
        network_name = service.get("service_network")
        backend = service.get("backend", {})
        backend_vm_name = backend.get("vm") if isinstance(backend, dict) else None
        if network_name:
            existing_vm = network_backend_vms.setdefault(network_name, backend_vm_name)
            if existing_vm != backend_vm_name:
                errors.append(
                    ValidationError(
                        "service_network_spans_backend_vms",
                        f"inventory/services/{service_name}.yaml.service_network",
                        f"Service Network {network_name} spans Backend VMs {existing_vm} and {backend_vm_name}",
                    )
                )
        if network_name:
            network_key = ("service_network", network_name)
            network_description = f"Service Network {network_name}"
        else:
            network_key = ("service", service_name)
            network_description = f"Service {service_name}"
        aliases = aliases_by_network.setdefault(network_key, {})
        for container_index, container in enumerate(service.get("deploy", {}).get("containers", []) or []):
            alias = container.get("name")
            if not alias:
                continue
            if alias in aliases:
                other_service = aliases[alias]
                errors.append(
                    ValidationError(
                        "container_alias_collision",
                        f"inventory/services/{service_name}.yaml.deploy.containers[{container_index}].name",
                        f"Services {other_service} and {service_name} both declare Container Alias {alias} "
                        f"in {network_description}",
                    )
                )
            else:
                aliases[alias] = service_name
    return errors


def _validate_container_dependencies(model):
    errors = []
    for service_name, service in model.services.items():
        if service.get("deploy", {}).get("type") != "quadlet":
            continue
        containers = service.get("deploy", {}).get("containers", []) or []
        container_names = {container.get("name") for container in containers if container.get("name")}
        graph = {}
        for container_index, container in enumerate(containers):
            container_name = container.get("name")
            graph[container_name] = list(container.get("depends_on", []) or [])
            for dependency in graph[container_name]:
                if dependency not in container_names:
                    errors.append(
                        ValidationError(
                            "missing_container_dependency",
                            f"inventory/services/{service_name}.yaml.deploy.containers[{container_index}].depends_on",
                            f"Service {service_name} container {container_name} depends on missing "
                            f"same-Service container {dependency}",
                        )
                    )
        if _has_dependency_cycle(graph):
            errors.append(
                ValidationError(
                    "container_dependency_cycle",
                    f"inventory/services/{service_name}.yaml.deploy.containers",
                    f"Service {service_name} has a Container Dependency cycle",
                )
            )
    return errors


def _has_dependency_cycle(graph):
    visiting = set()
    visited = set()

    def visit(container_name):
        if container_name in visiting:
            return True
        if container_name in visited:
            return False
        visiting.add(container_name)
        for dependency in graph.get(container_name, []):
            if dependency in graph and visit(dependency):
                return True
        visiting.remove(container_name)
        visited.add(container_name)
        return False

    return any(visit(container_name) for container_name in graph)


def _validate_service_secrets(model, runtime_intent=None):
    errors = []
    errors.extend(
        _runtime_diagnostics_as_validation_errors(
            runtime_intent or analyze_service_runtime_intent(model),
            SERVICE_SECRET_RUNTIME_DIAGNOSTICS,
        )
    )
    for service_name, service in model.services.items():
        if service.get("deploy", {}).get("type") != "quadlet":
            continue
        for container_index, container in enumerate(service.get("deploy", {}).get("containers", []) or []):
            env_names = set((container.get("env") or {}).keys())
            secret_env_names = set()
            for secret_index, secret in enumerate(container.get("secrets", []) or []):
                secret_env = secret.get("env")
                if secret_env in secret_env_names:
                    errors.append(
                        ValidationError(
                            "service_env_conflict",
                            _service_secret_path(service_name, container_index, secret_index, "env"),
                            f"Service {service_name} container {container.get('name', container_index)} "
                            f"declares duplicate generated environment variable {secret_env}",
                        )
                    )
                secret_env_names.add(secret_env)

            conflict = sorted(env_names & secret_env_names)
            if conflict:
                errors.append(
                    ValidationError(
                        "service_env_conflict",
                        f"inventory/services/{service_name}.yaml.deploy.containers[{container_index}].env",
                        f"Service {service_name} container {container.get('name', container_index)} "
                        f"declares environment variable {conflict[0]} both as env and as a Service Secret",
                    )
                )

            fragment_env_names = _quadlet_fragment_environment_names(model, service_name, container)
            conflict = sorted((env_names | secret_env_names) & fragment_env_names)
            if conflict:
                errors.append(
                    ValidationError(
                        "service_env_conflict",
                        f"inventory/services/{service_name}.quadlet.d/{container.get('name')}.container",
                        f"Service {service_name} Quadlet Fragment cannot override environment variable "
                        f"{conflict[0]} owned by Service yaml",
                    )
                )
    return errors


def _quadlet_fragment_environment_names(model, service_name, container):
    root = getattr(model, "root", None)
    if root is None:
        return set()
    fragment_path = (
        root
        / "inventory"
        / "services"
        / f"{service_name}.quadlet.d"
        / f"{container.get('name')}.container"
    )
    if not fragment_path.is_file():
        return set()
    names = set()
    section = None
    for raw_line in fragment_path.read_text().splitlines():
        line = raw_line.strip()
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1]
            continue
        if section != "Container" or not line.startswith("Environment="):
            continue
        assignment = line.split("=", 1)[1]
        if "=" in assignment:
            names.add(assignment.split("=", 1)[0])
    return names


def _service_secret_path(service_name, container_index, secret_index, field):
    return (
        f"inventory/services/{service_name}.yaml.deploy.containers"
        f"[{container_index}].secrets[{secret_index}].{field}"
    )


def validate_service_hostnames(model):
    errors = []
    seen_ingress_hostnames = {}
    for service_name, service in model.services.items():
        for route_index, route in enumerate(service.get("ingress_routes", []) or []):
            hostname = route.get("hostname")
            if not hostname:
                continue
            if hostname in seen_ingress_hostnames:
                errors.append(
                    ValidationError(
                        "duplicate_ingress_hostname",
                        f"inventory/services/{service_name}.yaml.ingress_routes[{route_index}].hostname",
                        f"{seen_ingress_hostnames[hostname]} and Service Ingress Route "
                        f"{service_name}/{route.get('name')} both publish hostname {hostname}",
                    )
                )
            else:
                seen_ingress_hostnames[hostname] = f"Service Ingress Route {service_name}/{route.get('name')}"
    return errors


def _hostname_is_under_domain(hostname, domain):
    if not isinstance(hostname, str) or not hostname.endswith(f".{domain}"):
        return False
    labels = hostname.split(".")
    return all(labels) and len(labels) > len(domain.split("."))


def validate_service_share_backed_volumes(model, runtime_intent=None):
    return _runtime_diagnostics_as_validation_errors(
        runtime_intent or analyze_service_runtime_intent(model),
        SHARE_BACKED_VOLUME_RUNTIME_DIAGNOSTICS,
    )


def _unsafe_share_backed_source(source):
    if source == "/":
        return False
    if not source or source.startswith("/"):
        return True
    return ".." in str(source).split("/")


def _service_volumes(service):
    containers = service.get("deploy", {}).get("containers", []) or []
    for container_index, container in enumerate(containers):
        for volume_index, volume in enumerate(container.get("volumes", []) or []):
            yield container_index, container, volume_index, volume


def _service_volume_path(service_name, container_index, volume_index, field):
    return (
        f"inventory/services/{service_name}.yaml.deploy.containers"
        f"[{container_index}].volumes[{volume_index}].{field}"
    )
