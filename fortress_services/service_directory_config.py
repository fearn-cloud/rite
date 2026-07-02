from fortress_inventory.entity_graph import InventoryEntityGraph
from fortress_services.quadlet import ServiceDataFile


HOMEPAGE_SERVICES_PATH = "/srv/services/service-directory/config/services.yaml"


def service_directory_service_data_files(model):
    service = model.services.get("service-directory") or {}
    owner = service.get("service_data_owner") or {}
    return (
        ServiceDataFile(
            path=HOMEPAGE_SERVICES_PATH,
            content=homepage_services_yaml(InventoryEntityGraph(model).directory_entry_facts()),
            uid=owner.get("uid"),
            gid=owner.get("gid"),
            force=True,
        ),
    )


def homepage_services_yaml(directory_entries):
    groups = {}
    for entry in directory_entries:
        groups.setdefault(entry.group or "", []).append(entry)
    if not groups:
        return "[]\n"

    lines = []
    for group in sorted(groups):
        lines.append(f"- {group}:")
        for entry in sorted(groups[group], key=lambda fact: fact.label or ""):
            lines.append(f"  - {entry.label}:")
            lines.append(f"      href: {entry.destination}")
    return "\n".join(lines) + "\n"
