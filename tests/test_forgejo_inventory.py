import unittest
from pathlib import Path

from fortress_inventory.model import load_inventory_tree


REPO_ROOT = Path(__file__).resolve().parents[1]


class ForgejoInventoryTests(unittest.TestCase):
    def test_forgejo_service_declares_upgrade_target_image(self):
        model = load_inventory_tree(REPO_ROOT)
        forgejo = model.services["forgejo"]

        self.assertEqual(
            "codeberg.org/forgejo/forgejo:15.0.3",
            forgejo["deploy"]["containers"][0]["image"],
        )


if __name__ == "__main__":
    unittest.main()
