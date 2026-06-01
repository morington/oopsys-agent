import asyncio
from contextlib import asynccontextmanager

from dishka import AsyncContainer
from dishka.integrations.fastapi import FastapiProvider, setup_dishka
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from structlog import getLogger
from uvicorn import Config, Server

from oopsys_agent.api import include_routers
from oopsys_agent.configuration import Configuration, Loggers
from oopsys_agent.dependency_injection import build_container
from oopsys_agent.runtime import AppRuntime
from oopsys_agent.services import TokenService
from oopsys_agent.services.nats import NatsGateway
from oopsys_agent.services.scheduler import AgentScheduler

logger = getLogger(Loggers.main.name)


async def _bootstrap_identity(container: AsyncContainer, runtime: AppRuntime, configuration: Configuration) -> None:
    session_factory = await container.get(async_sessionmaker[AsyncSession])
    async with session_factory() as session:
        service = TokenService(session)
        runtime.agent_id = await service.get_agent_id()
        if configuration.agent.token:
            await service.reconcile_env_token(configuration.agent.token)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await logger.ainfo("Application starting up...")
    container = app.state.dishka_container
    runtime: AppRuntime = await container.get(AppRuntime)
    configuration: Configuration = await container.get(Configuration)

    await _bootstrap_identity(container, runtime, configuration)
    await logger.ainfo("Agent identity ready", agent_id=runtime.agent_id)

    gateway: NatsGateway = await container.get(NatsGateway)
    await gateway.start()

    scheduler: AgentScheduler = await container.get(AgentScheduler)
    await scheduler.start()

    try:
        yield
    finally:
        await scheduler.stop()
        await gateway.close()
        await container.close()
        await logger.awarning("Application shut down")


def create_app(container: AsyncContainer) -> FastAPI:
    app = FastAPI(lifespan=lifespan, title="oopsys-agent")
    setup_dishka(container=container, app=app)
    include_routers(app)
    return app


async def main() -> None:
    runtime = AppRuntime()
    container = build_container(FastapiProvider(), context={AppRuntime: runtime})
    configuration: Configuration = await container.get(Configuration)

    Loggers(developer_mode=configuration.is_development)

    app = create_app(container)
    server = Server(
        config=Config(
            app=app,
            host=configuration.application.host,
            port=configuration.application.port,
            log_config=None,
        )
    )

    try:
        await logger.ainfo(f"Opening the agent {configuration.application.url()}..")
        await server.serve()
    except asyncio.CancelledError:
        await logger.awarning("Uvicorn server task cancelled")
        raise


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.warning("Application interrupted by user")
