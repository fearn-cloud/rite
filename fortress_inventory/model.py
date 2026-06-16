from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path

from .simple_yaml import load_yaml


@dataclass(frozen=True)
class InventoryModel:
    root: Path
    hosts: dict
    vms: dict
    services: dict
    datasets: dict
    nas_endpoints: dict
    templates: dict
    template_verification_policy: dict
    acceptance_policies: dict
    globals: dict
    backup_policy_file_exists: bool = False
    backup_policies: dict = field(default_factory=dict)
    dns_filtering_exceptions: list = field(default_factory=list)


def load_inventory_tree(root):
    root = Path(root)
    inventory_root = root / "inventory"
    services = _load_entity_dir(inventory_root / "services")
    return InventoryModel(
        root=root,
        hosts=_load_entity_dir(inventory_root / "hosts"),
        vms=_default_vms(_load_entity_dir(inventory_root / "vms")),
        services=_default_services(services),
        datasets=_load_entity_dir(inventory_root / "datasets"),
        nas_endpoints=_default_nas_endpoints(_load_entity_dir(inventory_root / "nas")),
        templates=_load_entity_dir(inventory_root / "templates"),
        template_verification_policy=_load_optional_yaml(inventory_root / "template-verification-policy.yaml"),
        backup_policy_file_exists=(inventory_root / "backup-policies.yaml").is_file(),
        backup_policies=_load_optional_yaml(inventory_root / "backup-policies.yaml").get("policies", {}),
        dns_filtering_exceptions=_load_optional_yaml(inventory_root / "dns-filtering-exceptions.yaml").get(
            "exceptions",
            [],
        ),
        acceptance_policies=_load_entity_dir(inventory_root / "acceptance"),
        globals=_load_optional_yaml(inventory_root / "group_vars" / "all.yaml"),
    )


def _load_entity_dir(path):
    entities = {}
    if not path.is_dir():
        return entities
    for yaml_path in sorted(path.glob("*.yaml")):
        if yaml_path.name.startswith("_") or yaml_path.name.endswith(".sops.yaml"):
            continue
        entities[yaml_path.stem] = load_yaml(yaml_path)
    return entities


def _load_optional_yaml(path):
    if not path.is_file():
        return {}
    return load_yaml(path)


def _default_vms(vms):
    return {
        vm_name: _default_vm(vm)
        for vm_name, vm in vms.items()
    }


def _default_vm(vm):
    vm = deepcopy(vm)
    lifecycle = vm.get("lifecycle", {}) or {}
    if lifecycle.get("kind", "ordinary") == "ordinary":
        instrumentation = dict(vm.get("instrumentation") or {})
        instrumentation.setdefault("enabled", True)
        vm["instrumentation"] = instrumentation
    backup = dict(vm.get("backup") or {})
    if backup.get("enabled") is True:
        backup.setdefault("policy", "default")
        vm["backup"] = backup
    return vm


def _default_services(services):
    return {
        service_name: _default_service(service)
        for service_name, service in services.items()
    }


def _default_service(service):
    service = deepcopy(service)
    for container in service.get("deploy", {}).get("containers", []) or []:
        for published_port in container.get("published_ports", []) or []:
            published_port.setdefault("bind", "127.0.0.1")
            published_port.setdefault("protocol", "tcp")
    return service


def _default_nas_endpoints(nas_endpoints):
    return {
        endpoint_name: _default_nas_endpoint(endpoint)
        for endpoint_name, endpoint in nas_endpoints.items()
    }


def _default_nas_endpoint(endpoint):
    endpoint = deepcopy(endpoint)
    ingress = dict(endpoint.get("ingress") or {})
    web_ui = dict(ingress.get("web_ui") or {})
    if web_ui.get("enabled"):
        web_ui.setdefault("exposure", "trusted_only")
        web_ui.setdefault("tls", "letsencrypt_dns")
        web_ui.setdefault("auth", {"type": "none"})
        web_ui.setdefault("scheme", "http")
        web_ui.setdefault("port", 80)
    if web_ui:
        ingress["web_ui"] = web_ui
    if ingress:
        endpoint["ingress"] = ingress
    return endpoint
