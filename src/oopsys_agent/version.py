from importlib.metadata import PackageNotFoundError, version


def get_version() -> str:
    try:
        return version("oopsys-agent")
    except PackageNotFoundError:
        return "0.0.0"
