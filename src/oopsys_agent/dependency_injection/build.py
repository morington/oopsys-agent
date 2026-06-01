from typing import Any

from dishka import AsyncContainer, make_async_container
from dishka.provider import BaseProvider

from oopsys_agent.dependency_injection.configuration import ConfigurationProvider
from oopsys_agent.dependency_injection.connections import ConnectionProvider
from oopsys_agent.dependency_injection.services import ServiceProvider


def build_container(*providers: BaseProvider, context: dict[Any, Any] | None = None) -> AsyncContainer:
    return make_async_container(
        ConfigurationProvider(),
        ConnectionProvider(),
        ServiceProvider(),
        *providers,
        context=context,
    )
