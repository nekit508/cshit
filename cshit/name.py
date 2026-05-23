from another_dependency_injector.wiring import injection, InjectionType

from .iname import IName, INameProvider


class Name(IName):
    name: str

    def __init__(self, name: str):
        self.name = name

    def actual(self) -> str:
        return self.name

    def __repr__(self) -> str:
        return self.actual()


@injection(InjectionType.SINGLETON)
class DefaultNameProvider(INameProvider):
    def __init__(self):
        pass

    def simple(self, name: str) -> IName:
        return Name(name)