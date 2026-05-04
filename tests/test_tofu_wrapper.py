import os
import shutil
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURES = REPO_ROOT / "tests" / "fixtures"


class TofuWrapperTests(unittest.TestCase):
    def test_wrap_decrypts_host_tokens_generates_hcl_and_invokes_tofu_from_tofu_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, calls_log = self._wrapper_fixture(tmp)
            env = self._fake_tools(root, calls_log)

            result = subprocess.run(
                [str(REPO_ROOT / "scripts" / "tofu-wrap"), "plan", "-input=false"],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual("", result.stdout)
            self.assertEqual("", result.stderr)
            calls = calls_log.read_text()
            self.assertIn("sops --decrypt --extract [\"pve_tokens\"][\"tofu\"][\"value\"]", calls)
            self.assertNotIn("sops --decrypt /", calls)
            self.assertIn("inventory/hosts/wintermute.sops.yaml", calls)
            self.assertIn("inventory/hosts/neuromancer.sops.yaml", calls)
            self.assertIn("tofu-generated present", calls)
            self.assertIn(f"tofu-cwd {root / 'tofu'}", calls)
            self.assertIn("tofu-env TF_VAR_pve_token_neuromancer=neuromancer-secret", calls)
            self.assertIn("tofu-env TF_VAR_pve_token_wintermute=wintermute-secret", calls)
            self.assertNotIn("TF_VAR_pve_token_molly", calls)

    def test_wrap_fails_before_tofu_when_host_sibling_sops_file_is_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, calls_log = self._wrapper_fixture(tmp)
            (root / "inventory" / "hosts" / "neuromancer.sops.yaml").unlink()
            env = self._fake_tools(root, calls_log)

            result = subprocess.run(
                [str(REPO_ROOT / "scripts" / "tofu-wrap"), "plan"],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            self.assertEqual(result.returncode, 1)
            self.assertEqual("", result.stdout)
            self.assertIn("missing Host Sibling SOPS File", result.stderr)
            self.assertIn("neuromancer", result.stderr)
            self.assertNotIn("tofu plan", calls_log.read_text() if calls_log.exists() else "")

    def test_wrap_fails_before_tofu_when_tofu_token_value_is_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, calls_log = self._wrapper_fixture(tmp)
            env = self._fake_tools(root, calls_log)
            env["FORTRESS_FAKE_EMPTY_TOKEN_FOR"] = "neuromancer"

            result = subprocess.run(
                [str(REPO_ROOT / "scripts" / "tofu-wrap"), "plan"],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            self.assertEqual(result.returncode, 1)
            self.assertEqual("", result.stdout)
            self.assertIn("missing pve_tokens.tofu.value", result.stderr)
            self.assertIn("neuromancer", result.stderr)
            self.assertNotIn("wintermute-secret", result.stderr)
            self.assertNotIn("tofu plan", calls_log.read_text() if calls_log.exists() else "")

    def test_docs_state_tofu_wrap_is_the_supported_entry_point(self):
        docs = (REPO_ROOT / "docs" / "opentofu.md").read_text()

        self.assertIn("scripts/tofu-wrap", docs)
        self.assertIn("Direct `tofu` invocation is unsupported", docs)
        self.assertIn("Tofu must never read SOPS", docs)

    def _wrapper_fixture(self, tmp):
        root = Path(tmp)
        shutil.copytree(FIXTURES / "inventory_valid", root, dirs_exist_ok=True)
        host_dir = root / "inventory" / "hosts"
        (host_dir / "neuromancer.yaml").write_text(
            "proxmox:\n"
            "  pve_node_name: neuromancer\n"
            "network:\n"
            "  management_address: 10.0.0.11\n"
        )
        (host_dir / "wintermute.sops.yaml").write_text("encrypted wintermute\n")
        (host_dir / "neuromancer.sops.yaml").write_text("encrypted neuromancer\n")
        (root / "tofu").mkdir(exist_ok=True)
        calls_log = root / "calls.log"
        return root, calls_log

    def _fake_tools(self, root, calls_log):
        bin_dir = root / "bin"
        bin_dir.mkdir()
        for name, body in {
            "sops": (
                "#!/usr/bin/env bash\n"
                "printf 'sops %s\\n' \"$*\" >> \"$CALLS_LOG\"\n"
                "if [ \"$2\" != \"--extract\" ]; then exit 2; fi\n"
                "if [ -n \"$FORTRESS_FAKE_EMPTY_TOKEN_FOR\" ] && [[ \"$*\" == *\"$FORTRESS_FAKE_EMPTY_TOKEN_FOR.sops.yaml\"* ]]; then exit 0; fi\n"
                "case \"$*\" in\n"
                "  *wintermute.sops.yaml*) printf 'wintermute-secret\\n' ;;\n"
                "  *neuromancer.sops.yaml*) printf 'neuromancer-secret\\n' ;;\n"
                "  *) exit 1 ;;\n"
                "esac\n"
            ),
            "tofu": (
                "#!/usr/bin/env bash\n"
                "printf 'tofu %s\\n' \"$*\" >> \"$CALLS_LOG\"\n"
                "printf 'tofu-cwd %s\\n' \"$PWD\" >> \"$CALLS_LOG\"\n"
                "[ -f generated-providers.tf ] && printf 'tofu-generated present\\n' >> \"$CALLS_LOG\"\n"
                "env | sort | grep '^TF_VAR_pve_token_' | sed 's/^/tofu-env /' >> \"$CALLS_LOG\"\n"
            ),
        }.items():
            tool = bin_dir / name
            tool.write_text(body)
            tool.chmod(tool.stat().st_mode | stat.S_IXUSR)

        env = os.environ.copy()
        env["PATH"] = f"{bin_dir}:{env['PATH']}"
        env["FORTRESS_ROOT"] = str(root)
        env["CALLS_LOG"] = str(calls_log)
        return env
