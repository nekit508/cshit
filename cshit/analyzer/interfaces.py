from ..ast import AST
from ..iname import IName
from ..types import Type


class UnresolvedType(Exception):
    name: IName

    def __init__(self, name: IName):
        self.name = name

    def __str__(self) -> str:
        return self.__repr__()

    def __repr__(self) -> str:
        return f"Unresolved type {self.name}"


class TypesMismatch(Exception):
    type1: Type
    type2: Type
    ast1: AST
    ast2: AST

    def __init__(self, type1: Type, type2: Type, ast1: AST, ast2: AST):
        self.type1 = type1
        self.type2 = type2
        self.ast1 = ast1
        self.ast2 = ast2

    def __str__(self) -> str:
        return self.__repr__()

    def __repr__(self) -> str:
        return f"Mismatched types {self.type1} of {self.ast1} and {self.type2} of {self.ast2}"


class IAnalyzer:
    pass