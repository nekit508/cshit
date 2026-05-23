from llvmlite.ir import IntType, VoidType, FloatType

from cshit.types import PrimitiveType

class BuiltinTypes:
    int_type: PrimitiveType | None
    char_type: PrimitiveType | None
    float_type: PrimitiveType | None
    void_type: PrimitiveType | None

    def __init__(self):
        self.int_type = None
        self.char_type = None
        self.float_type = None
        self.void_type = None

    def init(self):
        self.int_type = PrimitiveType("int", IntType(32))
        self.char_type = PrimitiveType("char", IntType(8))
        self.float_type = PrimitiveType("float", FloatType())
        self.void_type = PrimitiveType("void", VoidType())

builtin_types = BuiltinTypes()