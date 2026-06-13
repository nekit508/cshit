from typing import Self


class Signature:
    def same(self, other: Self) -> bool:
        raise NotImplementedError()


class NamedSignature(Signature):
    name: str

    def __init__(self, name: str):
        self.name = name

    def __repr__(self) -> str:
        return f"{self.name}"


class TypeSignature(NamedSignature):
    def __init__(self, name: str):
        super().__init__(name)

    def same(self, other: Self) -> bool:
        return type(self) is type(other) and self.name == other.name


class VariableSignature(NamedSignature):
    def __init__(self, name: str):
        super().__init__(name)

    def same(self, other: Self) -> bool:
        return type(self) is type(other) and self.name == other.name


class FunctionSignature(NamedSignature):
    params_num: int
    var_args: bool

    def __init__(self, name: str, params_num: int, var_args: bool):
        super().__init__(name)
        self.params_num = params_num
        self.var_args = var_args

    def same(self, other: Self) -> bool:
        return type(self) is type(other) and self.name == other.name and (self.var_args or self.params_num == other.params_num)

    def __repr__(self) -> str:
        return f"{super().__repr__()}({self.params_num}{"..." if self.var_args else ""})"
