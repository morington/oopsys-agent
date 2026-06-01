from dishka import Provider, Scope, from_context, provide
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from oopsys_agent.configuration import Configuration
from oopsys_agent.runtime import AppRuntime
from oopsys_agent.services.docker import DockerMonitor
from oopsys_agent.services.events import EventService
from oopsys_agent.services.monitor import SystemMonitor
from oopsys_agent.services.nats import NatsGateway
from oopsys_agent.services.scheduler import AgentScheduler
from oopsys_agent.services.server_client import ServerClient


class ServiceProvider(Provider):
    runtime = from_context(provides=AppRuntime, scope=Scope.APP)

    @provide(scope=Scope.APP)
    def system_monitor(self) -> SystemMonitor:
        return SystemMonitor()

    @provide(scope=Scope.APP)
    def docker_monitor(self) -> DockerMonitor:
        return DockerMonitor()

    @provide(scope=Scope.APP)
    def server_client(self, configuration: Configuration) -> ServerClient:
        return ServerClient(configuration.server, configuration.agent)

    @provide(scope=Scope.APP)
    def nats_gateway(
        self,
        configuration: Configuration,
        server_client: ServerClient,
        runtime: AppRuntime,
    ) -> NatsGateway:
        return NatsGateway(
            configuration.nats,
            server_client,
            runtime,
            retry_base=configuration.intervals.retry_base_seconds,
        )

    @provide(scope=Scope.APP)
    def scheduler(
        self,
        configuration: Configuration,
        runtime: AppRuntime,
        session_factory: async_sessionmaker[AsyncSession],
        system: SystemMonitor,
        docker: DockerMonitor,
        gateway: NatsGateway,
    ) -> AgentScheduler:
        return AgentScheduler(
            configuration=configuration,
            runtime=runtime,
            session_factory=session_factory,
            system=system,
            docker=docker,
            gateway=gateway,
        )

    @provide(scope=Scope.REQUEST)
    def events(
        self,
        session: AsyncSession,
        gateway: NatsGateway,
        configuration: Configuration,
    ) -> EventService:
        return EventService(session, gateway, subject_prefix=configuration.nats.subject_prefix)
