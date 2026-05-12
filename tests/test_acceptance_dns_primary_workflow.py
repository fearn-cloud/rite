import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
LISTENER_CHECK = (
    "tcp=\"$(ss -H -ltn 'sport = :53' || true)\"; "
    "udp=\"$(ss -H -lun 'sport = :53' || true)\"; "
    "printf 'TCP port 53 listeners:\\n%s\\n' \"$tcp\"; "
    "printf 'UDP port 53 listeners:\\n%s\\n' \"$udp\"; "
    "printf '%s\\n' \"$tcp\" | awk '{print $4}' | grep -Eq '^(10\\.40\\.0\\.11|\\*|0\\.0\\.0\\.0|\\[::\\]):53$' && "
    "printf '%s\\n' \"$udp\" | awk '{print $4}' | grep -Eq '^(10\\.40\\.0\\.11|\\*|0\\.0\\.0\\.0|\\[::\\]):53$'"
)


class AcceptanceDNSPrimaryWorkflowTests(unittest.TestCase):
    def test_acceptance_dns_primary_deploys_and_verifies_existing_resolver_by_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            calls_log = root / "calls.log"
            self._fake_script(root / "scripts" / "service-deploy")
            self._fake_script(root / "scripts" / "vm-shell")
            self._fake_script(root / "bin" / "dig")
            env = os.environ.copy()
            env["FORTRESS_ROOT"] = str(root)
            env["CALLS_LOG"] = str(calls_log)
            env["PATH"] = f"{root / 'bin'}:{env['PATH']}"

            result = subprocess.run(
                [
                    str(REPO_ROOT / "scripts" / "acceptance-dns-primary"),
                    "external=example.com",
                ],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("dns-primary acceptance: passed", result.stdout)
            self.assertIn("expecting existing DNS VM dns-primary-vm", result.stdout)
            self.assertEqual(
                [
                    "service-deploy dns-primary",
                    "vm-shell dns-primary-vm -- systemctl is-active fortress-dns-primary-unbound.service",
                    "vm-shell dns-primary-vm -- systemctl is-active fortress-dns-primary-pihole.service",
                    f"vm-shell dns-primary-vm -- sh -lc {LISTENER_CHECK}",
                    "vm-shell dns-primary-vm -- sudo podman exec fortress-dns-primary-pihole sh -lc test \"$FTLCONF_dns_upstreams\" = \"unbound\"",
                    "dns-query @10.40.0.11 example.com A",
                ],
                calls_log.read_text().splitlines(),
            )

    def test_acceptance_dns_primary_can_opt_into_internal_lookup_once_records_exist(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            calls_log = root / "calls.log"
            self._fake_script(root / "scripts" / "service-deploy")
            self._fake_script(root / "scripts" / "vm-shell")
            env = os.environ.copy()
            env["FORTRESS_ROOT"] = str(root)
            env["CALLS_LOG"] = str(calls_log)

            result = subprocess.run(
                [
                    str(REPO_ROOT / "scripts" / "acceptance-dns-primary"),
                    "internal=internal-ingress.fearn.cloud",
                ],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(
                [
                    "service-deploy dns-primary",
                    "vm-shell dns-primary-vm -- systemctl is-active fortress-dns-primary-unbound.service",
                    "vm-shell dns-primary-vm -- systemctl is-active fortress-dns-primary-pihole.service",
                    f"vm-shell dns-primary-vm -- sh -lc {LISTENER_CHECK}",
                    "vm-shell dns-primary-vm -- sudo podman exec fortress-dns-primary-pihole sh -lc test \"$FTLCONF_dns_upstreams\" = \"unbound\"",
                    "dns-query @10.40.0.11 example.com A",
                    "dns-query @10.40.0.11 internal-ingress.fearn.cloud A",
                ],
                calls_log.read_text().splitlines(),
            )

    def test_acceptance_dns_primary_can_run_vm_lifecycle_when_requested(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            calls_log = root / "calls.log"
            self._fake_script(root / "scripts" / "vm-up")
            self._fake_script(root / "scripts" / "service-deploy")
            self._fake_script(root / "scripts" / "vm-shell")
            self._fake_script(root / "bin" / "dig")
            env = os.environ.copy()
            env["FORTRESS_ROOT"] = str(root)
            env["CALLS_LOG"] = str(calls_log)
            env["PATH"] = f"{root / 'bin'}:{env['PATH']}"

            result = subprocess.run(
                [
                    str(REPO_ROOT / "scripts" / "acceptance-dns-primary"),
                    "provision=true",
                    "auto_confirm=true",
                ],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual("vm-up dns-primary-vm --auto-confirm", calls_log.read_text().splitlines()[0])

    def test_acceptance_dns_primary_is_exposed_through_just_and_runbook(self):
        justfile = (REPO_ROOT / "justfile").read_text()
        runbook = (REPO_ROOT / "runbooks" / "dns-architecture.md").read_text()

        self.assertIn('acceptance-dns-primary provision="false" auto_confirm="false" external="example.com" internal="":', justfile)
        self.assertIn("./scripts/acceptance-dns-primary", justfile)
        self.assertIn("just acceptance-dns-primary", runbook)
        self.assertIn("just acceptance-dns-primary provision=true auto_confirm=true", runbook)
        self.assertIn("just acceptance-dns-primary internal=internal-ingress.fearn.cloud", runbook)

    def _fake_script(self, path):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "#!/usr/bin/env bash\n"
            "printf '%s %s\\n' \"$(basename \"$0\")\" \"$*\" >> \"$CALLS_LOG\"\n"
        )
        path.chmod(path.stat().st_mode | stat.S_IXUSR)


if __name__ == "__main__":
    unittest.main()
