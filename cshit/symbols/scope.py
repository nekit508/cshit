from typing import TYPE_CHECKING, Literal, Self

if TYPE_CHECKING:
    from cshit.symbols.symbols import Symbol
    from cshit.symbols.signature import FunctionSignature, TypeSignature, Signature
    from .signature import VariableSignature
    from .symbols import Type, Function, Variable

from .symbol_dict import RecursiveSymbolDict
from ..stack import StackableObject, Stack, StackableObjectRef


class UnknownSymbol(Exception):
    signature: "Signature"
    type: Literal["var", "func", "type"]

    def __init__(self,  signature: "Signature", typ: Literal["var", "func", "type"]):
        self.signature = signature
        self.type = typ

    def __repr__(self) -> str:
        return f"Unknown {self.type} with signature {self.signature}"

    def __str__(self) -> str:
        return repr(self)


class AmbiguousSymbol(Exception):
    signature: "Signature"
    type: Literal["var", "func", "type"]

    def __init__(self, signature: "Signature", typ: Literal["var", "func", "type"]):
        self.signature = signature
        self.type = typ

    def __repr__(self) -> str:
        return f"Ambiguous {self.type} with signature {self.signature}"

    def __str__(self) -> str:
        return repr(self)


class SymbolRedefinition(Exception):
    signature: "Signature"
    symbol: "Symbol"
    type: Literal["var", "func", "type"]

    def __init__(self, signature: "Signature", symbol: "Symbol", typ: Literal["var", "func", "type"]):
        self.signature = signature
        self.symbol = symbol
        self.type = typ

    def __repr__(self) -> str:
        return f"{self.type} {self.symbol} with signature {self.signature} redefinition"

    def __str__(self) -> str:
        return repr(self)


class DoubleDeclaration(Exception):
    name: str
    type: str

    def __init__(self, name: str, typ: str):
        self.name = name
        self.type = typ

    def __repr__(self) -> str:
        return f"Double declaration of {self.type} with name \"{self.name}\""


class Scope(StackableObject):
    variables: "RecursiveSymbolDict[VariableSignature, Variable]"
    functions: "RecursiveSymbolDict[FunctionSignature, Function]"
    types: "RecursiveSymbolDict[TypeSignature, Type]"
    parent: "Scope"

    def __init__(self, stack: Stack["Scope"] | None):
        super().__init__(stack)

    def resolve_parent(self, stack: Stack["Scope"] | None):
        self.parent = None if stack is None or len(stack) == 0 else stack.top
        self.variables = RecursiveSymbolDict(self.parent and self.parent.variables)
        self.functions = RecursiveSymbolDict(self.parent and self.parent.functions, False)
        self.types = RecursiveSymbolDict(self.parent and self.parent.types)

    def type_to_dict(self, typ: Literal["var", "func", "type"]) -> "RecursiveSymbolDict":
        return self.variables if typ == "var" else self.functions if typ == "func" else self.types if typ == "type" else None

    def register(self, signature: "Signature", symbol: "Symbol", typ: Literal["var", "func", "type"]):
        self.type_to_dict(typ).register(signature, symbol, SymbolRedefinition(signature, symbol, typ))

    def resolve_all[S:"Symbol"](self, signature: "Signature", typ: Literal["var", "func", "type"]) -> list[S]:
        return self.type_to_dict(typ).resolve(signature, UnknownSymbol(signature, typ))

    def resolve[S:"Symbol"](self, signature: "Signature", typ: Literal["var", "func", "type"]) -> S:
        out = self.resolve_all(signature, typ)
        if len(out) > 1:
            raise AmbiguousSymbol(signature, typ)
        return out[0]

    def set_stack(self, stack: Stack[Self] | None):
        super().set_stack(stack)
        self.resolve_parent(stack)

    @property
    def child(self) -> "StackableObjectRef[Scope]":
        return Scope(self.stack).to()


class ScopeStack(Stack[Scope]):
    def __init__(self):
        super().__init__()
        self.append(Scope(self))