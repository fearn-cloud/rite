import unittest
from pathlib import Path

from fortress_ingress.generate import (
    build_caddy_layer4_route_model,
    build_caddy_route_model,
    render_caddy_routes,
    render_ingress_dns_record_sets,
)
from fortress_inventory.model import load_inventory_tree
from fortress_inventory.service_runtime_intent import analyze_service_runtime_intent
from fortress_inventory.validate import validate_inventory_tree
from fortress_services.quadlet import render_quadlet_service


REPO_ROOT = Path(__file__).resolve().parents[1]


class ForgejoInventoryTests(unittest.TestCase):
    def test_forgejo_runner_vm_is_stateless_dedicated_infrastructure_vm(self):
        model = load_inventory_tree(REPO_ROOT)
        runner_vm_names = [vm_name for vm_name in model.vms if vm_name.startswith("forgejo-runner")]
        runner_vm = model.vms["forgejo-runner-vm"]
        addresses = []
        for vm in model.vms.values():
            for interface in vm.get("network", {}).get("interfaces", []) or []:
                addresses.append(interface.get("address"))
                addresses.extend(interface.get("secondary_addresses", []) or [])

        self.assertEqual(["forgejo-runner-vm"], runner_vm_names)
        self.assertEqual("neuromancer", runner_vm["placement"]["host"])
        self.assertEqual("debian-13-base", runner_vm["source"]["template"])
        self.assertEqual("forgejo-runner-vm", runner_vm["cloud_init"]["hostname"])
        self.assertEqual(40, runner_vm["network"]["interfaces"][0]["vlan"])
        self.assertEqual("10.40.0.20/24", runner_vm["network"]["interfaces"][0]["address"])
        self.assertEqual(1, addresses.count("10.40.0.20/24"))
        self.assertEqual(
            {
                "enabled": False,
                "reason": (
                    "Forgejo Runner VM state is reproducible from Inventory and VM Configure; "
                    "workspaces, image caches, and job artifacts are disposable."
                ),
            },
            runner_vm["backup"],
        )
        self.assertIn("rebuild with VM Up", runner_vm["description"])
        self.assertIn("recover runtime state with VM Configure", runner_vm["description"])
        self.assertEqual(
            {
                "forgejo_service": "forgejo",
                "scope": "instance",
                "labels": ["debian-13:docker://debian:13"],
                "concurrency": 1,
                "cleanup": {
                    "workspace": "after_job",
                    "cache": "disposable",
                },
                "job_containers": {
                    "expose_container_runtime_socket": False,
                },
            },
            runner_vm["forgejo_runner_runtime"],
        )
        self.assertNotIn("forgejo-runner", model.services)
        self.assertEqual("forgejo-vm", model.services["forgejo"]["backend"]["vm"])
        self.assertEqual([], validate_inventory_tree(REPO_ROOT))

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

    def test_forgejo_mcp_streamable_http_ingress_is_inventory_owned(self):
        model = load_inventory_tree(REPO_ROOT)
        forgejo_mcp = model.services["forgejo-mcp"]

        self.assertEqual("forgejo-vm", forgejo_mcp["backend"]["vm"])
        self.assertEqual(
            [
                {
                    "name": "mcp",
                    "hostname": "mcp.git.fearn.cloud",
                    "published_port": 8080,
                    "exposure": "lan_only",
                    "tls": "letsencrypt_dns",
                    "auth": {"type": "none"},
                }
            ],
            forgejo_mcp["ingress_routes"],
        )
        self.assertEqual([], validate_inventory_tree(REPO_ROOT))

        route = next(
            route
            for route in build_caddy_route_model(model)["routes"]
            if route["owner"] == "forgejo-mcp"
        )
        self.assertEqual(
            {
                "kind": "service",
                "hostname": "mcp.git.fearn.cloud",
                "target": "http://10.40.0.12:8080",
                "owner": "forgejo-mcp",
                "route": "mcp",
                "tls": "letsencrypt_dns",
            },
            route,
        )

        self.assertIn(
            "mcp.git.fearn.cloud {\n"
            "\ttls {\n"
            "\t\tdns cloudflare {$CLOUDFLARE_API_TOKEN}\n"
            "\t}\n"
            "\treverse_proxy http://10.40.0.12:8080\n"
            "}",
            render_caddy_routes(model),
        )
        self.assertIn(
            "address=/mcp.git.fearn.cloud/10.40.0.16",
            render_ingress_dns_record_sets(model)[0]["content"],
        )

        rendered = render_quadlet_service(
            forgejo_mcp,
            model.vms["forgejo-vm"],
            inventory_root=REPO_ROOT / "inventory",
            runtime_intent=analyze_service_runtime_intent(model),
        )
        self.assertIn(
            "AddHost=git.fearn.cloud:10.40.0.21",
            rendered.artifacts_by_filename["fortress-forgejo-mcp-server.container"].content,
        )


if __name__ == "__main__":
    unittest.main()
