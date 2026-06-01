from dishka import Provider, Scope, from_context, provide
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from oopsys_agent.configuration import Configuration
from oopsys_agent.runtime import AppRuntime
from oopsys_agent.services.docker import DockerMonitor
from oopsys_agent.services.monitor import SystemMonitor
from oopsys_agent.services.outbox import OutboxService
from oopsys_agent.services.publisher import NatsPublisher
from oopsys_agent.services.scheduler import AgentScheduler


class ServiceProvider(Provider):
    runtime = from_context(provides=AppRuntime, scope=Scope.APP)

    @provide(scope=Scope.APP)
    def system_monitor(self) -> SystemMonitor:
        return SystemMonitor()

    @provide(scope=Scope.APP)
    def docker_monitor(self) -> DockerMonitor:
        return DockerMonitor()

    @provide(scope=Scope.APP)
    def nats_publisher(self, configuration: Configuration) -> NatsPublisher:
        return NatsPublisher(configuration.nats)

    @provide(scope=Scope.APP)
    def scheduler(
        self,
        configuration: Configuration,
        runtime: AppRuntime,
        session_factory: async_sessionmaker[AsyncSession],
        system: SystemMonitor,
        docker: DockerMonitor,
        publisher: NatsPublisher,
    ) -> AgentScheduler:
        return AgentScheduler(
            configuration=configuration,
            runtime=runtime,
            session_factory=session_factory,
            system=system,
            docker=docker,
            publisher=publisher,
        )

    @provide(scope=Scope.REQUEST)
    def outbox(self, session: AsyncSession, configuration: Configuration) -> OutboxService:
        return OutboxService(session, subject_prefix=configuration.nats.subject_prefix)
