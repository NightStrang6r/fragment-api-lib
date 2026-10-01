"""The v2 client sends its auth key only in the Authorization header: a key in a URL ends up
in access logs. A local mock server records what arrives; nothing leaves this machine.

    python -m tests.test_v2_auth_header
"""
import json
import threading
import warnings
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from fragment_api_lib.client import FragmentAPIClient

KEY = "k" * 64
seen = []
ok = fail = 0


def check(name, cond, extra=""):
    global ok, fail
    if cond:
        ok += 1
    else:
        fail += 1
        print("FAIL:", name, extra)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        seen.append((self.path, self.headers.get("Authorization")))
        body = json.dumps({"success": True}).encode()
        self.send_response(200)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
threading.Thread(target=server.serve_forever, daemon=True).start()
warnings.simplefilter("ignore", DeprecationWarning)
api = FragmentAPIClient(base_url=f"http://127.0.0.1:{server.server_address[1]}", auth_key=KEY)

for name, call in [
    ("get_balance_v2", lambda: api.get_balance_v2()),
    ("get_user_info_v2", lambda: api.get_user_info_v2("durov")),
    ("get_orders_v2", lambda: api.get_orders_v2(limit=5, offset=10)),
]:
    seen.clear()
    call()
    path, header = seen[0] if seen else ("", None)
    check(f"{name}: no key in the URL", KEY not in path and "auth_key" not in path, path)
    check(f"{name}: key in the Authorization header", header == "Bearer " + KEY, header)

check("get_orders_v2 keeps limit and offset", "limit=5" in path and "offset=10" in path, path)
server.shutdown()
print(f"passed {ok}, failed {fail}")
raise SystemExit(1 if fail else 0)
