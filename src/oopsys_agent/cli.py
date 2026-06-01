import argparse
import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from oopsys_agent.configuration import Configuration
from oopsys_agent.database import create_all
from oopsys_agent.services import TokenExistsError, TokenService


@asynccontextmanager
async def _session() -> AsyncIterator[AsyncSession]:
    configuration = Configuration()
    engine = create_async_engine(configuration.sqlite.url())
    await create_all(engine, sqlite_path=configuration.sqlite.path)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with factory() as session:
            yield session
    finally:
        await engine.dispose()


async def _token_create(label: str | None, *, force: bool) -> int:
    async with _session() as session:
        service = TokenService(session)
        try:
            created = await service.create_token(label=label, force=force)
        except TokenExistsError:
            print("An active token already exists. Use --force to revoke it and create a new one.")
            return 1
        agent_id = await service.get_agent_id()
        print("Token created (shown only once, store it now):")
        print(f"  agent_id: {agent_id}")
        print(f"  token:    {created.token}")
        return 0


async def _token_list() -> int:
    async with _session() as session:
        service = TokenService(session)
        identity = await service.ensure_identity()
        print(f"agent_id:        {identity.agent_id}")
        print(f"active token:    {'yes' if identity.token_hash else 'no'}")
        print(f"token label:     {identity.token_label or '-'}")
        print(f"token created:   {identity.token_created_at.isoformat() if identity.token_created_at else '-'}")
        return 0


async def _token_revoke() -> int:
    async with _session() as session:
        service = TokenService(session)
        revoked = await service.revoke_token()
        print("Token revoked." if revoked else "No active token to revoke.")
        return 0


def _run() -> int:
    from oopsys_agent.main import main

    asyncio.run(main())
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="oopsys-agent", description="oopsys local server agent")
    sub = parser.add_subparsers(dest="command", required=True)

    token = sub.add_parser("token", help="manage the agent token (server <-> agent)")
    token_sub = token.add_subparsers(dest="token_command", required=True)

    create = token_sub.add_parser("create", help="create a new token (shown once)")
    create.add_argument("--label", default=None, help="optional human-readable label")
    create.add_argument("--force", action="store_true", help="revoke the active token and create a new one")

    token_sub.add_parser("list", help="show agent_id and token status (never the plaintext)")
    token_sub.add_parser("revoke", help="revoke the active token")

    sub.add_parser("run", help="run the agent (HTTP API + monitoring)")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    if args.command == "run":
        return _run()
    if args.command == "token":
        if args.token_command == "create":
            return asyncio.run(_token_create(args.label, force=args.force))
        if args.token_command == "list":
            return asyncio.run(_token_list())
        if args.token_command == "revoke":
            return asyncio.run(_token_revoke())
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
