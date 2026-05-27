from typing import Self, override

from another_dependency_injector.wiring import inject, Wire

from .interfaces import IParser, WrongToken, MessageError
from ..ast import Statement, \
    Expression, ConstExpression, OpExpression, IdentExpression, FunctionDeclaration, \
    TypeReference, VarDeclaration, FunctionDefinition, CodeBlock, ReturnStatement, File, FileMember, VarDefinition, \
    CastExpression, CallExpression, GetExpression, Directive, ImportDirective, IfStatement
from ..iname import INameProvider, IName
from ..lex.interfaces import ILexer, TokenType, IToken
from ..lex.lexer import Lexer
from ..lex.source import FileSource
from ..lex.token import Token
from ..stack import View, Stack
from ..utils import pretty_list

d = -1

class Parser(IParser): ...

def tprint(*args, **kwargs):
    print(f"    " * d, end="")
    print(*args, **kwargs)

def tfunc(func):
    def wrapper(*args, **kwargs):
        global d
        d += 1
        out = func(*args, **kwargs)
        d -= 1
        return out
    return wrapper

def any_type(*types: TokenType):
    return lambda a: a.type in types

class TokensView(View[IToken]):
    def __init__(self, stack: Stack[Self], data: list[IToken], start: int, end: int):
        super().__init__(stack, data, start, end)

    def after_to_first_type(self, *types: TokenType) -> Self:
        ind = self.find_next(*types, default=-1)
        return self.sub_view(self.pos, ind)

    def find_next[V](self, *types: TokenType, default: V = None) -> int | V:
        return super().find_next(any_type(*types), default=default)

    def find_next_pair(self, left: TokenType, right: TokenType) -> tuple[int, int] | tuple[None, None]:
        depth = 0
        enter_ind: int = 0
        for ind, token in self:
            if token.type is left:
                if depth == 0:
                    enter_ind = ind
                depth += 1
            elif token.type is right:
                if depth == 1:
                    return enter_ind, ind
                depth -= 1
        return None, None

    @override
    def split_all(self, *types: TokenType) -> list[Self]:
        return super().split_all(any_type(*types))


class Depth:
    parser: Parser

    def __init__(self, parser):
        self.parser = parser

    def __enter__(self):
        self.parser.depth += 1

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.parser.depth -= 1


class Parser(IParser):
    lexer: ILexer
    tokens: list[IToken]
    name_provider: INameProvider
    views: Stack[TokensView]

    depth: int
    ignore_new_lines: bool

    constable: list[TokenType]

    unary_operators: list[TokenType]
    binary_operators: list[TokenType]

    binary_operators_sorted: list[list[TokenType]]

    @inject
    def __init__(self, lexer: ILexer = Wire[ILexer], name_provider: INameProvider = Wire[INameProvider]):
        self.lexer = lexer
        self.name_provider = name_provider

        self.ignore_new_lines = True
        self.tokens = []
        self.depth = 0
        self.constable = [TokenType.NUMBER, TokenType.STRING]

        self.unary_operators = [
            TokenType.PLUS,
            TokenType.MINUS,
            TokenType.STAR,
            TokenType.AMPERSAND,
            TokenType.EXCLAIM
        ]

        self.binary_operators_sorted = [ # lower -> more priority
            [TokenType.EQ],
            [TokenType.EQEQ, TokenType.NEQ],
            [TokenType.GE, TokenType.GT, TokenType.LE, TokenType.LT],
            [TokenType.PLUS, TokenType.MINUS],
            [TokenType.STAR, TokenType.SLASH]
        ]

        self.binary_operators = list(token for tokens in self.binary_operators_sorted for token in tokens)

        self.read_all_tokens()
        self.views = Stack()
        self.views.push(TokensView(self.views, self.tokens, 0, len(self.tokens)))

    def skip_white_spaces(self):
        while self.probe().type in [TokenType.NEW_LINE, TokenType.INDENT]:
            self.consume()

    @property
    def inc_depth(self):
        return Depth(self)

    @property
    def pos(self):
        return self.view.pos

    def probe(self, offset: int = 0) -> IToken:
        return self.view[self.view.pos + offset]

    def probe_type(self, *types: TokenType, offset: int = 0) -> bool:
        return self.view.remain() > offset and self.probe(offset).type in types

    def consume(self):
        self.view.consume()

    def accept(self, *types: TokenType, offset: int = 0) -> IToken:
        token = self.probe(offset)
        if token.type in types:
            self.view.pos += 1
            return token
        raise WrongToken(token, *types)

    def read_all_tokens(self):
        while True:
            token = self.lexer.get_next_token()
            self.tokens.append(token)
            if token.type is TokenType.EOF:
                break

    def push_view(self, view: TokensView):
        self.views.append(view)

    def pop_view(self) -> TokensView:
        return self.views.pop()

    @property
    def view(self) -> TokensView:
        return self.views.top()

    def handle_depth(self, token: IToken, depth: int, reverse: bool = False) -> tuple[int, int]:
        """
        RPAREN -> 1

        LPAREN -> -1
        """
        state = 0
        if reverse:
            if token.type is TokenType.RPAREN:
                depth += 1
                state = 1
            elif token.type is TokenType.LPAREN:
                depth -= 1
                state = -1
        else:
            if token.type is TokenType.RPAREN:
                depth -= 1
                state = 1
            elif token.type is TokenType.LPAREN:
                depth += 1
                state = -1

        if depth < 0:
            raise MessageError(f"Found unpaired paren: {token}")

        return depth, state

    def next_level_is_same(self) -> bool:
        with self.view.after().ignore as view:
            depth = 0
            lines = 0
            while True:
                token = self.probe()
                if token == TokenType.NEW_LINE:
                    depth = 0
                    lines += 1
                elif token == TokenType.INDENT:
                    depth += 1
                elif token == TokenType.EOF:
                    out = False
                    break
                else:
                    out = depth == self.depth or lines == 0
                    break
                self.consume()
        if out: view.align_pos(self.view)
        return out

    def parse_Name(self) -> IName:
        return self.name_provider.simple(self.accept(TokenType.IDENT).value_str)

    def parse_Statement(self) -> Statement | None:
        if self.probe_type(TokenType.IDENT) and self.probe_type(TokenType.COLON, offset=1):
            return self.parse_VarDefinition_or_VarDeclaration()
        elif self.probe_type(TokenType.IF):
            return self.parse_IfStatement()
        elif self.probe().type is TokenType.RETURN:
            self.consume()
            expr = self.parse_Expression_to_end_of_line()
            return ReturnStatement(expr)
        return self.parse_Expression_to_end_of_line()

    def parse_IfStatement(self) -> IfStatement:
        conditions: list[Expression] = []
        branches: list[CodeBlock] = []

        self.accept(TokenType.IF)
        while len(conditions) == 0 or (self.next_level_is_same() and self.probe_type(TokenType.ELIF)):
            if len(conditions) != 0: self.consume()
            with self.view.after_to_first_type(TokenType.COLON).to_end as v:
                conditions.append(self.parse_Expression())
            self.accept(TokenType.COLON)
            branches.append(self.parse_CodeBlock())

        negative = None
        if self.next_level_is_same() and self.probe_type(TokenType.ELSE):
            self.consume()
            self.accept(TokenType.COLON)
            negative = self.parse_CodeBlock()
        return IfStatement(conditions, branches, negative)

    @tfunc
    def parse_Expression_to_end_of_line(self) -> Expression | None:
        tprint("expr_teol", self.view)
        with self.view.after_to_first_type(TokenType.NEW_LINE, TokenType.EOF).to_end:
            return self.parse_Expression() if self.view.len != 0 else None

    @tfunc
    def parse_Expression(self) -> Expression:
        tprint("expr", self.view)
        if self.view.len >= 2 and self.view[0] == TokenType.LPAREN:
            depth = 0
            paired = True
            for ind, token in self.view:
                depth, _ = self.handle_depth(token, depth)

                if depth == 0 and ind != self.view.len-1:
                    paired = False
                    break
            if paired:
                with self.view.sub_view(1, self.view.len-1).ignore:
                    out = self.parse_Expression()
                    return out

        # parse binary operators
        depth = 0
        for operators in self.binary_operators_sorted:
            for ind, token in self.view.reversed:
                depth, _ = self.handle_depth(token, depth, True)
                if depth == 0:
                    if token.type in operators and (ind != 0 and self.view[ind - 1] not in [*self.binary_operators, TokenType.LPAREN]) and (ind != self.view.len - 1):
                        left, right = self.view.split(ind)
                        with left.ignore:
                            left_expr = self.parse_Expression()
                        with right.ignore:
                            right_expr = self.parse_Expression()
                        return OpExpression(token.type, [left_expr, right_expr])

        # parse unary operator
        if self.view[0] in self.unary_operators:
            if self.view.len == 1:
                raise MessageError(f"Found single unary operator {self.view[0]}")
            with self.view.after(1).ignore:
                expr = self.parse_Expression()
            return OpExpression(self.view[0].type, [expr])

        # parse cast expression
        if self.view[0] == TokenType.LPAREN:
            left, right = self.view.find_next_pair(TokenType.LPAREN, TokenType.RPAREN)
            if self.view.len <= right or self.probe(right+1).type not in [TokenType.DOT, TokenType.DOUBLE_COLON]: # check if we found complex call expression
                with self.view.sub_view(left + 1, right).ignore:
                    typ = self.parse_TypeReference()
                with self.view.after(right+1).ignore:
                    expr = self.parse_Expression()
                return CastExpression(typ, expr)

        # get/call expression
        depth = 0
        for ind, token in self.view.reversed:
            depth, _ = self.handle_depth(token, depth, True)
            if depth == 0:
                if token == TokenType.LPAREN:
                    self.view.pos = ind
                    first, second = self.view.find_next_pair(TokenType.LPAREN, TokenType.RPAREN)
                    params: list[Expression] = []
                    if first is None:
                        raise MessageError(f"Unable to find pair for {token}")
                    with self.view.before(first-1).ignore:
                        expr = self.parse_Expression()
                    with self.view.sub_view(first+1, second).ignore as v:
                        if v.len > 0:
                            params += self.parse_Expressions_comma_separated()
                    return CallExpression(expr, params)
                elif token.type in [TokenType.DOUBLE_COLON, TokenType.DOT]:
                    left, right = self.view.split(ind)
                    with left.ignore:
                        left_expr = self.parse_Expression()
                    with right.ignore:
                        name = self.parse_Name()
                    return GetExpression(left_expr, name, token == TokenType.DOUBLE_COLON)

        # no binary operators - parse const/ident
        if self.view.len == 1:
            if self.view[0].type in self.constable: # const expr
                return self.parse_ConstExpression()
            elif self.probe() == TokenType.IDENT:
                return self.parse_IdentExpression()

        raise MessageError(f"Unable to parse expression \"{pretty_list(list(i.value for _, i in self.view), " ")}\"")

    @tfunc
    def parse_Expressions_comma_separated(self) -> list[Expression]:
        tprint("expr_cs", self.view)
        out: list[Expression] = []
        depth = 0
        prev = 0
        for ind, token in self.view:
            depth, _ = self.handle_depth(token, depth)
            if depth == 0 and self.view[ind] == TokenType.COMMA:
                with self.view.sub_view(prev, ind).ignore:
                    out.append(self.parse_Expression())
                prev = ind+1
        with self.view.after(prev).ignore:
            out.append(self.parse_Expression())
        return out

    def parse_IdentExpression(self) -> IdentExpression:
        return IdentExpression(self.name_provider.simple(self.accept(TokenType.IDENT).value_str))

    def parse_ConstExpression(self) -> ConstExpression:
        return ConstExpression(self.accept(*self.constable).value)

    def parse_TypeReference(self) -> TypeReference:
        name = self.parse_Name()
        is_ptr = False
        if self.view.remain() >= 1 and self.probe().type is TokenType.STAR:
            self.consume()
            is_ptr = True
        return TypeReference(name, is_ptr)

    def parse_VarDeclaration(self, must_parse_name: bool = True) -> VarDeclaration:
        if must_parse_name or (self.probe_type(TokenType.COLON, offset=1)):
            name = self.parse_Name()
            self.accept(TokenType.COLON)
            type_ref = self.parse_TypeReference()
            return VarDeclaration(name, type_ref)
        else:
            type_ref = self.parse_TypeReference()
            return VarDeclaration(None, type_ref)

    def parse_VarDefinition_or_VarDeclaration(self, must_parse_name: bool = True) -> VarDefinition | VarDeclaration:
        decl = self.parse_VarDeclaration(must_parse_name)
        if self.view.remain() > 0 and self.probe().type is TokenType.EQ:
            if decl.name is None:
                raise MessageError(f"Unable to set initial value to unnamed variable declarations {self.probe()}")
            self.consume()
            with self.view.after_to_first_type(TokenType.EOF, TokenType.NEW_LINE).to_end as v:
                initial = self.parse_Expression()
            return VarDefinition(decl, initial)
        return decl

    def parse_FunctionDeclaration(self) -> FunctionDeclaration:
        params: list[VarDeclaration] = []

        self.accept(TokenType.FN)
        name = self.parse_Name()

        lparen = self.probe()
        if lparen.type is not TokenType.LPAREN:
            raise WrongToken(self.probe(), TokenType.LPAREN)
        start_ind, end_ind = self.view.find_next_pair(TokenType.LPAREN, TokenType.RPAREN)
        if end_ind is None:
            raise MessageError(f"Expected closing parens pair at {lparen}")

        var_arg = False

        with self.view.sub_view(start_ind + 1, end_ind).to_end:
            if self.view.len > 0:
                params_views = self.view.split_all(TokenType.COMMA)
                for i, view in enumerate(params_views):
                    with view.to_end:
                        if i == len(params_views)-1 and self.probe_type(TokenType.ELLIPSIS):
                            var_arg = True
                            continue
                        params.append(self.parse_VarDefinition_or_VarDeclaration(False))
        self.accept(TokenType.RPAREN) # )

        self.accept(TokenType.ARROW_RIGHT)
        type_ref = self.parse_TypeReference()

        return FunctionDeclaration(name, type_ref, params, var_arg)

    def _parse_CodeBlock(self) -> CodeBlock:
        start = self.view.pos
        statements: list[Statement] = []

        while self.next_level_is_same():
            stmt = self.parse_Statement()
            if stmt is not None:
                statements.append(stmt)

        #if self.probe_type(TokenType.NEW_LINE):
        #    self.consume()

        if len(statements) == 0:
            raise MessageError(f"Got empty code block at {self.view[start]}")
        return CodeBlock(statements)

    def parse_CodeBlock(self, inc: bool = True) -> CodeBlock:
        print("pcb", self.probe())
        if inc:
            with self.inc_depth:
                return self._parse_CodeBlock()
        return self._parse_CodeBlock()

    def parse_Directive(self) -> Directive:
        self.accept(TokenType.CRATE)
        token = self.accept(TokenType.IDENT)
        if token.value_str == "import":
            return ImportDirective(self.accept(TokenType.STRING).value_str)

    def parse_FunctionDefinition_or_FunctionDeclaration(self) -> FunctionDefinition | FunctionDeclaration:
        decl = self.parse_FunctionDeclaration()
        if self.probe().type is TokenType.COLON:
            self.consume()
            block = self.parse_CodeBlock()
            return FunctionDefinition(decl, block)
        return decl

    def parse_File(self) -> File:
        members: list[FileMember] = []
        self.skip_white_spaces()
        while self.probe().type is not TokenType.EOF:
            token = self.probe()
            if token.type is TokenType.FN:
                members.append(self.parse_FunctionDefinition_or_FunctionDeclaration())
            elif token.type is TokenType.IDENT:
                members.append(self.parse_VarDefinition_or_VarDeclaration())
            elif token.type is TokenType.CRATE:
                self.handle_directive(members, self.parse_Directive())
            else:
                raise MessageError(f"Unexpected start of File member {token}")
            self.skip_white_spaces()
        out = File(members)
        return out

    def handle_directive(self, members: list[FileMember], directive: Directive):
        if isinstance(directive, ImportDirective):
            directive: ImportDirective = directive
            parser = Parser(Lexer(FileSource(directive.file)), self.name_provider)
            file = parser.parse_File()
            members += file.members
