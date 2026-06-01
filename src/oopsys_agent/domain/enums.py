from enum import Enum


class Severity(str, Enum):
    ERROR = "error"
    CRITICAL = "critical"


class Source(str, Enum):
    PROJECTS = "projects"
    SERVER = "server"
    DOCKER = "docker"
    AGENT = "agent"
