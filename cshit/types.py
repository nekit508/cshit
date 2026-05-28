from typing import Self

from another_dependency_injector.wiring import inject, Wire
from llvmlite import ir

from .iname import IName, INameProvider


class PtrType: ...

# abstract
class Type:
    _ptr: PtrType | None

    def __init__(self):
        self._ptr = None

    def test_name(self, name: IName) -> bool:
        return False

    def as_native(self) -> ir.types.Type:
        raise NotImplementedError()

    def as_ptr(self) -> PtrType:
        if self._ptr is None:
            self._ptr = PtrType(self)
        return self._ptr

    def de_ptr(self) -> Self:
        if isinstance(self, PtrType):
            return self.enclosing
        raise NotImplementedError("Cannot de-ptr not ptr type")

    @property
    def is_ptr(self):
        return self.as_native().is_pointer

    @property
    def is_func(self):
        return isinstance(self, FunctionType)

    @property
    def is_primitive(self):
        return isinstance(self, PrimitiveType)

    @property
    def is_structure(self):
        return isinstance(self, StructureType)


# abstract
class ContainerType(Type):
    def get_member(self, name: str) -> Type:
        raise NotImplementedError


class PtrType(Type):
    enclosing: Type

    def __init__(self, enclosing: Type):
        super().__init__()
        self.enclosing = enclosing

    def as_native(self) -> ir.types.Type:
        native = self.enclosing.as_native()
        return ir.IntType(8).as_pointer() if isinstance(native, ir.VoidType) else native.as_pointer()

    def __repr__(self) -> str:
        return f"Ptr<{self.enclosing}>"


# abstract
class NamedType(Type):
    full_name: IName

    def __init__(self, full_name: IName):
        super().__init__()
        self.full_name = full_name

    def name(self) -> IName:
        return self.full_name

    def test_name(self, name: IName) -> bool:
        return self.full_name.actual() == name.actual()


class FunctionType(NamedType):
    ret: Type
    params: list[Type]
    var_arg: bool

    def __init__(self, full_name: IName, ret: Type, params: list[Type], var_arg: bool):
        super().__init__(full_name)
        self.ret = ret
        self.params = params
        self.var_arg = var_arg

    def __repr__(self) -> str:
        from .utils import pretty_list
        return f"{self.name().actual()}({pretty_list(self.params)}) -> {self.ret}"

    def as_native(self) -> ir.types.Type:
        return ir.FunctionType(self.ret.as_native(), list(param.as_native() for param in self.params), var_arg=self.var_arg)


class RecursiveType(Type):
    parent: Type

    def __init__(self, parent: Type):
        super().__init__()
        self.parent = parent

    def as_native(self) -> ir.types.Type:
        return self.parent.as_native()

    def as_ptr(self) -> PtrType:
        return self.parent.as_ptr()

    def test_name(self, name: IName) -> bool:
        return self.parent.test_name(name)

    def __repr__(self) -> str:
        return f"<{self.parent}>"


class PrimitiveType(NamedType):
    type: ir.types.Type

    @inject
    def __init__(self, name: str, typ: ir.types.Type, name_provider: INameProvider = Wire[INameProvider]):
        super().__init__(name_provider.simple(name))
        self.type = typ

    def as_native(self) -> ir.types.Type:
        return self.type

    def __repr__(self) -> str:
        return f"{self.type}"


class StructureType(NamedType, ContainerType):
    fields: dict[str, Type]
    fields_idx: dict[str, int]
    methods: dict[str, FunctionType]
    _structure_instance: "StructureInstance"

    def __init__(self, full_name: IName, fields: dict[str, Type], methods: dict[str, FunctionType]):
        super().__init__(full_name)
        self.fields = fields
        self.methods = methods
        self._structure_instance = StructureInstance(self)

    def __repr__(self) -> str:
        from .utils import pretty_dict
        return f"{self.name().actual()}<fields:[{pretty_dict(self.fields)}] methods:[{pretty_dict(self.methods)}]>"

    def get_member(self, name: str) -> "Type":
        return self.fields[name] or self.methods[name]

    def as_ptr(self) -> PtrType:
        raise NotImplementedError("Cannot get ptr of structure type")

    def get_instance(self) -> "StructureInstance":
        return self._structure_instance


class StructureInstance(NamedType, ContainerType):
    structure_type: StructureType

    def __init__(self, structure_type: StructureType):
        super().__init__(structure_type.full_name)
        self.structure_type = structure_type

    def __repr__(self) -> str:
        return f"StructureInstance<{self.structure_type}>"

    def get_member(self, name: str) -> "Type":
        return self.structure_type.fields[name] or self.structure_type.methods[name]