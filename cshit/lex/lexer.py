from another_dependency_injector.wiring import injection, inject, Wire, InjectionType

from .interfaces import ILexer, ISource, TokenType
from .token import Token


@injection(InjectionType.SINGLETON)
class Lexer(ILexer):
    indent_size: int
    indent: str

    @inject
    def __init__(self, source: ISource = Wire[ISource], ident_size: int = 4):
        self.source = source.get_str()
        self.pos = 0
        self.line = 1
        self.col = 1

        self.indent_size = ident_size
        self.indent = " " * self.indent_size

    def to_end(self) -> int:
        return len(self.source) - self.pos

    def is_fit(self, size: int) -> bool:
        return self.to_end() >= size

    def peek(self) -> str:
        if self.pos >= len(self.source):
            return "\0"
        return self.source[self.pos]

    def advance(self) -> str:
        ch = self.peek()
        self.pos += 1
        if ch == "\n":
            self.line += 1
            self.col = 1
        else:
            self.col += 1
        return ch

    def advance_n(self, n: int):
        for i in range(n):
            self.advance()

    def cmp(self, s: str) -> bool:
        return self.is_fit(len(s)) and self.source[self.pos:self.pos+self.indent_size] == s

    def skip_whitespace_or_get_idents(self) -> Token | None:
        while self.peek() in " \t\r":
            ch = self.peek()
            if ch == "\t":
                self.advance()
                return Token(TokenType.INDENT, self.indent, self.line, self.col)
            if ch == " " and self.cmp(self.indent):
                self.advance_n(self.indent_size)
                return Token(TokenType.INDENT, self.indent, self.line, self.col)

            self.advance()

        return None

    def read_number(self) -> Token:
        start_col = self.col
        num = ''
        while self.peek().isdigit():
            num += self.advance()
        if self.peek() == ".":
            num += self.advance()
            while self.peek().isdigit():
                num += self.advance()
        return Token(TokenType.NUMBER, int(num) if "." not in num else float(num), self.line, start_col)

    def read_identifier_or_keyword(self) -> Token:
        start_col = self.col
        ident = ''
        while self.peek().isalnum() or self.peek() == "_":
            ident += self.advance()
        return Token(TokenType.IDENT, ident, self.line, start_col)

    def get_next_token(self) -> Token | None:
        indent = self.skip_whitespace_or_get_idents()
        if indent is not None:
            return indent

        ch = self.peek()
        if ch == "\0":
            self.advance()
            return Token(TokenType.EOF, "\0", self.line, self.pos)

        for token_type in TokenType.scan_values():
            l = len(token_type.value)
            if self.is_fit(l) and token_type.value == self.source[self.pos:self.pos+l]:
                out = Token(token_type, token_type.value, self.line, self.col)
                self.advance_n(l)
                return out

        if ch.isdigit():
            return self.read_number()

        if ch.isalpha() or ch == "_":
            return self.read_identifier_or_keyword()

        raise SyntaxError(f"Unexpected char \"{ch}\" at {self.line}:{self.col}")