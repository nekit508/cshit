from typing import Self


class RecursiveDict[T]:
    data: dict[str, T]
    parent: Self | None

    def __init__(self, parent: Self | None):
        self.data = {}
        self.parent = parent

    def register(self, name: str, obj: T) -> bool:
        if name in self.data:
            return False
        else:
            self.data[name] = obj
            return True

    def resolve(self, name: str) -> T | None:
        if name in self.data:
            return self.data[name]
        elif self.parent is not None:
            return self.parent.resolve(name)
        else: return None

    def __getitem__(self, name: str) -> T | None:
        return self.resolve(name)

    def __setitem__(self, name: str, obj: T) -> bool:
        return self.register(name, obj)

    #def __repr__(self):
    #    from cshit.utils import pretty_list
    #    print(f"{pretty_list(list(f"{i}: {self[i]}" for i in self))}")
