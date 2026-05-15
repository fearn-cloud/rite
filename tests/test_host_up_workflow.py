import os
import stat
import subprocess
import tempfile
import time
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


class HostUpWorkflowTests(unittest.TestCase):
    def test_just_host_up_calls_workflow_script_with_defaults(self):
        justfile = (REPO_ROOT / "justfile").read_text()

        self.assertIn('host-up host endpoint="all" auto_confirm="false" keep_on_fail="false":', justfile)
        self.assertIn("./scripts/host-up {{host}} endpoint={{endpoint}} auto_confirm={{auto_confirm}} keep_on_fail={{keep_on_fail}}", justfile)

    def test_new_host_runbook_documents_host_readiness_operator_workflow(self):
        content = (REPO_ROOT / "runbooks" / "new-host.md").read_text()

        self.assertIn("just host-up <host> endpoint=all auto_confirm=false keep_on_fail=false", content)
        self.assertIn("endpoint=all", content)
        self.assertIn("every declared NAS Endpoint", content)
        self.assertIn("endpoint=<name>", content)
        self.assertIn("scopes acceptance to one NAS Endpoint", content)
        self.assertIn("stored per-Host credential proves SSH reachability", content)
        self.assertIn("full Host Configure", content)
        self.assertIn("builds all Host-declared Templates", content)
        self.assertIn("verifies all Host-declared Templates", content)
        self.assertIn("Template x NAS Endpoint", content)
        self.assertIn("A Host with no declared Templates cannot pass Host Readiness", content)
        self.assertIn("auto_confirm=true", content)
        self.assertIn("supported downstream phases non-interactive", content)
        self.assertIn("keep_on_fail=true", content)
        self.assertIn("preserves generated artifacts", content)
        self.assertIn("stop later cells to avoid artifact collisions", content)
        self.assertIn("lower-level commands", content)
        self.assertIn("phase scoping", content)

    def test_rejects_host_equals_positional_argument_with_just_guidance(self):
        result = subprocess.run(
            [str(REPO_ROOT / "scripts" / "host-up"), "host=wintermute"],
            cwd=REPO_ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        self.assertEqual(result.returncode, 2)
        self.assertIn("host-up takes the host name as a positional argument", result.stderr)
        self.assertIn("just host-up wintermute", result.stderr)

    def test_missing_sops_bootstraps_then_runs_full_readiness_in_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, calls_log = self._fixture(tmp, include_sops=False)
            env = self._workflow_env(root, calls_log)

            result = subprocess.run(
                [str(REPO_ROOT / "scripts" / "host-up"), "wintermute"],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(
                [
                    "host-bootstrap wintermute",
                    "host-shell wintermute -- true",
                    "host-configure wintermute proxmox_repos,system_hygiene,proxmox_network,proxmox_users,gpu_passthrough",
                    "templates-build wintermute",
                    "template-verify host=wintermute template=debian-13-base keep_on_fail=false",
                    "acceptance-nfs-shared-mount host=wintermute template=debian-13-base endpoint=backup auto_confirm=false keep_on_fail=false",
                    "acceptance-service-layer host=wintermute template=debian-13-base endpoint=backup auto_confirm=false keep_on_fail=false",
                    "acceptance-nfs-shared-mount host=wintermute template=debian-13-base endpoint=truenas auto_confirm=false keep_on_fail=false",
                    "acceptance-service-layer host=wintermute template=debian-13-base endpoint=truenas auto_confirm=false keep_on_fail=false",
                ],
                calls_log.read_text().splitlines(),
            )
            self.assertIn("bootstrap: ran", result.stdout)
            self.assertIn("host-readiness: passed", result.stdout)

    def test_satisfied_bootstrap_verifies_sops_and_host_reachability_before_configure(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, calls_log = self._fixture(tmp)
            env = self._workflow_env(root, calls_log)

            result = subprocess.run(
                [str(REPO_ROOT / "scripts" / "host-up"), "wintermute", "endpoint=truenas"],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            calls = calls_log.read_text().splitlines()
            self.assertEqual(
                calls[0],
                f"sops --decrypt --extract [\"ssh_keys\"][\"bootstrap\"][\"private_key\"] "
                f"{root / 'inventory' / 'hosts' / 'wintermute.sops.yaml'}",
            )
            self.assertEqual(calls[1], "host-shell wintermute -- true")
            self.assertNotIn("host-bootstrap", calls_log.read_text())
            self.assertIn("endpoint=truenas", calls_log.read_text())
            self.assertNotIn("endpoint=backup", calls_log.read_text())
            self.assertIn("bootstrap: satisfied", result.stdout)

    def test_streams_downstream_phase_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, _calls_log = self._fixture(tmp)
            env = self._workflow_env(root, root / "calls.log")
            env["OUTPUT_PHASE"] = "template-verify"

            result = subprocess.run(
                [str(REPO_ROOT / "scripts" / "host-up"), "wintermute", "endpoint=truenas"],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("template-verify progress", result.stdout)
            self.assertIn("template-verify debian-13-base: passed", result.stdout)

    def test_streams_downstream_prompt_without_waiting_for_newline(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, _calls_log = self._fixture(tmp)
            env = self._workflow_env(root, root / "calls.log")
            env["PROMPT_PHASE"] = "acceptance-nfs-shared-mount"

            process = subprocess.Popen(
                [str(REPO_ROOT / "scripts" / "host-up"), "wintermute", "endpoint=truenas"],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            stdout = self._read_until(process, "Type 'acceptance nfs shared mount' to continue: ")
            self.assertIn("peer: tmp-nfs-peer VMID 8912 10.10.0.232/24", stdout)
            self.assertIn("Type 'acceptance nfs shared mount' to continue: ", stdout)
            assert process.stdin is not None
            process.stdin.write("acceptance nfs shared mount\n")
            process.stdin.flush()
            remaining_stdout, stderr = process.communicate(timeout=5)
            self.assertEqual(process.returncode, 0, stderr)
            self.assertIn("host-readiness: passed", stdout + remaining_stdout)

    def test_ambiguous_sops_stops_before_configure(self):
        scenarios = {
            "undecryptable": {"SOPS_FAIL": "1"},
            "missing-key": {"SOPS_PLAINTEXT": "ssh_keys:\n  bootstrap:\n    public_key: nope\n"},
        }
        for _name, overrides in scenarios.items():
            with self.subTest(overrides=overrides), tempfile.TemporaryDirectory() as tmp:
                root, calls_log = self._fixture(tmp)
                env = self._workflow_env(root, calls_log)
                env.update(overrides)

                result = subprocess.run(
                    [str(REPO_ROOT / "scripts" / "host-up"), "wintermute"],
                    cwd=REPO_ROOT,
                    env=env,
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )

                self.assertEqual(result.returncode, 1)
                self.assertIn("Host Sibling SOPS File", result.stderr)
                self.assertNotIn("host-configure", calls_log.read_text())
                self.assertIn("host-readiness: failed", result.stdout)

    def test_validates_host_templates_and_endpoint_before_downstream_workflows(self):
        scenarios = [
            ("ghost", "endpoint=all", "Host 'ghost' is not declared"),
            ("molly", "endpoint=all", "declares no Templates"),
            ("wintermute", "endpoint=missing", "NAS Endpoint 'missing' is not declared"),
        ]
        for host, endpoint_arg, message in scenarios:
            with self.subTest(host=host, endpoint_arg=endpoint_arg), tempfile.TemporaryDirectory() as tmp:
                root, calls_log = self._fixture(tmp)
                (root / "inventory" / "hosts" / "molly.yaml").write_text("proxmox:\n  templates: []\n")
                env = self._workflow_env(root, calls_log)

                result = subprocess.run(
                    [str(REPO_ROOT / "scripts" / "host-up"), host, endpoint_arg],
                    cwd=REPO_ROOT,
                    env=env,
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )

                self.assertEqual(result.returncode, 1)
                self.assertIn(message, result.stderr)
                self.assertFalse(calls_log.exists())
                self.assertIn("host-readiness: failed", result.stdout)

    def test_auto_confirm_and_keep_on_fail_pass_only_to_supported_workflows(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, calls_log = self._fixture(tmp)
            env = self._workflow_env(root, calls_log)

            result = subprocess.run(
                [
                    str(REPO_ROOT / "scripts" / "host-up"),
                    "wintermute",
                    "auto_confirm=true",
                    "keep_on_fail=true",
                ],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            calls = calls_log.read_text()
            self.assertIn("template-verify host=wintermute template=debian-13-base keep_on_fail=true", calls)
            self.assertIn("acceptance-nfs-shared-mount host=wintermute template=debian-13-base endpoint=backup auto_confirm=true keep_on_fail=true", calls)
            self.assertIn("acceptance-service-layer host=wintermute template=debian-13-base endpoint=truenas auto_confirm=true keep_on_fail=true", calls)
            self.assertNotIn("host-configure wintermute auto_confirm", calls)
            self.assertNotIn("templates-build wintermute auto_confirm", calls)

    def test_prerequisite_failures_stop_immediately(self):
        phases = [
            ("host-configure", "templates-build"),
            ("templates-build", "template-verify"),
            ("template-verify", "acceptance-nfs-shared-mount"),
        ]
        for failing_phase, later_phase in phases:
            with self.subTest(failing_phase=failing_phase), tempfile.TemporaryDirectory() as tmp:
                root, calls_log = self._fixture(tmp)
                env = self._workflow_env(root, calls_log)
                env["FAIL_PHASE"] = failing_phase

                result = subprocess.run(
                    [str(REPO_ROOT / "scripts" / "host-up"), "wintermute"],
                    cwd=REPO_ROOT,
                    env=env,
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )

                self.assertEqual(result.returncode, 1)
                self.assertIn(failing_phase, result.stderr)
                self.assertNotIn(later_phase, calls_log.read_text())
                self.assertIn("host-readiness: failed", result.stdout)

    def test_acceptance_failures_aggregate_when_cleanup_removes_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, calls_log = self._fixture(tmp)
            env = self._workflow_env(root, calls_log)
            env["FAIL_PHASE"] = "acceptance-nfs-shared-mount"

            result = subprocess.run(
                [str(REPO_ROOT / "scripts" / "host-up"), "wintermute"],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            self.assertEqual(result.returncode, 1)
            self.assertEqual(calls_log.read_text().count("acceptance-nfs-shared-mount"), 2)
            self.assertEqual(calls_log.read_text().count("acceptance-service-layer"), 2)
            self.assertIn("acceptance nfs-shared-mount debian-13-base@backup: failed", result.stdout)
            self.assertIn("acceptance service-layer debian-13-base@truenas: passed", result.stdout)
            self.assertIn("host-readiness: failed", result.stdout)

    def test_acceptance_failure_with_keep_on_fail_stops_to_avoid_artifact_collision(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, calls_log = self._fixture(tmp)
            env = self._workflow_env(root, calls_log)
            env["FAIL_PHASE"] = "acceptance-nfs-shared-mount"

            result = subprocess.run(
                [str(REPO_ROOT / "scripts" / "host-up"), "wintermute", "keep_on_fail=true"],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            self.assertEqual(result.returncode, 1)
            self.assertEqual(calls_log.read_text().count("acceptance-nfs-shared-mount"), 1)
            self.assertNotIn("acceptance-service-layer", calls_log.read_text())
            self.assertIn("preserved artifacts may collide", result.stderr)

    def _fixture(self, tmp, include_sops=True):
        root = Path(tmp)
        (root / "inventory" / "hosts").mkdir(parents=True)
        (root / "inventory" / "nas").mkdir(parents=True)
        (root / "inventory" / "templates").mkdir(parents=True)
        (root / "scripts").mkdir()
        (root / "inventory" / "hosts" / "wintermute.yaml").write_text(
            "proxmox:\n"
            "  templates: [debian-13-base]\n"
        )
        (root / "inventory" / "nas" / "backup.yaml").write_text("management_address: 10.10.0.12\n")
        (root / "inventory" / "nas" / "truenas.yaml").write_text("management_address: 10.10.0.10\n")
        (root / "inventory" / "templates" / "debian-13-base.yaml").write_text("vmid: 9001\n")
        if include_sops:
            (root / "inventory" / "hosts" / "wintermute.sops.yaml").write_text("encrypted\n")

        calls_log = root / "calls.log"
        for name in [
            "host-bootstrap",
            "host-shell",
            "host-configure",
            "templates-build",
            "template-verify",
            "acceptance-nfs-shared-mount",
            "acceptance-service-layer",
        ]:
            self._fake_script(root / "scripts" / name, calls_log, name)
        return root, calls_log

    def _workflow_env(self, root, calls_log):
        bin_dir = root / "bin"
        bin_dir.mkdir()
        fake_sops = bin_dir / "sops"
        fake_sops.write_text(
            "#!/usr/bin/env bash\n"
            "printf 'sops %s\\n' \"$*\" >> \"$CALLS_LOG\"\n"
            "if [ -n \"$SOPS_FAIL\" ]; then echo decrypt failed >&2; exit 1; fi\n"
            "plaintext=\"${SOPS_PLAINTEXT:-ssh_keys:\n    bootstrap:\n        private_key: test-key\n}\"\n"
            "if [ \"$2\" = \"--extract\" ]; then\n"
            "  if [[ \"$plaintext\" != *private_key:* ]]; then echo 'private_key not found' >&2; exit 1; fi\n"
            "  printf '%s' 'test-key'\n"
            "else\n"
            "  printf '%s' \"$plaintext\"\n"
            "fi\n"
        )
        fake_sops.chmod(fake_sops.stat().st_mode | stat.S_IXUSR)
        env = os.environ.copy()
        env["FORTRESS_ROOT"] = str(root)
        env["CALLS_LOG"] = str(calls_log)
        env["PATH"] = f"{bin_dir}:{env['PATH']}"
        return env

    def _fake_script(self, path, calls_log, name):
        path.write_text(
            "#!/usr/bin/env bash\n"
            f"printf '{name} %s\\n' \"$*\" >> {str(calls_log)!r}\n"
            f"if [ \"$OUTPUT_PHASE\" = \"{name}\" ]; then echo '{name} progress'; fi\n"
            f"if [ \"$PROMPT_PHASE\" = \"{name}\" ]; then\n"
            "  echo 'peer: tmp-nfs-peer VMID 8912 10.10.0.232/24'\n"
            "  printf \"Type 'acceptance nfs shared mount' to continue: \"\n"
            "  read -r _response\n"
            "fi\n"
            f"if [ \"$FAIL_PHASE\" = \"{name}\" ]; then echo '{name} failed' >&2; exit 1; fi\n"
        )
        path.chmod(path.stat().st_mode | stat.S_IXUSR)

    def _read_until(self, process, needle, timeout=5):
        assert process.stdout is not None
        fd = process.stdout.fileno()
        os.set_blocking(fd, False)
        output = ""
        deadline = time.monotonic() + timeout
        while needle not in output and time.monotonic() < deadline:
            try:
                chunk = os.read(fd, 4096)
            except BlockingIOError:
                time.sleep(0.01)
                continue
            if not chunk:
                return output
            output += chunk.decode(errors="replace")
        os.set_blocking(fd, True)
        return output


if __name__ == "__main__":
    unittest.main()
