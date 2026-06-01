# Demo parser

Small loop on [oopsys-python](https://pypi.org/project/oopsys-python/) that sometimes hits parse errors and sends them to the agent.

## Run

```bash
# from repo root
docker compose up -d --build

cd examples/parser
docker compose up --build
```

Start the agent first (creates `oopsys-net`). The parser uses `OOPSYS_AGENT__HOST=oopsys-agent`.
