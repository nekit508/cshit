from dataclasses import dataclass

from .interfaces import IToken, TokenType


@dataclass
class Token(IToken):
    type: TokenType
    value: object
    line: int
    column: int

    @property
    def value_str(self) -> str:
        return str(self.value)

    def __repr__(self) -> str:
        #return f"\"{self.value}\"<{self.type.name}>({self.line}:{self.column})"
        return f"\"{self.value}\" {self.line}:{self.column}".replace("\n", "\\n")