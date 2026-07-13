import json
import os
import subprocess
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from fortress_inventory.model import load_inventory_tree


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "forgejo-mcp-auth-proof"


class ForgejoMcpAuthProofTests(unittest.TestCase):
    def test_inventory_has_no_global_forgejo_token_source(self):
        service = load_inventory_tree(REPO_ROOT).services["forgejo-mcp"]
        container = service["deploy"]["containers"][0]
        rendered = json.dumps(container).lower()

        self.assertNotIn("--token", rendered)
        self.assertNotIn("forgejo_access_token", rendered)
        self.assertNotIn("gitea_access_token", rendered)
        self.assertNotIn("secret", rendered)

    def test_proof_exercises_session_bound_token_bearer_missing_bad_and_origin_requests(self):
        observed = []

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                observed.append({"headers": dict(self.headers), "payload": payload})
                if payload["method"] == "initialize":
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Mcp-Session-Id", "test-session")
                    self.end_headers()
                    self.wfile.write(b'{"jsonrpc":"2.0","id":1,"result":{}}')
                    return

                authorization = self.headers.get("Authorization")
                if authorization == "token token-secret":
                    login = "first-user"
                elif authorization == "Bearer bearer-secret":
                    login = "second-user"
                else:
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(b'{"jsonrpc":"2.0","id":2,"result":{"isError":true}}')
                    return
                body = json.dumps(
                    {
                        "jsonrpc": "2.0",
                        "id": 2,
                        "result": {"content": [{"text": json.dumps({"Result": {"login": login}})}]},
                    }
                ).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, _format, *_args):
                pass

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever)
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(thread.join)
        self.addCleanup(server.shutdown)
        env = os.environ | {
            "FORGEJO_MCP_URL": f"http://127.0.0.1:{server.server_port}",
            "FORGEJO_MCP_TOKEN_AUTH_TOKEN": "token-secret",
            "FORGEJO_MCP_BEARER_AUTH_TOKEN": "bearer-secret",
            "FORGEJO_MCP_TOKEN_AUTH_LOGIN": "first-user",
            "FORGEJO_MCP_BEARER_AUTH_LOGIN": "second-user",
        }
        result = subprocess.run([sys.executable, str(SCRIPT)], cwd=REPO_ROOT, env=env, text=True, capture_output=True)

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertNotIn("token-secret", result.stdout + result.stderr)
        self.assertNotIn("bearer-secret", result.stdout + result.stderr)
        self.assertEqual(6, len(observed))
        self.assertTrue(all(request["headers"]["Accept"] == "application/json, text/event-stream" for request in observed))
        self.assertTrue(all(request["headers"]["Content-Type"] == "application/json" for request in observed))
        self.assertEqual("test-session", observed[1]["headers"]["Mcp-Session-Id"])
        self.assertIsNone(observed[1]["headers"].get("Authorization"))
        self.assertEqual("token token-secret", observed[2]["headers"]["Authorization"])
        self.assertEqual("Bearer bearer-secret", observed[3]["headers"]["Authorization"])
        self.assertEqual("Bearer fortress-invalid-token", observed[4]["headers"]["Authorization"])
        self.assertEqual("https://fortress-origin-probe.invalid", observed[5]["headers"]["Origin"])


if __name__ == "__main__":
    unittest.main()
