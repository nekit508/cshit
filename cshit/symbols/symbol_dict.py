from dataclasses import dataclass
from typing import Self, TYPE_CHECKING

if TYPE_CHECKING:
    from .signature import Signature
    from .symbols import Symbol


class SymbolDictEntry[S:Signature, T:"Symbol"]:
    signature: S
    symbols: list[T]
    unique: bool

    def __init__(self, signature: S, unique: bool = True):
        self.signature = signature
        self.symbols = []
        self.unique = unique

    def add(self, symbol: T) -> bool:
        if any(s.same(symbol) for s in self.symbols):
            return False
        self.symbols.append(symbol)
        return True

    def __eq__(self, signature: S | Self): # for "[entry] == [signature]"
        if isinstance(signature, SymbolDictEntry):
            return super().__eq__(signature)
        else: return self.signature.same(signature)


class SymbolDict[S:Signature, T:"Symbol"]:
    entries: list[SymbolDictEntry[S, T]]
    unique: bool

    def __init__(self, unique: bool = True):
        self.entries = []
        self.unique = unique

    def register(self, signature: S, symbol: T, error: Exception | None = None):
        for entry in self.entries:
            if entry == signature:
                entry.symbols.append(symbol)
                break
        else:
            entry = SymbolDictEntry(signature, self.unique)
            self.entries.append(entry)
            if not entry.add(symbol) and error is not None:
                raise error

    def resolve(self, signature: S, error: Exception | None = None) -> list["Symbol"] | None:
        for entry in self.entries:
            if entry == signature:
                return entry.symbols.copy()
        if error is None:
            return None
        raise error

    def __iter__(self):
        for entry in self.entries:
            for symbol in entry.symbols:
                yield symbol


class RecursiveSymbolDict[S:Signature, T:"Symbol"](SymbolDict[S, T]):
    parent: SymbolDict[S, T] | None

    def __init__(self, parent: SymbolDict[S, T] | None, unique: bool = True):
        super().__init__(unique)
        self.parent = parent

    def resolve(self, signature: S, error: Exception | None = None) -> list["Symbol"] | None:
        out = super().resolve(signature) or self.parent and self.parent.resolve(signature)
        if out is not None or error is None:
            return out
        raise error