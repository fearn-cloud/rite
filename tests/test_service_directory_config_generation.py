import unittest

from fortress_inventory.model import InventoryModel
from fortress_services.service_directory_config import service_directory_service_data_files


HOMEPAGE_SERVICES_PATH = "/srv/services/service-directory/config/services.yaml"


def inventory_model(hosts=None, services=None, nas_endpoints=None):
    return InventoryModel(
        root=None,
        hosts=hosts or {},
        vms={
            "directory-vm": {
                "network": {"interfaces": [{"address": "10.40.0.17/24"}]},
            },
            "app-vm": {
                "network": {"interfaces": [{"address": "10.50.0.13/24"}]},
            },
        },
        services=services or {},
        datasets={},
        nas_endpoints=nas_endpoints or {},
        templates={},
        template_verification_policy={},
        acceptance_policies={},
        globals={},
    )


class ServiceDirectoryConfigGenerationTests(unittest.TestCase):
    def test_homepage_services_config_is_generated_empty_when_no_directory_entries_exist(self):
        model = inventory_model(services={"service-directory": service_directory_service()})

        services = generated_file(service_directory_service_data_files(model), HOMEPAGE_SERVICES_PATH)

        self.assertEqual("[]\n", services.content)
        self.assertTrue(services.force)

    def test_homepage_services_config_groups_a_single_service_directory_entry(self):
        model = inventory_model(
            services={
                "service-directory": service_directory_service(),
                "hermes": {
                    "backend": {"vm": "app-vm"},
                    "ingress_routes": [
                        {
                            "name": "web",
                            "hostname": "hermes.fearn.cloud",
                            "directory_entry": {
                                "enabled": True,
                                "label": "Hermes",
                                "group": "Apps",
                            },
                        },
                    ],
                },
            }
        )

        services = generated_file(service_directory_service_data_files(model), HOMEPAGE_SERVICES_PATH)

        self.assertEqual(
            "- Apps:\n"
            "  - Hermes:\n"
            "      href: https://hermes.fearn.cloud\n",
            services.content,
        )

    def test_homepage_services_config_orders_groups_and_entries_by_label(self):
        model = inventory_model(
            services={
                "service-directory": service_directory_service(),
                "sonarr": {
                    "backend": {"vm": "app-vm"},
                    "ingress_routes": [
                        {
                            "name": "web",
                            "hostname": "sonarr.fearn.cloud",
                            "directory_entry": {
                                "enabled": True,
                                "label": "Sonarr",
                                "group": "Media",
                            },
                        },
                        {
                            "name": "anime",
                            "hostname": "anime.fearn.cloud",
                            "directory_entry": {
                                "enabled": True,
                                "label": "Anime",
                                "group": "Media",
                            },
                        },
                    ],
                },
                "vaultwarden": {
                    "backend": {"vm": "app-vm"},
                    "ingress_routes": [
                        {
                            "name": "web",
                            "hostname": "vault.fearn.cloud",
                            "directory_entry": {
                                "enabled": True,
                                "label": "Vaultwarden",
                                "group": "Apps",
                            },
                        },
                    ],
                },
            }
        )

        services = generated_file(service_directory_service_data_files(model), HOMEPAGE_SERVICES_PATH)

        self.assertEqual(
            "- Apps:\n"
            "  - Vaultwarden:\n"
            "      href: https://vault.fearn.cloud\n"
            "- Media:\n"
            "  - Anime:\n"
            "      href: https://anime.fearn.cloud\n"
            "  - Sonarr:\n"
            "      href: https://sonarr.fearn.cloud\n",
            services.content,
        )

    def test_homepage_services_config_includes_mixed_route_kind_directory_entries(self):
        model = inventory_model(
            hosts={
                "wintermute": {
                    "ingress": {
                        "proxmox_web_ui": {
                            "enabled": True,
                            "hostname": "wintermute.fearn.cloud",
                            "directory_entry": {
                                "enabled": True,
                                "label": "Wintermute",
                                "group": "Infrastructure",
                            },
                        },
                    },
                },
            },
            services={
                "service-directory": service_directory_service(),
                "hermes": {
                    "backend": {"vm": "app-vm"},
                    "ingress_routes": [
                        {
                            "name": "web",
                            "hostname": "hermes.fearn.cloud",
                            "directory_entry": {
                                "enabled": True,
                                "label": "Hermes",
                                "group": "Apps",
                            },
                        },
                    ],
                },
            },
            nas_endpoints={
                "truenas": {
                    "ingress": {
                        "web_ui": {
                            "enabled": True,
                            "hostname": "truenas.fearn.cloud",
                            "directory_entry": {
                                "enabled": True,
                                "label": "TrueNAS",
                                "group": "Infrastructure",
                            },
                        },
                    },
                },
            },
        )

        services = generated_file(service_directory_service_data_files(model), HOMEPAGE_SERVICES_PATH)

        self.assertEqual(
            "- Apps:\n"
            "  - Hermes:\n"
            "      href: https://hermes.fearn.cloud\n"
            "- Infrastructure:\n"
            "  - TrueNAS:\n"
            "      href: https://truenas.fearn.cloud\n"
            "  - Wintermute:\n"
            "      href: https://wintermute.fearn.cloud\n",
            services.content,
        )


def generated_file(deploy_vars, path):
    return next(
        file
        for file in deploy_vars
        if file.path == path
    )


def service_directory_service():
    return {
        "name": "service-directory",
        "service_data_owner": {"uid": 1000, "gid": 1000},
        "backend": {"vm": "directory-vm"},
        "deploy": {
            "type": "quadlet",
            "containers": [
                {
                    "name": "homepage",
                    "image": "ghcr.io/gethomepage/homepage:v1.4.6",
                    "volumes": [
                        {
                            "service_path": "config",
                            "container": "/app/config",
                            "access": "read_write",
                        }
                    ],
                }
            ],
        },
    }


if __name__ == "__main__":
    unittest.main()
