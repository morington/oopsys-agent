# oopsys-agent

> oops, system crashed :)

Local agent for a server: accepts error reports from [oopsys-python](https://pypi.org/project/oopsys-python/), collects host and Docker metrics, stores history in SQLite, and publishes to NATS JetStream (with a local outbox).

---

## What it does

| Area | Behavior |
|------|----------|
| Projects | `POST /reports` — `ErrorReport` from apps (no auth; trusted Docker network) |
| Host | CPU, memory, network, load (psutil) |
| Docker | All containers on the host daemon (via mounted socket) |
| Delivery | SQLite history + outbox → NATS JetStream; ack before mark delivered |
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

## NATS subjects

Prefix: `NATS__SUBJECT_PREFIX` (default `oopsys`). Stream: `NATS__STREAM` (default `OOPSYS`).

| Subject | Source | Payload |
|---------|--------|---------|
| `oopsys.agents.<agent_id>.projects` | Project errors | `ErrorReport` |
| `oopsys.agents.<agent_id>.server` | Host metrics | `ServerMetrics` |
| `oopsys.agents.<agent_id>.docker` | Containers | `ContainerState` |
| `oopsys.agents.<agent_id>.agent` | Agent faults | `AgentFault` |

Envelope: `{schema_version, agent_id, source, occurred_at, payload}`.

Errors are published immediately; metrics on `INTERVALS__METRICS_SECONDS`.

---

## API

| Method | Path | Auth |
|--------|------|------|
| POST | `/reports` | — |
| GET | `/ping` | — |
| POST | `/health` | Bearer |
| POST | `/usage` | Bearer |

---

## Token (server ↔ agent)

Identifies the **agent**, not a user. One token can be linked from several server accounts. Only the hash is stored locally.

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
