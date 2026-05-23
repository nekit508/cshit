from ast import parse

from another_dependency_injector.wiring import inject, Wire

from ..ast import TypeReference, FunctionDefinition, VarDeclaration, FunctionDeclaration, CodeBlock, Statement, \
    PassStatement, ReturnStatement, Expression, ConstExpression, AST, CallExpression
from .interfaces import IParser, ParserError, MessageError, WrongToken
from ..iname import IName, INameProvider
from ..lex.interfaces import ILexer, TokenType, IToken
from ..utils import pretty_list


class TokensView:
    tokens: list[IToken]
    start: int
    end: int
    pos: int

    def __init__(self, parser: object, start: int, end: int, ):
        self.parser = parser
        self.start = start
        self.end = end
        self.pos = 0

    def __getitem__(self, ind: int):
        return self.tokens[self.pos + ind]

    def offset_edges(self, offset: int):
        self.start += offset
        self.end += offset

    def __repr__(self) -> str:
        return f"{self.start}:{self.end}|{self.pos} {pretty_list(self.tokens[self.start:self.end])}"


class Parser(IParser):
    lexer: ILexer
    tokens: list[IToken]
    name_provider: INameProvider
    constable: list[TokenType]
    parks: list[int]
    tokens_views: list[TokensView]

    depth: int
    ignore_new_lines: bool

    pos: object

    @inject
    def __init__(self, lexer: ILexer = Wire[ILexer], name_provider: INameProvider = Wire[INameProvider]):
        self.lexer = lexer
        self.name_provider = name_provider

        self.ignore_new_lines = True
        self.tokens = []
        self.parks = []
        self.depth = 0
        self.constable = [TokenType.NUMBER, TokenType.STRING]

        self.read_all_token()
        self.tokens_views = [TokensView(self, 0, len(self.tokens))]
        #print(*self.tokens, sep="\n")

    def resolve_index(self, offset: int = 0, absolute: int | None = None, additional: int = 0, end: bool = False) -> int:
        return self.pos + offset + additional if absolute is None else absolute + additional

    def read_all_token(self):
        while True:
            token = self.lexer.get_next_token()
            self.tokens.append(token)

            if token.type is TokenType.EOF:
                break

    def select_to_end_if_line(self) -> TokensView:
        return self.select_to_first([TokenType.NEW_LINE, TokenType.EOF])

    def select_to_first(self, types: list[TokenType], start: int | None = None, forward: bool = True) -> TokensView | None:
        ignore_new_lines = not TokenType.NEW_LINE in types
        l = start
        while self.token(offset=l, ignore_new_lines=ignore_new_lines).type in types:
            l += 1 if forward else -1
            if l < 0:
                return None
            elif l > self.len():
                return None
        return self.push_view(self.resolve_index(start), self.resolve_index(l))

    @property
    def pos(self) -> int:
        return self.view().pos

    def len(self) -> int:
        view = self.view()
        return view.end - view.start

    def push_view(self, start: int, end: int) -> TokensView:
        out = TokensView(self, start, end)
        self.tokens_views.append(out)
        return out

    def push_view_l(self, length: int) -> TokensView:
        return self.push_view(self.pos, self.pos + length)

    def pop_view(self) -> TokensView:
        return self.tokens_views.pop()

    def view(self) -> TokensView | None:
        return self.tokens_views[-1] if len(self.tokens_views) else None

    def nl(self):
        self.accept(TokenType.NEW_LINE)

    def push_park(self):
        self.parks.append(self.view().pos)

    def pop_park(self) -> int:
        return self.parks.pop()

    def ret_park(self):
        self.view().pos = self.parks[-1]

    def token(self, ignore_new_lines: bool | None = None, **args: int) -> IToken:
        i = 0
        while (self.ignore_new_lines if ignore_new_lines is None else ignore_new_lines) and self.tokens[self.resolve_index(**args, additional=i)].type is TokenType.NEW_LINE:
            i += 1
        return self.tokens[self.resolve_index(**args, additional=i)]

    def consume(self, **kwargs) -> IToken:
        token = self.token(**kwargs)
        self.view().pos += 1
        return token

    def accept(self, token_type: TokenType) -> IToken:
        token = self.consume(ignore_new_lines = token_type is not TokenType.NEW_LINE)
        if token.type is token_type:
            return token
        raise WrongToken(token.type, [token_type])

    def probe(self, token_type: TokenType, **args: int) -> bool:
        token = self.token(**args)
        return token.type is token_type

    def name(self, name: str) -> IName:
        return self.name_provider.simple(name)

    def parse_Name(self) -> IName:
        return self.name(self.accept(TokenType.IDENT).value_str)

    def try_parse_depth(self) -> bool:
        #l = list(self.token(i) for i in range(self.depth))
        ok = all(self.probe(TokenType.INDENT, offset=i) for i in range(self.depth))
        #print(ok, l)
        if ok:
            for i in range(self.depth):
                self.consume()
        return ok

    def parse_TypeReference(self) -> TypeReference:
        return TypeReference(self.parse_Name())

    def parse_VarDeclaration(self) -> VarDeclaration:
        name = self.parse_Name()
        self.accept(TokenType.COLON)
        typee = self.parse_TypeReference()
        return VarDeclaration(name, typee)

    def parse_FunctionDeclaration(self):
        params: list[VarDeclaration] = []

        self.accept(TokenType.FN)
        name = self.parse_Name()

        self.accept(TokenType.LPAREN)
        if not self.probe(TokenType.RPAREN):
            while True:
                params.append(self.parse_VarDeclaration())
                if not self.probe(TokenType.COMMA):
                    self.accept(TokenType.RPAREN)
                    break
                else: self.consume()
        else: self.consume()

        self.accept(TokenType.ARROW_RIGHT)
        ret = self.parse_TypeReference()

        return FunctionDeclaration(name, ret, params)

    # part of code, which can represent any value

    def parse_Expression(self) -> Expression:
        view = self.select_to_first([TokenType.RPAREN], self.len(), False)
        print(view)
        if view is not None:
            pass

    def parse_ConstExpression(self) -> ConstExpression:
        token = self.token()
        if token.type in self.constable:
            self.consume()
            return ConstExpression(token.value)
        else: raise MessageError(f"Expected one of {pretty_list(self.constable)} got {token.type}")

    def parse_CallExpression(self) -> CallExpression:
        called = self.parse_Expression()
        return CallExpression(called)

    # common part of code, ts does not return value generally

    def parse_Statement(self) -> Statement:
        if self.probe(TokenType.RETURN):
            return self.parse_ReturnStatement()
        else: # no keyword which represents start of any other statement found
            self.select_to_end_if_line()
            return self.parse_Expression()

    def parse_ReturnStatement(self) -> ReturnStatement:
        self.accept(TokenType.RETURN)
        return ReturnStatement(self.parse_Expression())

    def parse_CodeBlock(self) -> CodeBlock:
        statements: list[Statement] = []

        while self.try_parse_depth():
            statements.append(self.parse_Statement())

        return CodeBlock(statements)

    # general syntax shit

    def parse_FunctionDefinition(self) -> FunctionDefinition:
        decl = self.parse_FunctionDeclaration()
        self.accept(TokenType.COLON)

        self.depth += 1
        code = self.parse_CodeBlock()

        return FunctionDefinition(decl, code)