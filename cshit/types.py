from another_dependency_injector.wiring import inject, Wire
from llvmlite import ir

from .iname import IName, INameProvider


class PtrType: ...


class Type:
    ptr: PtrType | None

    def __init__(self):
        self.ptr = None

    def test_name(self, name: IName) -> bool:
        return False

    def as_native(self) -> ir.types.Type:
        raise NotImplementedError()

    def as_ptr(self) -> PtrType:
        if self.ptr is None:
            self.ptr = PtrType(self)
        return self.ptr


class PtrType(Type):
    enclosing: Type

    def __init__(self, enclosing: Type):
        super().__init__()
        self.enclosing = enclosing

    def as_native(self) -> ir.types.Type:
        native = self.enclosing.as_native()
        return ir.IntType(8).as_pointer() if isinstance(native, ir.VoidType) else native.as_pointer()


class NamedType(Type):
    full_name: IName

    def __init__(self, full_name: IName):
        super().__init__()
        self.full_name = full_name

    def name(self) -> IName:
        return self.full_name

    def test_name(self, name: IName) -> bool:
        return self.full_name.actual() == name.actual()


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


class PrimitiveType(NamedType):
    type: ir.types.Type

    @inject
    def __init__(self, name: str, typ: ir.types.Type, name_provider: INameProvider = Wire[INameProvider]):
        super().__init__(name_provider.simple(name))
        self.type = typ

    def as_native(self) -> ir.types.Type:
        return self.type