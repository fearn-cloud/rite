import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from fortress_ingress.generate import render_caddy_routes
from fortress_inventory.model import load_inventory_tree


REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURES = REPO_ROOT / "tests" / "fixtures"


class IngressGenerationTests(unittest.TestCase):
    def test_host_ingress_route_is_limited_to_inventory_trusted_source_ranges(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            shutil.copytree(FIXTURES / "inventory_valid", root, dirs_exist_ok=True)
            (root / "inventory" / "group_vars" / "all.yaml").write_text(
                "domain: fearn.cloud\n"
                "nas:\n"
                "  default_options:\n"
                "    - nfsvers=4.2\n"
                "ingress:\n"
                "  trusted_source_ranges:\n"
                "    - 10.20.0.0/24\n"
                "    - 100.64.0.0/10\n"
            )
            (root / "inventory" / "hosts" / "wintermute.yaml").write_text(
                "proxmox:\n"
                "  pve_node_name: wintermute\n"
                "network:\n"
                "  management_address: 10.0.0.10\n"
                "ingress:\n"
                "  proxmox_web_ui:\n"
                "    enabled: true\n"
                "    hostname: wintermute.fearn.cloud\n"
            )

            caddy_routes = render_caddy_routes(load_inventory_tree(root))

            self.assertIn("wintermute.fearn.cloud {", caddy_routes)
            self.assertIn("@trusted remote_ip 10.20.0.0/24 100.64.0.0/10", caddy_routes)
            self.assertIn("handle @trusted {\n\t\treverse_proxy http://10.0.0.10:8006\n\t}", caddy_routes)
            self.assertIn("respond 403", caddy_routes)
            self.assertIn("photos.fearn.cloud {", caddy_routes)
            self.assertNotIn("@trusted remote_ip 10.0.10.101", caddy_routes)

    def test_ingress_regenerate_command_prints_trusted_host_routes(self):
        result = subprocess.run(
            [str(REPO_ROOT / "scripts" / "ingress-regenerate")],
            cwd=REPO_ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("wintermute.fearn.cloud {", result.stdout)
        self.assertIn("@trusted remote_ip 10.20.0.0/24", result.stdout)
