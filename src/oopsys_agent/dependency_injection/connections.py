from collections.abc import AsyncIterable

import structlog
from dishka import Provider, Scope, provide
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from oopsys_agent.configuration import Configuration, Loggers
from oopsys_agent.database import create_all

logger = structlog.getLogger(Loggers.providers.name)


class ConnectionProvider(Provider):
    scope = Scope.APP

    @provide
    async def engine(self, configuration: Configuration) -> AsyncIterable[AsyncEngine]:
        await logger.adebug("Create SQLite engine", url=configuration.sqlite.url())

        engine = create_async_engine(configuration.sqlite.url(), pool_pre_ping=True)
        await create_all(engine, sqlite_path=configuration.sqlite.path)
        yield engine
        await engine.dispose()

    @provide
    async def session_factory(self, engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
        return async_sessionmaker(engine, expire_on_commit=False)

    @provide(scope=Scope.REQUEST)
    async def session(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> AsyncIterable[AsyncSession]:
        async with session_factory() as session:
            yield session
