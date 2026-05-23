import enum
from typing import Self


class TokenType(enum.Enum):
    LPAREN = "("
    RPAREN = ")"
    LBRACE = "{"
    RBRACE = "}"
    LBRACKET = "["
    RBRACKET = "]"
    COMMA = ","
    DOT = "."
    COLON = ":"
    SEMICOLON = ";"
    UNDERSCORE = "_"

    PLUS = "+"
    MINUS = "-"
    STAR = "*"
    SLASH = "/"
    PERCENT = "%"
    CARET = "^"
    AT = "@"
    CRATE = "#"
    TILDE = "~"
    EXCLAIM = "!"
    QUESTION = "?"
    PIPE = "|"
    AMPERSAND = "&"
    DOLLAR = "$"

    EQ = "="
    EQEQ = "=="
    NE = "!="
    LT = "<"
    GT = ">"
    LE = "<="
    GE = ">="
    DOUBLE_COLON = "::"

    AND = "&&"
    OR = "||"

    ARROW_RIGHT = "->"
    VOID_POINTER = "(*)"

    FN = "fn"
    RETURN = "return"
    PASS = "pass"

    INDENT = "    "
    NEW_LINE = "\n"

    CHAR = "CHAR"
    NUMBER = "NUMBER"
    STRING = "STRING"
    IDENT = "IDENT"
    EOF = "EOF"
    ERROR = "ERROR"

    actual_type_notations = [CHAR, NUMBER, STRING, IDENT, EOF, ERROR, INDENT]

    @classmethod
    def scan_values(cls) -> list[Self]:
        return list(filter(lambda a: a not in cls.actual_type_notations.value, sorted([getattr(cls, member_name) for member_name in cls._member_names_ if member_name not in ("actual_type_notations")], key=lambda a: -len(a.value)), ))

class IToken:
    type: TokenType
    value: object
    line: int
    column: int

    value_str: str

class ISource:
    def get_str(self) -> str: ...


class ILexer:
    source: str
    pos: int
    line: int
    col: int

    def get_next_token(self) -> IToken | None: ...
