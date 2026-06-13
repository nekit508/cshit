import typing
from typing import Self, Literal, Union

from llvmlite.ir import IntType, FloatType

from .scope import Scope

from llvmlite import ir

from .signature import Signature, TypeSignature, VariableSignature, FunctionSignature
from ..utils import single_entry


class Value: # result of expression
    kind: Literal["rvalue", "lvalue", "symbol"]
    type: "Type"

    def __init__(self, kind: Literal["rvalue", "lvalue", "symbol"], typ: "Type"):
        self.kind = kind
        self.type = typ

    @property
    def is_value(self) -> bool:
        return self.is_lvalue or self.is_rvalue

    @property
    def is_rvalue(self) -> bool:
        return self.kind == "rvalue"

    @property
    def is_lvalue(self) -> bool:
        return self.kind == "lvalue"

    @property
    def is_symbol(self) -> bool:
        return self.kind == "symbol"

class Symbol:
    def __init__(self):
        pass

    def same[S:Symbol](self, other: S) -> bool:
        raise NotImplementedError()


class NamedSymbol(Symbol):
    name: str

    def __init__(self, name: str):
        super().__init__()
        self.name = name

    def same[S:"Symbol"](self, other: S) -> bool:
        return type(self) is type(other) and self.name == other.name

    def signature[S:"Signature"](self) -> S:
        raise NotImplementedError()


class Type(NamedSymbol):
    _native: ir.Type | None
    _ptr: typing.Union["Type", None]

    # primitive fields
    primitive: ir.Type | None

    # synthetic fields
    members: Union["Scope", None]

    # pointer fields
    pointed: Union["Type", None]

    # function fields
    ret: Union["Type", None]
    params: list["Type"] | None
    var_args: bool | None

    def __init__(self, name: str):
        super().__init__(name)
        self._ptr = None
        self._native = None

        self.primitive = None
        self.members = None
        self.pointed = None
        self.ret = None
        self.params = None
        self.var_args = None

    @property
    @single_entry(arg = 0)
    def signature(self) -> TypeSignature:
        if self.is_function:
            raise ValueError("Function types does not have signatures")
        return TypeSignature(self.name)

    def to_function(self, ret: "Type", params: list["Type"], var_args: bool) -> Self:
        self.ret = ret
        self.params = params
        self.var_args = var_args
        return self

    @property
    def is_function(self) -> bool:
        return self.ret is not None

    def to_primitive(self, typ: ir.Type) -> Self:
        self.primitive = typ
        return self

    @property
    def is_primitive(self) -> bool:
        return self.primitive is not None

    def to_synthetic(self) -> Self:
        self.members = Scope(None)
        return self

    @property
    def is_synthetic(self) -> bool:
        return self.members is not None

    def to_pointer(self, typ: "Type") -> Self:
        self.pointed = typ
        return self

    @property
    def is_pointer(self) -> bool:
        return self.pointed is not None

    @property
    def as_ptr(self) -> Self:
        if self._ptr is None:
            self._ptr = Type(self.name + "*")
            self._ptr.to_pointer(self)

        return self._ptr

    def native[T:ir.Type](self, context: "ir.context.Context") -> T:
        if self._native is None:
            if self.is_pointer:
                self._native = ir.PointerType(self.pointed.native(context))
            elif self.is_primitive:
                self._native = self.primitive
            elif self.is_synthetic:
                self._native: ir.IdentifiedStructType = context.get_identified_type(self.name)
                self._native.set_body(*list(member.type.native(context) for member in self.members.variables))
            elif self.is_function:
                self._native = ir.FunctionType(self.ret, list(param.native(context) for param in self.params), self.var_args)
            else: raise NotImplementedError("Unknown Type type")
        return self._native

    def __repr__(self) -> str:
        return f"Type<synth:{self.is_synthetic} prim:{self.is_primitive} ptr:{self.is_pointer}>"

    def same[S:Symbol](self, other: S) -> bool:
        return not other.is_function and not self.is_function and super().same(other) or \
            self.is_function and other.is_function and self.ret.same(other) and \
            len(self.params) == len(other.params) and \
            all(p.same(other.params[i]) for i, p in enumerate(self.params))

    def can_cast_to(self, other: "Type") -> bool:
        return self.is_pointer and other.is_pointer or \
            self.is_synthetic and self is other or \
            self.is_primitive and other.is_primitive and self.can_cast_to_primitive(other) or \
            self.is_function and other.is_function and self.can_call_as(other)

    def can_cast_to_primitive(self, other: "Type") -> bool:
        return True

    def can_call_as(self, other: "Type") -> bool:
        return self.ret.can_cast_to(other.ret) and \
            len(self.params) == len(other.params) and \
            all(other.params[i].can_cast_to(p) for i, p in enumerate(self.params))


class Variable(NamedSymbol):
    type: Type

    def __init__(self, name: str, typ: Type):
        super().__init__(name)
        self.type = typ

    @property
    @single_entry(arg = 0)
    def signature(self) -> VariableSignature:
        return VariableSignature(self.name)

    def same[S:Symbol](self, other: S) -> bool:
        return super().same(other) and self.type.same(other.type)


class Function(NamedSymbol):
    type: Type
    scope: Scope

    def __init__(self, name: str, typ: Type):
        super().__init__(name)
        self.type = typ
        self.scope = Scope(None)

    @property
    @single_entry(arg = 0)
    def signature(self) -> FunctionSignature:
        return FunctionSignature(self.name, len(self.type.params), self.type.var_args)

    def same[S:Symbol](self, other: S) -> bool:
        return super().same(other) and self.type.same(other.type)

    def native(self, context: "ir.context.Context") -> ir.FunctionType:
        return self.type.native(context)
