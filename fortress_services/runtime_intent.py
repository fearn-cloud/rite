"""Service Runtime Intent analysis for fortress-owned Service runtime meaning."""

from dataclasses import dataclass


@dataclass(frozen=True)
class RuntimeDiagnostic:
    code: str
    path: str
    message: str


@dataclass(frozen=True)
class BackendRuntimeFact:
    service_name: str
    vm_name: str
    port: int


@dataclass(frozen=True)
class PublishedPortRuntimeFact:
    service_name: str
    vm_name: str
    container_name: str | None
    container_index: int
    port_index: int
    host_port: int
    container_port: int
    bind: str
    protocols: tuple[str, ...]
    ingress: bool


@dataclass(frozen=True)
class ServiceRuntimeIntent:
    backends: tuple[BackendRuntimeFact, ...]
    published_ports: tuple[PublishedPortRuntimeFact, ...]
    diagnostics: tuple[RuntimeDiagnostic, ...]


def analyze_service_runtime_intent(model):
    backends = []
    published_ports = []
    diagnostics = []
    seen_backend_ports = {}
    seen_published_ports = {}
    for service_name, service in model.services.items():
        backend = service.get("backend", {})
        if not isinstance(backend, dict):
            diagnostics.append(
                RuntimeDiagnostic(
                    "service_backend_not_singular",
                    f"inventory/services/{service_name}.yaml.backend",
                    f"Service {service_name} must declare one singular Backend for issue 07",
                )
            )
            continue

        vm_name = backend.get("vm")
        port = backend.get("port")
        if vm_name and vm_name not in model.vms:
            diagnostics.append(
                RuntimeDiagnostic(
                    "missing_service_backend_vm",
                    f"inventory/services/{service_name}.yaml.backend.vm",
                    f"Service {service_name} references missing Backend VM {vm_name}",
                )
            )
        if vm_name and port:
            backends.append(BackendRuntimeFact(service_name, vm_name, port))
            key = (vm_name, port)
            if key in seen_backend_ports:
                other_service = seen_backend_ports[key]
                diagnostics.append(
                    RuntimeDiagnostic(
                        "backend_port_collision",
                        f"inventory/services/{service_name}.yaml.backend.port",
                        f"Services {other_service} and {service_name} both use Backend {vm_name}:{port}",
                    )
                )
            else:
                seen_backend_ports[key] = service_name

        if service.get("deploy", {}).get("type") != "quadlet":
            continue
        ingress_backend_matches = []
        for container_index, container in enumerate(service.get("deploy", {}).get("containers", []) or []):
            for port_index, published_port in enumerate(container.get("published_ports", []) or []):
                container_port = published_port.get("container")
                host_port = published_port.get("host", container_port)
                if not (vm_name and host_port and container_port):
                    continue
                protocols = _published_port_protocols(published_port.get("protocol", "tcp"))
                fact = PublishedPortRuntimeFact(
                    service_name=service_name,
                    vm_name=vm_name,
                    container_name=container.get("name"),
                    container_index=container_index,
                    port_index=port_index,
                    host_port=host_port,
                    container_port=container_port,
                    bind=published_port.get("bind", "127.0.0.1"),
                    protocols=protocols,
                    ingress=published_port.get("ingress") is True,
                )
                published_ports.append(fact)
                if fact.ingress and fact.host_port == port and "tcp" in fact.protocols:
                    ingress_backend_matches.append(fact)
                for protocol in protocols:
                    key = (vm_name, host_port, protocol)
                    if key in seen_published_ports:
                        other_service = seen_published_ports[key].service_name
                        diagnostics.append(
                            RuntimeDiagnostic(
                                "published_port_collision",
                                _service_published_port_path(service_name, container_index, port_index, "host"),
                                f"Services {other_service} and {service_name} both publish "
                                f"{protocol.upper()} port {host_port} on Backend VM {vm_name}",
                            )
                        )
                    else:
                        seen_published_ports[key] = fact
        if service.get("ingress", {}).get("enabled") and port:
            if len(ingress_backend_matches) != 1:
                diagnostics.append(
                    RuntimeDiagnostic(
                        "invalid_ingress_published_port",
                        f"inventory/services/{service_name}.yaml.backend.port",
                        f"Service {service_name} enables Ingress but must have exactly one TCP-capable "
                        f"Published Port marked for Ingress on Backend port {port}",
                    )
                )
            if not ingress_backend_matches:
                diagnostics.append(
                    RuntimeDiagnostic(
                        "missing_ingress_published_port",
                        f"inventory/services/{service_name}.yaml.backend.port",
                        f"Service {service_name} enables Ingress but no Published Port explicitly marks "
                        f"Backend port {port} with ingress: true",
                    )
                )

    return ServiceRuntimeIntent(
        backends=tuple(backends),
        published_ports=tuple(published_ports),
        diagnostics=tuple(diagnostics),
    )


def _published_port_protocols(protocol):
    if protocol == "tcp_udp":
        return ("tcp", "udp")
    return (protocol or "tcp",)


def _service_published_port_path(service_name, container_index, port_index, field):
    return (
        f"inventory/services/{service_name}.yaml.deploy.containers"
        f"[{container_index}].published_ports[{port_index}].{field}"
    )
