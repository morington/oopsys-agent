from dishka import Provider, Scope, provide

from oopsys_agent.configuration import Configuration


class ConfigurationProvider(Provider):
    scope = Scope.APP

    @provide
    def get_configuration(self) -> Configuration:
        return Configuration()
