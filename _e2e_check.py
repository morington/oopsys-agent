import asyncio
import contextlib
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from oopsys_agent.configuration.config import AgentModel, NatsModel, ServerModel
from oopsys_agent.runtime import AppRuntime
from oopsys_agent.services.nats import NatsGateway
from oopsys_agent.services.server_client import ServerClient

RECEIVED: list[bytes] = []
ACCEPT = {"ok": True}


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        if ACCEPT["ok"]:
            RECEIVED.append(body)
            self.send_response(202)
        else:
            self.send_response(503)
        self.end_headers()

    def log_message(self, *args):
        pass


def run_server(httpd):
    httpd.serve_forever()


async def main():
    httpd = HTTPServer(("127.0.0.1", 18099), Handler)
    threading.Thread(target=run_server, args=(httpd,), daemon=True).start()

    nats = NatsModel(servers=["nats://127.0.0.1:14222"], durable="e2e", ack_wait=3.0)
    server = ServerModel(url="http://127.0.0.1:18099", ingest_path="/ingest", timeout=3.0)
    runtime = AppRuntime(agent_id="agent-e2e")
    client = ServerClient(server, AgentModel(token="t"))
    gw = NatsGateway(nats, client, runtime, retry_base=1.0)

    assert await gw.start(), "gateway failed to start"

    # 1) server up -> message delivered over HTTP
    await gw.publish("oopsys.agents.agent-e2e.projects", {"source": "projects", "n": 1})
    await asyncio.sleep(2)
    print("phase1 received:", len(RECEIVED), "server_reachable:", runtime.server_reachable)
    assert len(RECEIVED) == 1

    # 2) server down -> message stays in queue, retried
    ACCEPT["ok"] = False
    await gw.publish("oopsys.agents.agent-e2e.server", {"source": "server", "n": 2})
    await asyncio.sleep(4)
    before = len(RECEIVED)
    print("phase2 (down) delivered:", before, "server_reachable:", runtime.server_reachable)

    # 3) server back up -> queued message finally delivered
    ACCEPT["ok"] = True
    await asyncio.sleep(5)
    print("phase3 (recovered) received total:", len(RECEIVED))
    assert len(RECEIVED) >= 2, "message was lost!"

    await gw.close()
    httpd.shutdown()
    print("E2E OK")


with contextlib.suppress(KeyboardInterrupt):
    asyncio.run(main())
