from another_dependency_injector.wiring import injection, InjectionType, inject, Wire

from .interfaces import ISource


class Source(ISource):
    def __init__(self):
        pass

    def get_str(self) -> str:
        raise NotImplementedError()


@injection(InjectionType.SINGLETON)
class FileSource(Source):
    file: str

    @inject
    def __init__(self, file: str = Wire["input_file"]):
        super().__init__()
        self.file = file

    def get_str(self) -> str:
        with open(self.file, "r") as fi:
            out = fi.read()
        return out