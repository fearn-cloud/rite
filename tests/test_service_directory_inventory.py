import unittest
from pathlib import Path

from fortress_inventory.entity_graph import InventoryEntityGraph
from fortress_inventory.model import load_inventory_tree
from fortress_inventory.validate import validate_inventory_model
from fortress_services.service_directory_config import homepage_services_yaml


REPO_ROOT = Path(__file__).resolve().parents[1]


class ServiceDirectoryInventoryTests(unittest.TestCase):
    def test_initial_directory_entries_are_intentionally_selected(self):
        model = load_inventory_tree(REPO_ROOT)
        facts = InventoryEntityGraph(model).directory_entry_facts()

        self.assertEqual(
            [
                ("service_ingress_route", "forgejo", "web", "Forgejo", "Development"),
                ("host_ingress_route", "molly", "proxmox_web_ui", "Molly Proxmox", "Hosts"),
                ("host_ingress_route", "neuromancer", "proxmox_web_ui", "Neuromancer Proxmox", "Hosts"),
                ("host_ingress_route", "straylight", "proxmox_web_ui", "Straylight Proxmox", "Hosts"),
                ("host_ingress_route", "wintermute", "proxmox_web_ui", "Wintermute Proxmox", "Hosts"),
                ("service_ingress_route", "bazarr", "web", "Bazarr", "Media"),
                ("service_ingress_route", "clonarr", "web", "Clonarr", "Media"),
                ("service_ingress_route", "jellyfin", "web", "Jellyfin", "Media"),
                ("service_ingress_route", "media-file-browser", "web", "Media Files", "Media"),
                ("service_ingress_route", "prowlarr", "web", "Prowlarr", "Media"),
                ("service_ingress_route", "radarr", "web", "Radarr", "Media"),
                ("service_ingress_route", "radarr-anime", "web", "Radarr Anime", "Media"),
                ("service_ingress_route", "seerr", "web", "Seerr", "Media"),
                ("service_ingress_route", "sonarr", "web", "Sonarr", "Media"),
                ("service_ingress_route", "sonarr-anime", "web", "Sonarr Anime", "Media"),
                ("service_ingress_route", "dns-primary", "web", "Pi-hole Primary", "Network"),
                ("service_ingress_route", "dns-secondary", "web", "Pi-hole Secondary", "Network"),
                ("service_ingress_route", "identity", "web", "Authentik", "Operations"),
                ("service_ingress_route", "observability", "web", "Grafana", "Operations"),
                ("service_ingress_route", "service-directory", "web", "Service Directory", "Operations"),
                ("service_ingress_route", "file-browser", "web", "Personal Files", "Storage"),
                ("nas_ingress_route", "truenas", "web_ui", "TrueNAS", "Storage"),
            ],
            [
                (fact.route_kind, fact.owner_name, fact.route_name, fact.label, fact.group)
                for fact in facts
            ],
        )

    def test_initial_directory_entries_render_operator_navigation_groups(self):
        model = load_inventory_tree(REPO_ROOT)

        self.assertEqual(
            "- Development:\n"
            "  - Forgejo:\n"
            "      href: https://git.fearn.cloud\n"
            "- Hosts:\n"
            "  - Molly Proxmox:\n"
            "      href: https://molly.fearn.cloud\n"
            "  - Neuromancer Proxmox:\n"
            "      href: https://neuromancer.fearn.cloud\n"
            "  - Straylight Proxmox:\n"
            "      href: https://straylight.fearn.cloud\n"
            "  - Wintermute Proxmox:\n"
            "      href: https://wintermute.fearn.cloud\n"
            "- Media:\n"
            "  - Bazarr:\n"
            "      href: https://bazarr.fearn.cloud\n"
            "  - Clonarr:\n"
            "      href: https://clonarr.fearn.cloud\n"
            "  - Jellyfin:\n"
            "      href: https://jellyfin.fearn.cloud\n"
            "  - Media Files:\n"
            "      href: https://media-files.fearn.cloud\n"
            "  - Prowlarr:\n"
            "      href: https://prowlarr.fearn.cloud\n"
            "  - Radarr:\n"
            "      href: https://radarr.fearn.cloud\n"
            "  - Radarr Anime:\n"
            "      href: https://radarr-anime.fearn.cloud\n"
            "  - Seerr:\n"
            "      href: https://seerr.fearn.cloud\n"
            "  - Sonarr:\n"
            "      href: https://sonarr.fearn.cloud\n"
            "  - Sonarr Anime:\n"
            "      href: https://sonarr-anime.fearn.cloud\n"
            "- Network:\n"
            "  - Pi-hole Primary:\n"
            "      href: https://dns-primary.fearn.cloud\n"
            "  - Pi-hole Secondary:\n"
            "      href: https://dns-secondary.fearn.cloud\n"
            "- Operations:\n"
            "  - Authentik:\n"
            "      href: https://auth.fearn.cloud\n"
            "  - Grafana:\n"
            "      href: https://grafana.fearn.cloud\n"
            "  - Service Directory:\n"
            "      href: https://directory.fearn.cloud\n"
            "- Storage:\n"
            "  - Personal Files:\n"
            "      href: https://files.fearn.cloud\n"
            "  - TrueNAS:\n"
            "      href: https://truenas.fearn.cloud\n",
            homepage_services_yaml(InventoryEntityGraph(model).directory_entry_facts()),
        )

    def test_current_inventory_directory_entries_validate(self):
        model = load_inventory_tree(REPO_ROOT)

        errors = validate_inventory_model(model)

        self.assertEqual([], [error for error in errors if "directory_entry" in error.code])


if __name__ == "__main__":
    unittest.main()
