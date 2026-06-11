import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from fortress_dns_filtering_exceptions.plan import DNS_FILTERING_EXCEPTIONS_GROUP_NAME, build_plan
from fortress_inventory.model import load_inventory_tree


REPO_ROOT = Path(__file__).resolve().parents[1]


class DnsFilteringExceptionsTests(unittest.TestCase):
    def test_plan_targets_pihole_dns_services_with_declared_clients(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            shutil.copytree(REPO_ROOT / "inventory", root / "inventory")
            (root / "inventory" / "dns-filtering-exceptions.yaml").write_text(
                "exceptions:\n"
                "  - name: living-room-xbox\n"
                "    ipv4_address: 10.25.0.50\n"
                "    reason: vendor services break under Pi-hole blocking\n"
            )

            plan = build_plan(load_inventory_tree(root))

            self.assertEqual(DNS_FILTERING_EXCEPTIONS_GROUP_NAME, plan["group_name"])
            self.assertEqual(
                [{"name": "living-room-xbox", "ipv4_address": "10.25.0.50", "reason": "vendor services break under Pi-hole blocking"}],
                plan["clients"],
            )
            self.assertEqual(
                [
                    {"service": "dns-primary", "backend_vm": "dns-primary-vm", "provider": "pihole"},
                    {"service": "dns-secondary", "backend_vm": "dns-secondary-vm", "provider": "pihole"},
                ],
                plan["targets"],
            )

    def test_plan_reports_zero_clients_for_missing_or_empty_declaration(self):
        for declaration in (None, "exceptions: []\n"):
            with self.subTest(declaration=declaration):
                with tempfile.TemporaryDirectory() as tmp:
                    root = Path(tmp)
                    shutil.copytree(REPO_ROOT / "inventory", root / "inventory")
                    declaration_path = root / "inventory" / "dns-filtering-exceptions.yaml"
                    if declaration is None:
                        declaration_path.unlink(missing_ok=True)
                    else:
                        declaration_path.write_text(declaration)

                    plan = build_plan(load_inventory_tree(root))

                    self.assertEqual([], plan["clients"])
                    self.assertEqual(["dns-primary", "dns-secondary"], [target["service"] for target in plan["targets"]])

    def test_print_mode_outputs_stable_plan_without_calling_vm_shell(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            shutil.copytree(REPO_ROOT / "inventory", root / "inventory")
            (root / "inventory" / "dns-filtering-exceptions.yaml").write_text(
                "exceptions:\n"
                "  - name: living-room-xbox\n"
                "    ipv4_address: 10.25.0.50\n"
                "    reason: vendor services break under Pi-hole blocking\n"
            )
            scripts = root / "scripts"
            scripts.mkdir()
            vm_shell = scripts / "vm-shell"
            vm_shell.write_text("#!/usr/bin/env bash\nexit 99\n")
            vm_shell.chmod(vm_shell.stat().st_mode | 0o100)

            result = subprocess.run(
                [str(REPO_ROOT / "scripts" / "dns-filtering-exceptions-apply"), "--print"],
                cwd=REPO_ROOT,
                env={"FORTRESS_ROOT": str(root)},
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(
                "DNS Filtering Exceptions plan\n"
                "Group: fortress-dns-filtering-exceptions\n"
                "Clients (1):\n"
                "- living-room-xbox 10.25.0.50 reason=\"vendor services break under Pi-hole blocking\"\n"
                "Targets (2):\n"
                "- dns-primary -> dns-primary-vm (pihole)\n"
                "- dns-secondary -> dns-secondary-vm (pihole)\n",
                result.stdout,
            )

    def test_justfile_exposes_dns_filtering_exceptions_apply(self):
        justfile = (REPO_ROOT / "justfile").read_text()

        self.assertIn("dns-filtering-exceptions-apply", justfile)
        self.assertIn("./scripts/dns-filtering-exceptions-apply", justfile)

    def test_apply_uses_vm_shell_for_each_peer_without_confirmation_or_restart(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            shutil.copytree(REPO_ROOT / "inventory", root / "inventory")
            (root / "inventory" / "dns-filtering-exceptions.yaml").write_text(
                "exceptions:\n"
                "  - name: living-room-xbox\n"
                "    ipv4_address: 10.25.0.50\n"
            )
            calls_log = root / "calls.log"
            self._write_fake_vm_shell(root, calls_log)

            result = self._run_apply(root)

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertNotIn("confirm", result.stdout.lower())
            calls = calls_log.read_text()
            self.assertIn("vm-shell dns-primary-vm -- bash -s", calls)
            self.assertIn("vm-shell dns-secondary-vm -- bash -s", calls)
            self.assertLess(calls.index("dns-primary-vm"), calls.index("dns-secondary-vm"))
            self.assertIn("podman exec -i 'fortress-dns-primary-pihole' pihole-FTL sqlite3 /etc/pihole/gravity.db", calls)
            self.assertIn("podman exec 'fortress-dns-primary-pihole' pihole reloadlists", calls)
            self.assertIn("fortress-dns-filtering-exceptions", calls)
            self.assertIn("10.25.0.50", calls)
            self.assertIn(
                "DELETE FROM client_by_group "
                "WHERE group_id = (SELECT id FROM \"group\" WHERE name = 'Default')",
                calls,
            )
            self.assertIn(
                "AND client_id IN (SELECT client.id FROM client "
                "JOIN fortress_desired_dns_filtering_exception_clients desired ON desired.ip = client.ip)",
                calls,
            )
            self.assertIn(
                "DELETE FROM adlist_by_group "
                "WHERE group_id = (SELECT id FROM \"group\" WHERE name = 'fortress-dns-filtering-exceptions')",
                calls,
            )
            self.assertIn(
                "DELETE FROM domainlist_by_group "
                "WHERE group_id = (SELECT id FROM \"group\" WHERE name = 'fortress-dns-filtering-exceptions')",
                calls,
            )
            self.assertNotIn("systemctl restart", calls)

    def test_apply_converges_empty_declaration_by_ensuring_group_and_pruning_assignments(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            shutil.copytree(REPO_ROOT / "inventory", root / "inventory")
            (root / "inventory" / "dns-filtering-exceptions.yaml").write_text("exceptions: []\n")
            calls_log = root / "calls.log"
            self._write_fake_vm_shell(root, calls_log)

            result = self._run_apply(root)

            self.assertEqual(result.returncode, 0, result.stderr)
            calls = calls_log.read_text()
            self.assertIn('INSERT INTO "group"', calls)
            self.assertIn("fortress-dns-filtering-exceptions", calls)
            self.assertIn("DELETE FROM client_by_group", calls)
            self.assertNotIn("INSERT INTO fortress_desired_dns_filtering_exception_clients (ip, name) VALUES", calls)

    def test_apply_reports_failed_peer_without_rolling_back_successful_peers(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            shutil.copytree(REPO_ROOT / "inventory", root / "inventory")
            calls_log = root / "calls.log"
            self._write_fake_vm_shell(root, calls_log)

            result = self._run_apply(root, fail_on="dns-secondary-vm")

            self.assertEqual(result.returncode, 1)
            calls = calls_log.read_text()
            self.assertIn("vm-shell dns-primary-vm -- bash -s", calls)
            self.assertIn("vm-shell dns-secondary-vm -- bash -s", calls)
            self.assertIn("ok: apply DNS Filtering Exceptions for dns-primary on dns-primary-vm", result.stdout)
            self.assertIn("failed: apply DNS Filtering Exceptions for dns-secondary on dns-secondary-vm", result.stderr)
            self.assertIn("DNS Filtering Exceptions failed for: dns-secondary on dns-secondary-vm", result.stderr)
            self.assertNotIn("rollback", result.stdout.lower() + result.stderr.lower())

    def test_dns_runbook_documents_dns_filtering_exceptions_workflow(self):
        content = (REPO_ROOT / "runbooks" / "dns-architecture.md").read_text()
        normalized = " ".join(content.split()).lower()

        for phrase in [
            "DNS Filtering Exceptions",
            "inventory/dns-filtering-exceptions.yaml",
            "just dns-filtering-exceptions-apply",
            "scripts/dns-filtering-exceptions-apply --print",
            "missing or empty DNS Filtering Exceptions inventory means zero declared exceptions",
            "remove the last exception by leaving `exceptions: []` or deleting `inventory/dns-filtering-exceptions.yaml`",
            "fixed IPv4 assignment is handled outside Rite",
            "does not validate router VLAN membership",
            "does not create DHCP reservations",
            "fortress-managed Pi-hole group",
            "does not own manual Pi-hole groups",
            "domain allowlists",
            "blocklists",
            "adlists",
            "dns-primary-vm",
            "dns-secondary-vm",
            "pihole-FTL sqlite3 /etc/pihole/gravity.db",
            "pihole reloadlists",
        ]:
            with self.subTest(phrase=phrase):
                self.assertIn(" ".join(phrase.split()).lower(), normalized)

    def _run_apply(self, root, fail_on=""):
        env = {
            "FORTRESS_ROOT": str(root),
            "CALLS_LOG": str(root / "calls.log"),
            "FORTRESS_FAKE_VM_SHELL_FAIL_ON": fail_on,
        }
        return subprocess.run(
            [str(REPO_ROOT / "scripts" / "dns-filtering-exceptions-apply")],
            cwd=REPO_ROOT,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

    def _write_fake_vm_shell(self, root, calls_log):
        scripts = root / "scripts"
        scripts.mkdir(exist_ok=True)
        fake = scripts / "vm-shell"
        fake.write_text(
            "#!/usr/bin/env bash\n"
            "printf 'vm-shell %s\\n' \"$*\" >> \"$CALLS_LOG\"\n"
            "stdin=$(cat)\n"
            "if [ -n \"$stdin\" ]; then printf '%s\\n' \"$stdin\" >> \"$CALLS_LOG\"; fi\n"
            "if [ -n \"$FORTRESS_FAKE_VM_SHELL_FAIL_ON\" ]; then\n"
            "  case \" $* $stdin \" in *\"$FORTRESS_FAKE_VM_SHELL_FAIL_ON\"*) exit 42 ;; esac\n"
            "fi\n"
        )
        fake.chmod(fake.stat().st_mode | 0o100)


if __name__ == "__main__":
    unittest.main()
