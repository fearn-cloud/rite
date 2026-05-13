from ipaddress import ip_interface


def render_caddy_routes(model):
    routes = []
    routes.extend(_service_routes(model))
    routes.extend(_host_ingress_routes(model))
    return "\n\n".join(_render_caddy_route(route) for route in sorted(routes, key=lambda route: route["hostname"])) + "\n"


def render_caddyfile(model):
    routes = render_caddy_routes(model).strip()
    caddyfile = "{\n\tadmin {$CADDY_ADMIN}\n}\n"
    if routes:
        caddyfile += f"\n{routes}\n"
    return caddyfile


def _service_routes(model):
    routes = []
    for service_name, service in model.services.items():
        if not service.get("ingress", {}).get("enabled"):
            continue
        backend = service.get("backend", {})
        vm = model.vms.get(backend.get("vm"))
        if not vm:
            continue
        routes.append(
            {
                "kind": "service",
                "hostname": service.get("hostname"),
                "target": f"http://{_first_vm_address(vm)}:{backend.get('port')}",
                "owner": service_name,
            }
        )
    return routes


def _host_ingress_routes(model):
    routes = []
    trusted_source_ranges = _trusted_source_ranges(model)
    for host_name, host in model.hosts.items():
        route = host.get("ingress", {}).get("proxmox_web_ui", {})
        if not route.get("enabled"):
            continue
        routes.append(
            {
                "kind": "host",
                "hostname": route.get("hostname"),
                "target": f"http://{host.get('network', {}).get('management_address')}:{route.get('port', 8006)}",
                "trusted_source_ranges": trusted_source_ranges,
                "owner": host_name,
            }
        )
    return routes


def _render_caddy_route(route):
    if route["kind"] == "host":
        source_ranges = " ".join(route["trusted_source_ranges"])
        return "\n".join(
            [
                f"{route['hostname']} {{",
                "\ttls internal",
                f"\t@trusted remote_ip {source_ranges}",
                "\thandle @trusted {",
                f"\t\treverse_proxy {route['target']}",
                "\t}",
                "\trespond 403",
                "}",
            ]
        )

    return "\n".join(
        [
            f"{route['hostname']} {{",
            "\ttls internal",
            f"\treverse_proxy {route['target']}",
            "}",
        ]
    )


def _trusted_source_ranges(model):
    return list((model.globals.get("ingress") or {}).get("trusted_source_ranges") or [])


def _first_vm_address(vm):
    for interface in vm.get("network", {}).get("interfaces", []) or []:
        address = interface.get("address")
        if address:
            return str(ip_interface(address).ip)
    return None
