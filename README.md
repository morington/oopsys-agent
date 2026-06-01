# oopsys-agent

> oops, system crashed :)

Local agent for a server: accepts error reports from [oopsys-python](https://pypi.org/project/oopsys-python/), collects host and Docker metrics, stores history in SQLite, and reliably ships everything to the central `oopsys-server` over HTTP.

The agent **never talks to the server directly from the hot path**. Every event is written into a local NATS JetStream queue first; a worker drains that queue and `POST`s to the server. If the server is down, the message stays in the queue and is retried later — nothing is lost.

```
oopsys-python ──HTTP /reports──▶ agent ──enqueue──▶ NATS JetStream (local, durable)
                                                          │
                                              forwarder worker (consumer)
                                                          │ HTTP POST (ack on 2xx, nack+retry otherwise)
                                                          ▼
                                                    oopsys-server

oopsys-server ──HTTP /health, /usage (Bearer)──▶ agent
```

---

## What it does

| Area | Behavior |
|------|----------|
| Projects | `POST /reports` — `ErrorReport` from apps (no auth; trusted Docker network) |
| Host | CPU, memory, network, load (psutil) |
| Docker | All containers on the host daemon (via mounted socket) |
| Queue | Events → local NATS JetStream (durable); survives restarts |
| Delivery | Forwarder worker consumes the queue and `POST`s to the server over HTTP; server down → nack → retried |
| Self | Agent faults → `source=agent` (separate from project errors) |
| Server API | `GET /ping` (public), `POST /health` and `POST /usage` (Bearer token) |

---

## Quick start

```bash
cp .env.example .env
docker compose up -d --build
docker compose exec agent oopsys-agent token create --label my-server
```

Bind the printed token on the server. Without a valid token, `POST /health` returns 401.

Local run (no Docker):

```bash
uv sync
uv run oopsys-agent run
```

---

## Queue (NATS subjects)

NATS is the agent's **local, durable buffer** — not a transport to the server. The forwarder worker consumes these subjects and delivers the payload to the server over HTTP.

Prefix: `NATS__SUBJECT_PREFIX` (default `oopsys`). Stream: `NATS__STREAM` (default `OOPSYS`). Consumer: `NATS__DURABLE`.

| Subject | Source | Payload |
|---------|--------|---------|
| `oopsys.agents.<agent_id>.projects` | Project errors | `ErrorReport` |
| `oopsys.agents.<agent_id>.server` | Host metrics | `ServerMetrics` |
| `oopsys.agents.<agent_id>.docker` | Containers | `ContainerState` |
| `oopsys.agents.<agent_id>.agent` | Agent faults | `AgentFault` |

Envelope (what the server receives): `{schema_version, agent_id, source, occurred_at, payload}`.

Errors are enqueued immediately; metrics on `INTERVALS__METRICS_SECONDS`.

---

## API

| Method | Path | Auth |
|--------|------|------|
| POST | `/reports` | — |
| GET | `/ping` | — |
| POST | `/health` | Bearer |
| POST | `/usage` | Bearer |

---

## Delivery to the server

The forwarder posts each envelope to `SERVER__URL` + `SERVER__INGEST_PATH` with `Authorization: Bearer <AGENT__TOKEN>`. On HTTP `2xx` the message is acked and dropped from the queue; on any error it is nacked and retried (`max_deliver` is unlimited, redelivery after `NATS__ACK_WAIT`).

---

## Token (server ↔ agent)

Identifies the **agent**, not a user. One token can be linked from several server accounts. The agent stores only the token hash (used to verify incoming `POST /health` / `POST /usage` calls). For outbound delivery the forwarder uses the plaintext `AGENT__TOKEN` from the environment as a Bearer credential.

```bash
docker compose exec agent oopsys-agent token create --label my-server
docker compose exec agent oopsys-agent token list
docker compose exec agent oopsys-agent token create --force   # revoke old, create new
docker compose exec agent oopsys-agent token revoke
```

Optional: `AGENT__TOKEN` in `.env` — saved if none exists; must match hash if one exists.

---

## Docker socket

Required for container metrics:

```yaml
volumes:
  - /var/run/docker.sock:/var/run/docker.sock:ro
```

The agent runs in a container but sees the **host** Docker daemon. Without the socket it keeps running (host metrics only) and reports `docker monitor unavailable` in `/health`.

`:ro` is a mount flag only — socket access is still a high-privilege trust boundary on the host.

Container grouping is done on the server; the agent sends raw container data and labels.

---

## Example

[examples/parser](examples/parser) — demo parser on `oopsys-python` that fails sometimes and posts to the agent. Uses network `oopsys-net` from the agent compose.

---

## Configuration

See [.env.example](.env.example). Nested keys use `__` (e.g. `NATS__SERVERS`).
