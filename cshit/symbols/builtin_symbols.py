from llvmlite import ir

from cshit.symbols.helper import SymbolsHelper
from cshit.symbols.signature import TypeSignature
from cshit.symbols.symbols import Type


class BuiltInSymbols:
    int_sign: TypeSignature
    int: Type

    void_sign: TypeSignature
    void: Type

    types: list[tuple[TypeSignature, Type]]

    def __init__(self):
        pass

    def init(self):
        self.int_sign, self.int = SymbolsHelper.type_symbol_signature_pair("int")
        self.int.to_primitive(ir .IntType(32))

        self.void_sign, self.void = SymbolsHelper.type_symbol_signature_pair("void")
        self.void.to_primitive(ir.VoidType())

        self.types = [
            (self.int_sign, self.int),
            (self.void_sign, self.void)
        ]


builtin_symbols = BuiltInSymbols()
