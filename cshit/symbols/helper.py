from cshit.symbols.signature import TypeSignature
from cshit.symbols.symbols import Type


class SymbolsHelper:
    @staticmethod
    def type_symbol_signature_pair(name: str) -> tuple[TypeSignature, Type]:
        return TypeSignature(name),Type(name)