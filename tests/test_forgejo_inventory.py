import unittest
from pathlib import Path

from fortress_ingress.generate import build_caddy_layer4_route_model, render_ingress_dns_record_sets
from fortress_inventory.model import load_inventory_tree
from fortress_inventory.validate import validate_inventory_tree


REPO_ROOT = Path(__file__).resolve().parents[1]


class ForgejoInventoryTests(unittest.TestCase):
    def test_forgejo_service_declares_upgrade_target_image(self):
        model = load_inventory_tree(REPO_ROOT)
        forgejo = model.services["forgejo"]

        self.assertEqual(
            "codeberg.org/forgejo/forgejo:15.0.3",
            forgejo["deploy"]["containers"][0]["image"],
        )

    def test_git_ssh_ingress_surface_is_inventory_owned(self):
        model = load_inventory_tree(REPO_ROOT)
        ingress_vm = model.vms["internal-ingress-vm"]

        self.assertEqual("10.40.0.16/24", ingress_vm["network"]["interfaces"][0]["address"])
        self.assertIn("10.40.0.21/24", ingress_vm["network"]["interfaces"][0]["secondary_addresses"])
        self.assertEqual(
            {"listen_addresses": ["10.40.0.16"]},
            ingress_vm["management_ssh_policy"],
        )
        self.assertEqual([], validate_inventory_tree(REPO_ROOT))

        self.assertEqual(
            [
                {
                    "kind": "service_tcp",
                    "hostname": "git.fearn.cloud",
                    "listen_address": "10.40.0.21",
                    "listen_port": 22,
                    "target": "10.40.0.12:2222",
                    "owner": "forgejo",
                    "route": "ssh",
                }
            ],
            build_caddy_layer4_route_model(model)["routes"],
        )
        self.assertIn(
            "address=/git.fearn.cloud/10.40.0.21",
            render_ingress_dns_record_sets(model)[0]["content"],
        )


if __name__ == "__main__":
    unittest.main()
