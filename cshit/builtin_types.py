from dataclasses import dataclass

from llvmlite.ir import IntType, VoidType, FloatType, PointerType

from cshit.lex.interfaces import TokenType
from cshit.types import PrimitiveType, PtrType, Type


@dataclass
class DowncastRule:
    target: Type
    ascendants: list[Type]


class BuiltinTypes:
    int_type: PrimitiveType
    char_type: PrimitiveType
    float_type: PrimitiveType
    void_type: PrimitiveType
    bool_type: PrimitiveType
    ptr_type: PtrType

    types_priorities: dict[Type, int]

    map: dict[str, Type]
    ranks: dict[Type, int]

    floats: list[Type]
    signed_integers: list[Type]
    unsigned_integers: list[Type]
    integers: list[Type]

    logic_binary_operators: list[TokenType]
    arithmetic_binary_operators: list[TokenType]

    def __init__(self):
        pass

    def init(self):
        self.int_type = PrimitiveType("int", IntType(32))
        self.char_type = PrimitiveType("char", IntType(8))
        self.float_type = PrimitiveType("float", FloatType())
        self.bool_type = PrimitiveType("bool", IntType(1))

        self.void_type = PrimitiveType("void", VoidType())
        self.ptr_type = self.char_type.as_ptr()

        self.map = {
            "int": self.int_type,
            "char": self.char_type,
            "float": self.float_type,
            "bool": self.bool_type,

            "void": self.void_type,
            "ptr": self.ptr_type,
        }

        self.ranks = {
            self.bool_type:     0,
            self.char_type:     10,
            self.int_type:      40,
            self.float_type:    540,
        }

        self.floats = [
            self.float_type
        ]

        self.signed_integers = [
            self.int_type,
            self.char_type,
            self.bool_type,
            self.void_type,
            self.ptr_type,
        ]

        self.unsigned_integers = [

        ]

        self.integers = self.signed_integers + self.unsigned_integers

        self.logic_binary_operators = [
            TokenType.EQEQ,
            TokenType.NEQ,
            TokenType.GE,
            TokenType.GT,
            TokenType.LE,
            TokenType.LT
        ]

        self.arithmetic_binary_operators = [
            TokenType.PLUS,
            TokenType.MINUS,
            TokenType.STAR,
            TokenType.SLASH
        ]

builtin_types = BuiltinTypes()