import os
from pathlib import Path
import subprocess
import tempfile
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
LAUNCHER = REPO_ROOT / "scripts" / "forgejo-mcp-local"


class ForgejoMcpLocalLauncherTests(unittest.TestCase):
    def test_passes_repository_token_to_host_binary_without_command_line_exposure(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            credentials = temp / "forgejo.env"
            credentials.write_text(
                "export FORGEJO_MCP_URL=https://unused.invalid/mcp\n"
                "export FORGEJO_MCP_TOKEN=fixture-token\n"
            )
            fake_server = temp / "forgejo-mcp"
            fake_server.write_text(
                "#!/bin/sh\n"
                "printf 'args=%s\\n' \"$*\"\n"
                "printf 'access-token=%s\\n' \"$FORGEJO_ACCESS_TOKEN\"\n"
                "printf 'mcp-token=%s\\n' \"${FORGEJO_MCP_TOKEN-unset}\"\n"
            )
            fake_server.chmod(0o755)

            environment = os.environ.copy()
            environment.update(
                FORGEJO_MCP_BIN=str(fake_server),
                FORGEJO_MCP_ENV_FILE=str(credentials),
            )
            completed = subprocess.run(
                [LAUNCHER],
                check=True,
                capture_output=True,
                env=environment,
                text=True,
            )

        self.assertIn("args=--transport stdio --url https://git.fearn.cloud", completed.stdout)
        self.assertIn("access-token=fixture-token", completed.stdout)
        self.assertIn("mcp-token=unset", completed.stdout)
        self.assertNotIn("fixture-token", completed.stdout.splitlines()[0])

    def test_rejects_a_credential_file_without_a_token(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            credentials = Path(temp_dir) / "forgejo.env"
            credentials.write_text("export FORGEJO_MCP_URL=https://unused.invalid/mcp\n")
            environment = os.environ.copy()
            environment.pop("FORGEJO_MCP_TOKEN", None)
            environment["FORGEJO_MCP_ENV_FILE"] = str(credentials)

            completed = subprocess.run(
                [LAUNCHER],
                capture_output=True,
                env=environment,
                text=True,
            )

        self.assertNotEqual(0, completed.returncode)
        self.assertIn("FORGEJO_MCP_TOKEN is missing", completed.stderr)


if __name__ == "__main__":
    unittest.main()
