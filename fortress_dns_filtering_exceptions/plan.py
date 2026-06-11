from fortress_inventory.entity_graph import InventoryEntityGraph


DNS_FILTERING_EXCEPTIONS_GROUP_NAME = "fortress-dns-filtering-exceptions"


def build_plan(model):
    graph = InventoryEntityGraph(model)
    return {
        "group_name": DNS_FILTERING_EXCEPTIONS_GROUP_NAME,
        "clients": list(model.dns_filtering_exceptions),
        "targets": _pihole_dns_targets(model, graph),
    }


def render_plan(plan):
    lines = [
        "DNS Filtering Exceptions plan",
        f"Group: {plan['group_name']}",
        f"Clients ({len(plan['clients'])}):",
    ]
    for client in plan["clients"]:
        line = f"- {client['name']} {client['ipv4_address']}"
        if client.get("reason"):
            line += f" reason={client['reason']!r}".replace("'", '"')
        lines.append(line)
    lines.append(f"Targets ({len(plan['targets'])}):")
    for target in plan["targets"]:
        lines.append(f"- {target['service']} -> {target['backend_vm']} ({target['provider']})")
    return "\n".join(lines) + "\n"


def render_peer_apply_script(plan, target):
    container_name = f"fortress-{target['service']}-pihole"
    sql = _render_reconcile_sql(plan)
    return "\n".join(
        [
            "set -euo pipefail",
            "sql_file=$(mktemp)",
            "cleanup() { rm -f \"$sql_file\"; }",
            "trap cleanup EXIT",
            "cat > \"$sql_file\" <<'FORTRESS_SQL'",
            sql,
            "FORTRESS_SQL",
            f"sudo podman exec -i {_shell_quote(container_name)} pihole-FTL sqlite3 /etc/pihole/gravity.db < \"$sql_file\"",
            f"sudo podman exec {_shell_quote(container_name)} pihole reloadlists",
            "",
        ]
    )


def _pihole_dns_targets(model, graph):
    targets = []
    for service_name, service in model.services.items():
        dns = service.get("dns") or {}
        if dns.get("provider") != "pihole":
            continue
        targets.append(
            {
                "service": service_name,
                "backend_vm": graph.service_backend_vm_name(service_name),
                "provider": "pihole",
            }
        )
    return sorted(targets, key=lambda target: target["service"])


def _render_reconcile_sql(plan):
    group_name = _sql_string(plan["group_name"])
    lines = [
        "BEGIN;",
        (
            'INSERT INTO "group" (enabled, name, description) '
            f"VALUES (1, {group_name}, 'Managed by fortress DNS Filtering Exceptions') "
            "ON CONFLICT(name) DO UPDATE SET enabled = 1, description = excluded.description;"
        ),
        (
            "DELETE FROM adlist_by_group "
            f"WHERE group_id = (SELECT id FROM \"group\" WHERE name = {group_name});"
        ),
        (
            "DELETE FROM domainlist_by_group "
            f"WHERE group_id = (SELECT id FROM \"group\" WHERE name = {group_name});"
        ),
        "CREATE TEMP TABLE fortress_desired_dns_filtering_exception_clients (ip TEXT PRIMARY KEY, name TEXT NOT NULL);",
    ]
    for client in plan["clients"]:
        lines.append(
            "INSERT INTO fortress_desired_dns_filtering_exception_clients (ip, name) "
            f"VALUES ({_sql_string(client['ipv4_address'])}, {_sql_string(client['name'])});"
        )
    lines.extend(
        [
            (
                "INSERT INTO client (ip, date_added, date_modified, comment) "
                "SELECT desired.ip, unixepoch(), unixepoch(), desired.name "
                "FROM fortress_desired_dns_filtering_exception_clients desired "
                "WHERE NOT EXISTS (SELECT 1 FROM client WHERE client.ip = desired.ip);"
            ),
            (
                "UPDATE client "
                "SET comment = (SELECT desired.name FROM fortress_desired_dns_filtering_exception_clients desired "
                "WHERE desired.ip = client.ip), date_modified = unixepoch() "
                "WHERE ip IN (SELECT ip FROM fortress_desired_dns_filtering_exception_clients);"
            ),
            (
                "INSERT INTO client_by_group (client_id, group_id) "
                'SELECT client.id, "group".id '
                "FROM client "
                "JOIN fortress_desired_dns_filtering_exception_clients desired ON desired.ip = client.ip "
                f'JOIN "group" ON "group".name = {group_name} '
                "WHERE NOT EXISTS ("
                "SELECT 1 FROM client_by_group existing "
                'WHERE existing.client_id = client.id AND existing.group_id = "group".id'
                ");"
            ),
            (
                "DELETE FROM client_by_group "
                "WHERE group_id = (SELECT id FROM \"group\" WHERE name = 'Default') "
                "AND client_id IN ("
                "SELECT client.id FROM client "
                "JOIN fortress_desired_dns_filtering_exception_clients desired ON desired.ip = client.ip"
                ");"
            ),
            (
                "DELETE FROM client_by_group "
                f"WHERE group_id = (SELECT id FROM \"group\" WHERE name = {group_name}) "
                "AND client_id NOT IN ("
                "SELECT client.id FROM client "
                "JOIN fortress_desired_dns_filtering_exception_clients desired ON desired.ip = client.ip"
                ");"
            ),
            "COMMIT;",
        ]
    )
    return "\n".join(lines)


def _sql_string(value):
    return "'" + str(value).replace("'", "''") + "'"


def _shell_quote(value):
    return "'" + str(value).replace("'", "'\"'\"'") + "'"
